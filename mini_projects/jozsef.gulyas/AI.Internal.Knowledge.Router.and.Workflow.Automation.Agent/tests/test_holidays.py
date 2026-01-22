import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.infrastructure.tools.holidays import HolidayTools, Holiday


@pytest.fixture
def tool():
    return HolidayTools()


@pytest.fixture
def sample_holidays_response():
    return [
        {
            "date": "2024-01-01",
            "localName": "New Year's Day",
            "name": "New Year's Day",
            "countryCode": "US",
            "fixed": True,
            "global": True
        },
        {
            "date": "2024-07-04",
            "localName": "Independence Day",
            "name": "Independence Day",
            "countryCode": "US",
            "fixed": True,
            "global": True
        },
        {
            "date": "2024-12-25",
            "localName": "Christmas Day",
            "name": "Christmas Day",
            "countryCode": "US",
            "fixed": True,
            "global": True
        }
    ]


class TestHolidayToolsDefinitions:
    def test_has_two_tool_definitions(self, tool):
        assert len(tool.TOOL_DEFINITIONS) == 2

    def test_is_us_holiday_definition(self, tool):
        is_holiday_def = next(
            d for d in tool.TOOL_DEFINITIONS
            if d["function"]["name"] == "is_us_holiday"
        )
        assert "date" in is_holiday_def["function"]["parameters"]["properties"]
        assert is_holiday_def["function"]["parameters"]["required"] == ["date"]

    def test_list_us_holidays_definition(self, tool):
        list_holidays_def = next(
            d for d in tool.TOOL_DEFINITIONS
            if d["function"]["name"] == "list_us_holidays"
        )
        assert "year" in list_holidays_def["function"]["parameters"]["properties"]
        assert list_holidays_def["function"]["parameters"]["required"] == ["year"]


class TestIsUsHoliday:
    @pytest.mark.asyncio
    async def test_returns_true_for_holiday(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            is_holiday, name = await tool.is_us_holiday("2024-12-25")

            assert is_holiday is True
            assert name == "Christmas Day"

    @pytest.mark.asyncio
    async def test_returns_false_for_non_holiday(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            is_holiday, name = await tool.is_us_holiday("2024-03-15")

            assert is_holiday is False
            assert name is None

    @pytest.mark.asyncio
    async def test_calls_correct_api_endpoint(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.is_us_holiday("2024-07-04")

            mock_client.get.assert_called_once_with(
                "https://date.nager.at/api/v3/PublicHolidays/2024/US"
            )

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
                await tool.is_us_holiday("2024-12-25")


class TestListUsHolidays:
    @pytest.mark.asyncio
    async def test_returns_list_of_holidays(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            holidays = await tool.list_us_holidays(2024)

            assert len(holidays) == 3
            assert all(isinstance(h, Holiday) for h in holidays)

    @pytest.mark.asyncio
    async def test_holiday_has_correct_attributes(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            holidays = await tool.list_us_holidays(2024)

            christmas = next(h for h in holidays if "Christmas" in h.name)
            assert christmas.date == "2024-12-25"
            assert christmas.name == "Christmas Day"
            assert christmas.local_name == "Christmas Day"
            assert christmas.is_fixed is True
            assert christmas.is_global is True

    @pytest.mark.asyncio
    async def test_calls_correct_api_endpoint(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await tool.list_us_holidays(2025)

            mock_client.get.assert_called_once_with(
                "https://date.nager.at/api/v3/PublicHolidays/2025/US"
            )

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_no_holidays(self, tool):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            holidays = await tool.list_us_holidays(2024)

            assert holidays == []


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_is_us_holiday_returns_yes(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute("is_us_holiday", {"date": "2024-12-25"})

            assert "Yes" in result
            assert "Christmas Day" in result

    @pytest.mark.asyncio
    async def test_execute_is_us_holiday_returns_no(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute("is_us_holiday", {"date": "2024-03-15"})

            assert "No" in result
            assert "not a US public holiday" in result

    @pytest.mark.asyncio
    async def test_execute_list_us_holidays(self, tool, sample_holidays_response):
        mock_response = MagicMock()
        mock_response.json.return_value = sample_holidays_response
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await tool.execute("list_us_holidays", {"year": 2024})

            assert "2024" in result
            assert "New Year's Day" in result
            assert "Independence Day" in result
            assert "Christmas Day" in result

    @pytest.mark.asyncio
    async def test_execute_raises_on_unknown_function(self, tool):
        with pytest.raises(ValueError, match="Unknown function"):
            await tool.execute("unknown_function", {})
