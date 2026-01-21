"""Embedding generation service using OpenAI with Pydantic validation."""

import logging
import os
from typing import List, Dict, Union, overload
from pydantic import BaseModel, Field
from openai import OpenAI, APIError, APIConnectionError, RateLimitError, AuthenticationError
import httpx

from services.exceptions import EmbeddingServiceError
from services.resilience import retry_on_transient_error

logger = logging.getLogger(__name__)


# ===== REQUEST SCHEMAS =====

class GenerateEmbeddingRequest(BaseModel):
    """Request schema for single embedding generation."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="Input query text to embed (1-8000 chars for OpenAI)"
    )


class GenerateEmbeddingsBatchRequest(BaseModel):
    """Request schema for batch embedding generation."""
    texts: List[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of texts to embed (1-100 items)"
    )
    
    @property
    def text_count(self) -> int:
        """Get number of texts."""
        return len(self.texts)


# ===== SERVICE =====

class EmbeddingService:
    """Service for generating embeddings using OpenAI."""
    
    def __init__(self):
        from .config_service import get_config_service
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        # Load from system.ini
        config = get_config_service()
        timeout_seconds = config.get_openai_timeout()
        
        # Configure timeout with httpx.Timeout
        timeout = httpx.Timeout(
            timeout_seconds,  # Total timeout
            connect=10.0  # Connection timeout (fixed)
        )
        
        self.client = OpenAI(api_key=api_key, timeout=timeout)
        self.model = config.get_embedding_model()  # Now reads from OPENAI_MODEL_EMBEDDING env
        self.batch_size = config.get_embedding_batch_size()
        self.dimensions = config.get_embedding_dimensions()
        
        logger.info(
            f"EmbeddingService initialized: model={self.model}, "
            f"batch_size={self.batch_size}, dimensions={self.dimensions}, "
            f"timeout={timeout_seconds}s"
        )
    
    @overload
    def generate_embedding(self, request: GenerateEmbeddingRequest) -> List[float]: ...
    
    @overload  
    def generate_embedding(self, request: str) -> List[float]: ...

    @retry_on_transient_error(max_retries=3, initial_backoff=1.0, backoff_multiplier=2.0)
    def generate_embedding(self, request: Union[GenerateEmbeddingRequest, str]) -> List[float]:
        """
        Generate embedding for a single text (Pydantic-validated or raw string).
        
        Args:
            request: Validated embedding request OR raw text string
        
        Returns:
            Embedding vector as list of floats (3072 dimensions)
        
        Raises:
            EmbeddingServiceError: If OpenAI API call fails
        """
        # Handle both string and Pydantic request types
        if isinstance(request, str):
            text = request
        else:
            text = request.query
            
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float"
            )
            
            embedding = response.data[0].embedding
            
            logger.debug(f"Generated embedding: {len(embedding)} dimensions")
            
            return embedding
        
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}", exc_info=True)
            raise EmbeddingServiceError(
                "OpenAI rate limit exceeded",
                context={
                    "model": self.model,
                    "text_length": len(text),
                    "retry_after": getattr(e, 'retry_after', None),
                    "error_type": "RateLimitError"
                }
            ) from e
        
        except AuthenticationError as e:
            logger.error(f"OpenAI authentication failed: {e}", exc_info=True)
            raise EmbeddingServiceError(
                "OpenAI authentication failed - check API key",
                context={
                    "model": self.model,
                    "error_type": "AuthenticationError"
                }
            ) from e
        
        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {e}", exc_info=True)
            raise EmbeddingServiceError(
                "OpenAI connection error",
                context={
                    "model": self.model,
                    "text_length": len(text),
                    "error_type": "APIConnectionError"
                }
            ) from e
        
        except APIError as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise EmbeddingServiceError(
                f"OpenAI API error: {str(e)}",
                context={
                    "model": self.model,
                    "text_length": len(text),
                    "error_type": type(e).__name__
                }
            ) from e
        
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}", exc_info=True)
            raise EmbeddingServiceError(
                f"Embedding generation failed: {str(e)}",
                context={
                    "model": self.model,
                    "text_length": len(text),
                    "error_type": type(e).__name__
                }
            ) from e
    
    @retry_on_transient_error(max_retries=3, initial_backoff=1.0, backoff_multiplier=2.0)
    def generate_embeddings_batch(self, request: GenerateEmbeddingsBatchRequest) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single API call (Pydantic-validated).
        
        Args:
            request: Validated batch embedding request
        
        Returns:
            List of embedding vectors
        
        Raises:
            ValueError: If texts list is too large
            EmbeddingServiceError: If OpenAI API call fails
        """
        if request.text_count > self.batch_size:
            raise ValueError(
                f"Batch size {request.text_count} exceeds maximum {self.batch_size}"
            )
        
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=request.texts,
                encoding_format="float"
            )
            
            embeddings = [data.embedding for data in response.data]
            
            logger.info(
                f"Generated {len(embeddings)} embeddings in batch "
                f"({len(embeddings[0])} dimensions each)"
            )
            
            return embeddings
        
        except RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}", exc_info=True)
            raise EmbeddingServiceError(
                "OpenAI rate limit exceeded",
                context={
                    "model": self.model,
                    "batch_size": request.text_count,
                    "retry_after": getattr(e, 'retry_after', None),
                    "error_type": "RateLimitError"
                }
            ) from e
        
        except AuthenticationError as e:
            logger.error(f"OpenAI authentication failed: {e}", exc_info=True)
            raise EmbeddingServiceError(
                "OpenAI authentication failed - check API key",
                context={
                    "model": self.model,
                    "error_type": "AuthenticationError"
                }
            ) from e
        
        except APIConnectionError as e:
            logger.error(f"OpenAI connection error: {e}", exc_info=True)
            raise EmbeddingServiceError(
                "OpenAI connection error",
                context={
                    "model": self.model,
                    "batch_size": request.text_count,
                    "error_type": "APIConnectionError"
                }
            ) from e
        
        except APIError as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise EmbeddingServiceError(
                f"OpenAI API error: {str(e)}",
                context={
                    "model": self.model,
                    "batch_size": request.text_count,
                    "error_type": type(e).__name__
                }
            ) from e
        
        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}", exc_info=True)
            raise EmbeddingServiceError(
                f"Batch embedding generation failed: {str(e)}",
                context={
                    "model": self.model,
                    "batch_size": request.text_count,
                    "error_type": type(e).__name__
                }
            ) from e
    
    def generate_embeddings_for_chunks(
        self,
        chunks: List[Dict]
    ) -> List[Dict]:
        """
        Generate embeddings for document chunks with batching.
        
        Args:
            chunks: List of chunk dictionaries with 'id' and 'content' keys
        
        Returns:
            List of dicts with chunk_id and embedding
            [{"chunk_id": int, "embedding": List[float]}, ...]
        
        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        if not chunks:
            return []
        
        results = []
        total_chunks = len(chunks)
        
        logger.info(f"Generating embeddings for {total_chunks} chunks")
        
        # Process in batches
        for i in range(0, total_chunks, self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_texts = [chunk["content"] for chunk in batch]
            batch_ids = [chunk["id"] for chunk in batch]
            
            try:
                # Create Pydantic request
                request = GenerateEmbeddingsBatchRequest(texts=batch_texts)
                embeddings = self.generate_embeddings_batch(request)
                
                # Combine chunk IDs with embeddings
                for chunk_id, embedding in zip(batch_ids, embeddings):
                    results.append({
                        "chunk_id": chunk_id,
                        "embedding": embedding
                    })
                
                logger.info(
                    f"Batch {i // self.batch_size + 1}: "
                    f"Processed {len(batch)} chunks "
                    f"({len(results)}/{total_chunks} total)"
                )
            
            except EmbeddingServiceError as e:
                logger.error(
                    f"Failed to generate embeddings for batch {i // self.batch_size + 1}: {e}"
                )
                # Skip failed chunks or raise - for now, skip
                logger.warning(f"Skipping {len(batch)} chunks due to error")
                continue
        
        logger.info(
            f"Embedding generation complete: {len(results)}/{total_chunks} successful"
        )
        
        return results
