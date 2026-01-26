import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.infrastructure.tools.exchange_rates import ExchangeRateTool, ConversionResult


@pytest.fixture
def tool():
    return ExchangeRateTool()


class TestExchangeRateToolDefinition:
    def test_tool_definition_has_correct_name(self, tool):
        assert tool.TOOL_DEFINITION["function"]["name"] == "convert_currency"

    def test_tool_definition_has_required_parameters(self, tool):
        params = tool.TOOL_DEFINITION["function"]["parameters"]
        assert "amount" in params["properties"]
        assert "from_currency" in params["properties"]
        assert "to_currency" in params["properties"]
        assert params["required"] == ["amount", "from_currency", "to_currency"]

    def test_tool_definition_has_description(self, tool):
        assert "convert" in tool.TOOL_DEFINITION["function"]["description"].lower()


class TestConvertCurrency:
    @pytest.mark.asyncio
    async def test_converts_currency_successfully(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "amount": 100,
            "base": "USD",
            "date": "2024-01-15",
            "rates": {"EUR": 92.5}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.convert_currency(100, "USD", "EUR")

            assert isinstance(result, ConversionResult)
            assert result.amount == 100
            assert result.from_currency == "USD"
            assert result.to_currency == "EUR"
            assert result.converted_amount == 92.5
            assert result.rate == 0.925

    @pytest.mark.asyncio
    async def test_normalizes_currency_codes_to_uppercase(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "amount": 50,
            "rates": {"GBP": 40.0}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.convert_currency(50, "usd", "gbp")

            assert result.from_currency == "USD"
            assert result.to_currency == "GBP"

    @pytest.mark.asyncio
    async def test_calls_correct_api_endpoint(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"rates": {"EUR": 100}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.convert_currency(100, "USD", "EUR")

            mock_client.get.assert_called_once_with(
                "https://api.frankfurter.app/latest",
                params={"amount": 100, "from": "USD", "to": "EUR"}
            )

    @pytest.mark.asyncio
    async def test_handles_zero_amount(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"rates": {"EUR": 0}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.convert_currency(0, "USD", "EUR")

            assert result.amount == 0
            assert result.rate == 0

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, tool):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await tool.convert_currency(100, "USD", "EUR")


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_convert_currency(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = {"rates": {"EUR": 92.5}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute(
                "convert_currency",
                {"amount": 100, "from_currency": "USD", "to_currency": "EUR"}
            )

            assert "100 USD" in result
            assert "92.50 EUR" in result
            assert "rate" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_raises_on_unknown_function(self, tool):
        with pytest.raises(ValueError, match="Unknown function"):
            await tool.execute("unknown_function", {})
