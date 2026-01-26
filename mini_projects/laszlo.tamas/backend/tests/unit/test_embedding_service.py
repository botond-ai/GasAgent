"""
Unit Test: Embedding Service
Knowledge Router PROD

Tests EmbeddingService functionality:
- Single embedding generation
- Batch embedding generation
- Error handling (rate limit, auth, connection)
- Retry behavior
- Pydantic validation

Priority: HIGH (embeddings are core RAG functionality)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from openai import RateLimitError, AuthenticationError, APIConnectionError, APIError
from services.embedding_service import (
    EmbeddingService,
    GenerateEmbeddingRequest,
    GenerateEmbeddingsBatchRequest
)
from services.exceptions import EmbeddingServiceError


@pytest.mark.unit
class TestGenerateEmbeddingRequest:
    """Test Pydantic request validation."""
    
    def test_valid_request(self):
        """Test valid request is accepted."""
        request = GenerateEmbeddingRequest(query="Hello world")
        assert request.query == "Hello world"
    
    def test_empty_query_rejected(self):
        """Test empty query is rejected."""
        with pytest.raises(ValueError):
            GenerateEmbeddingRequest(query="")
    
    def test_too_long_query_rejected(self):
        """Test query exceeding max length is rejected."""
        with pytest.raises(ValueError):
            GenerateEmbeddingRequest(query="x" * 8001)
    
    def test_max_length_query_accepted(self):
        """Test query at max length is accepted."""
        request = GenerateEmbeddingRequest(query="x" * 8000)
        assert len(request.query) == 8000


@pytest.mark.unit
class TestGenerateEmbeddingsBatchRequest:
    """Test batch request validation."""
    
    def test_valid_batch_request(self):
        """Test valid batch request."""
        request = GenerateEmbeddingsBatchRequest(texts=["text1", "text2", "text3"])
        assert request.text_count == 3
    
    def test_empty_batch_rejected(self):
        """Test empty batch is rejected."""
        with pytest.raises(ValueError):
            GenerateEmbeddingsBatchRequest(texts=[])
    
    def test_batch_over_100_rejected(self):
        """Test batch over 100 items is rejected."""
        with pytest.raises(ValueError):
            GenerateEmbeddingsBatchRequest(texts=["text"] * 101)


@pytest.mark.unit
class TestEmbeddingService:
    """Test EmbeddingService functionality."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        client = Mock()
        
        # Mock successful response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 3072)]
        client.embeddings.create.return_value = mock_response
        
        return client
    
    @pytest.fixture
    def embedding_service(self, mock_openai_client):
        """Create EmbeddingService with mocked dependencies."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('services.config_service.get_config_service') as mock_config:
                mock_config.return_value.get_openai_timeout.return_value = 30
                mock_config.return_value.get_embedding_model.return_value = 'text-embedding-3-large'
                mock_config.return_value.get_embedding_batch_size.return_value = 100
                mock_config.return_value.get_embedding_dimensions.return_value = 3072
                
                with patch('services.embedding_service.OpenAI') as MockOpenAI:
                    MockOpenAI.return_value = mock_openai_client
                    service = EmbeddingService()
                    yield service  # Use yield to keep context manager open
    
    # ========================================================================
    # SINGLE EMBEDDING GENERATION
    # ========================================================================
    
    def test_generate_embedding_success(self, embedding_service, mock_openai_client):
        """Test successful embedding generation."""
        result = embedding_service.generate_embedding("Test query")
        
        assert result is not None
        assert len(result) == 3072
        mock_openai_client.embeddings.create.assert_called_once()
    
    def test_generate_embedding_with_pydantic_request(self, embedding_service, mock_openai_client):
        """Test embedding generation with Pydantic request."""
        request = GenerateEmbeddingRequest(query="Test query")
        
        result = embedding_service.generate_embedding(request)
        
        assert result is not None
        assert len(result) == 3072
    
    def test_generate_embedding_with_string(self, embedding_service, mock_openai_client):
        """Test embedding generation with raw string."""
        result = embedding_service.generate_embedding("Raw string query")
        
        assert result is not None
        mock_openai_client.embeddings.create.assert_called_with(
            model='text-embedding-3-large',
            input="Raw string query",
            encoding_format="float"
        )
    
    # ========================================================================
    # ERROR HANDLING
    # ========================================================================
    
    def test_rate_limit_error_wrapped(self, embedding_service, mock_openai_client):
        """Test RateLimitError is wrapped in EmbeddingServiceError."""
        # Create proper RateLimitError
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {}
        error = RateLimitError(
            message="Rate limit exceeded",
            response=mock_response,
            body={"error": {"message": "Rate limit exceeded"}}
        )
        mock_openai_client.embeddings.create.side_effect = error
        
        with pytest.raises(EmbeddingServiceError) as exc_info:
            embedding_service.generate_embedding("test")
        
        assert "rate limit" in str(exc_info.value).lower()
        assert exc_info.value.context["error_type"] == "RateLimitError"
    
    def test_auth_error_wrapped(self, embedding_service, mock_openai_client):
        """Test AuthenticationError is wrapped in EmbeddingServiceError."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.headers = {}
        error = AuthenticationError(
            message="Invalid API key",
            response=mock_response,
            body={"error": {"message": "Invalid API key"}}
        )
        mock_openai_client.embeddings.create.side_effect = error
        
        with pytest.raises(EmbeddingServiceError) as exc_info:
            embedding_service.generate_embedding("test")
        
        assert "authentication" in str(exc_info.value).lower()
        assert exc_info.value.context["error_type"] == "AuthenticationError"
    
    def test_connection_error_wrapped(self, embedding_service, mock_openai_client):
        """Test APIConnectionError is wrapped in EmbeddingServiceError."""
        error = APIConnectionError(request=Mock())
        mock_openai_client.embeddings.create.side_effect = error
        
        with pytest.raises(EmbeddingServiceError) as exc_info:
            embedding_service.generate_embedding("test")
        
        assert "connection" in str(exc_info.value).lower()
        assert exc_info.value.context["error_type"] == "APIConnectionError"
    
    # ========================================================================
    # INITIALIZATION
    # ========================================================================
    
    def test_init_without_api_key_raises(self):
        """Test initialization without API key raises ValueError."""
        with patch.dict('os.environ', {}, clear=True):
            # Remove OPENAI_API_KEY
            import os
            os.environ.pop('OPENAI_API_KEY', None)
            
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                EmbeddingService()


@pytest.mark.unit
class TestEmbeddingServiceBatch:
    """Test batch embedding functionality."""
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client for batch operations."""
        client = Mock()
        
        # Dynamic mock that returns correct number of embeddings based on input
        def create_embeddings(**kwargs):
            texts = kwargs.get('input', [])
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[0.1 * (i + 1)] * 3072) for i in range(len(texts))
            ]
            return mock_response
        
        client.embeddings.create.side_effect = create_embeddings
        
        return client
    
    @pytest.fixture
    def embedding_service(self, mock_openai_client):
        """Create EmbeddingService for batch tests."""
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            with patch('services.config_service.get_config_service') as mock_config:
                mock_config.return_value.get_openai_timeout.return_value = 30
                mock_config.return_value.get_embedding_model.return_value = 'text-embedding-3-large'
                mock_config.return_value.get_embedding_batch_size.return_value = 2  # Small batch for testing
                mock_config.return_value.get_embedding_dimensions.return_value = 3072
                
                with patch('services.embedding_service.OpenAI') as MockOpenAI:
                    MockOpenAI.return_value = mock_openai_client
                    service = EmbeddingService()
                    yield service  # Use yield to keep context manager open
    
    def test_generate_embeddings_batch(self, embedding_service, mock_openai_client):
        """Test batch embedding generation."""
        from services.embedding_service import GenerateEmbeddingsBatchRequest
        # batch_size is 2, so use 2 texts to fit in one batch
        request = GenerateEmbeddingsBatchRequest(texts=["text1", "text2"])
        
        result = embedding_service.generate_embeddings_batch(request)
        
        assert result is not None
        assert len(result) == 2
        for embedding in result:
            assert len(embedding) == 3072
    
    def test_generate_embeddings_with_pydantic_request(self, embedding_service, mock_openai_client):
        """Test batch embedding with Pydantic request."""
        request = GenerateEmbeddingsBatchRequest(texts=["a", "b"])  # Max 2 due to batch_size=2
        
        result = embedding_service.generate_embeddings_batch(request)
        
        assert len(result) == 2
    
    def test_generate_embeddings_batch_size_exceeded(self, embedding_service, mock_openai_client):
        """Test batch exceeding batch_size raises ValueError."""
        # batch_size is 2, so 3 texts should fail
        request = GenerateEmbeddingsBatchRequest(texts=["t1", "t2", "t3"])
        
        with pytest.raises(ValueError, match="exceeds maximum"):
            embedding_service.generate_embeddings_batch(request)
