"""
Unit tests for Ollama LLM client.
Uses mocking to avoid actual API calls.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from pydantic import BaseModel

from app.llm.ollama_client import OllamaClient, OllamaError


class SampleResponse(BaseModel):
    """Sample Pydantic model for testing structured generation."""
    name: str
    value: int


class TestOllamaClient:
    """Tests for OllamaClient."""
    
    @pytest.fixture
    def mock_httpx_client(self):
        """Create a mock httpx client."""
        with patch('app.llm.ollama_client.httpx.Client') as mock:
            yield mock.return_value
    
    @pytest.fixture
    def client(self, mock_httpx_client):
        """Create an OllamaClient with mocked HTTP client."""
        return OllamaClient()
    
    def test_get_available_models(self, client, mock_httpx_client):
        """Test fetching available models."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:8b"},
                {"name": "qwen2.5:14b-instruct"},
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response
        
        models = client.get_available_models()
        
        assert len(models) == 2
        assert "llama3.1:8b" in models
        assert "qwen2.5:14b-instruct" in models
    
    def test_get_available_models_caches(self, client, mock_httpx_client):
        """Test that models are cached."""
        mock_response = Mock()
        mock_response.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response
        
        # First call
        client.get_available_models()
        # Second call (should use cache)
        client.get_available_models()
        
        # Should only make one HTTP request
        assert mock_httpx_client.get.call_count == 1
    
    def test_validate_model_available(self, client, mock_httpx_client):
        """Test validation of available model."""
        mock_response = Mock()
        mock_response.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response
        
        is_valid, fallback = client.validate_model("llama3.1:8b")
        
        assert is_valid is True
        assert fallback is None
    
    def test_validate_model_unavailable_with_fallback(self, client, mock_httpx_client):
        """Test validation suggests fallback for unavailable model."""
        mock_response = Mock()
        mock_response.json.return_value = {"models": [{"name": "llama3.1:8b"}]}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.get.return_value = mock_response
        
        is_valid, fallback = client.validate_model("gpt-oss:20b")
        
        assert is_valid is False
        # Should suggest a fallback from the available models
        assert fallback is not None
    
    def test_generate(self, client, mock_httpx_client):
        """Test basic text generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Hello, world!"}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response
        
        result = client.generate("llama3.1:8b", "Say hello")
        
        assert result == "Hello, world!"
    
    def test_generate_json(self, client, mock_httpx_client):
        """Test JSON generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"key": "value"}'}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response
        
        result = client.generate_json("llama3.1:8b", "Return JSON")
        
        assert result == {"key": "value"}
    
    def test_generate_json_extracts_from_text(self, client, mock_httpx_client):
        """Test JSON extraction from text with extra content."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": 'Here is the JSON: {"key": "value"} That was the response.'
        }
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response
        
        result = client.generate_json("llama3.1:8b", "Return JSON")
        
        assert result == {"key": "value"}
    
    def test_generate_structured(self, client, mock_httpx_client):
        """Test structured generation with Pydantic validation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": '{"name": "test", "value": 42}'}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response
        
        # Mock model validation
        client._available_models = ["llama3.1:8b"]
        
        result = client.generate_structured(
            "llama3.1:8b",
            "Generate sample",
            SampleResponse,
        )
        
        assert isinstance(result, SampleResponse)
        assert result.name == "test"
        assert result.value == 42
    
    def test_retryable_error_codes(self, client, mock_httpx_client):
        """Test that certain error codes are marked as retryable."""
        for status_code in [429, 500, 502, 503]:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_httpx_client.post.return_value = mock_response
            
            with pytest.raises(OllamaError) as exc_info:
                client.generate("llama3.1:8b", "Test")
            
            assert exc_info.value.retryable is True
            assert exc_info.value.status_code == status_code
    
    def test_embed(self, client, mock_httpx_client):
        """Test embedding generation."""
        mock_response = Mock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        mock_response.raise_for_status = Mock()
        mock_httpx_client.post.return_value = mock_response
        
        embedding = client.embed("Test text")
        
        assert len(embedding) == 3
        assert embedding[0] == 0.1


class TestOllamaError:
    """Tests for OllamaError exception."""
    
    def test_basic_error(self):
        """Test basic error creation."""
        error = OllamaError("Test error")
        
        assert str(error) == "Test error"
        assert error.status_code is None
        assert error.retryable is False
    
    def test_error_with_details(self):
        """Test error with status code and retryable flag."""
        error = OllamaError("Rate limited", status_code=429, retryable=True)
        
        assert error.status_code == 429
        assert error.retryable is True
