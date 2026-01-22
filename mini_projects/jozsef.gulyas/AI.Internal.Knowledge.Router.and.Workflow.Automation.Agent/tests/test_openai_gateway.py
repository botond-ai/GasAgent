import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.infrastructure.openai_gateway import OpenAIGateway


@pytest.fixture
def gateway():
    return OpenAIGateway(
        api_key="test-api-key",
        completion_model="gpt-4o-mini",
        embedding_model="text-embedding-3-small"
    )


class TestOpenAIGatewayInit:
    def test_init_sets_api_key(self, gateway):
        assert gateway.api_key == "test-api-key"

    def test_init_sets_completion_model(self, gateway):
        assert gateway.completion_model == "gpt-4o-mini"

    def test_init_sets_embedding_model(self, gateway):
        assert gateway.model == "text-embedding-3-small"

    def test_init_sets_headers(self, gateway):
        assert gateway.headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-api-key",
        }


class TestGetCompletionResponse:
    @pytest.mark.asyncio
    async def test_returns_completion_content(self, gateway):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "  Hello, world!  "}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await gateway.get_completion_response([{"role": "user", "content": "Hi"}])

            assert result == "Hello, world!"
            mock_client.post.assert_called_once_with(
                "https://api.openai.com/v1/chat/completions",
                headers=gateway.headers,
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Hi"}],
                    "temperature": 0.2,
                }
            )

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self, gateway):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Error", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await gateway.get_completion_response([{"role": "user", "content": "Hi"}])

class TestGetEmbedding:
    @pytest.mark.asyncio
    async def test_returns_embedding_vector(self, gateway):
        expected_embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": expected_embedding}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await gateway.get_embedding("Hello world")

            assert result == expected_embedding
            mock_client.post.assert_called_once_with(
                "https://api.openai.com/v1/embeddings",
                headers=gateway.headers,
                json={
                    "input": "Hello world",
                    "model": "text-embedding-3-small"
                }
            )


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_returns_classified_domain(self, gateway):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "  HR  "}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await gateway.classify_intent("How do I request vacation?")

            assert result == "hr"

    @pytest.mark.asyncio
    async def test_prompt_contains_all_domains(self, gateway):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "general"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client

            await gateway.classify_intent("Random query")

            call_args = mock_client.post.call_args
            messages = call_args.kwargs["json"]["messages"]
            prompt = messages[0]["content"]

            assert "hr" in prompt
            assert "it" in prompt
            assert "finance" in prompt
            assert "legal" in prompt
            assert "marketing" in prompt
            assert "general" in prompt
