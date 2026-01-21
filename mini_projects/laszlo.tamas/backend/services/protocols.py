"""
Protocol interfaces for Dependency Injection.

Defines abstract interfaces for all services and repositories,
enabling loose coupling, testability, and implementation swapping.
"""

from typing import Protocol, List, Dict, Optional, Literal, TypedDict
from datetime import datetime


# ===== TYPED DICT DEFINITIONS =====

class DocumentDict(TypedDict, total=False):
    """Strictly typed document structure."""
    id: int
    tenant_id: int
    user_id: Optional[int]
    visibility: Literal["private", "tenant"]
    source: str
    title: str
    content: str
    created_at: datetime


class DocumentChunkDict(TypedDict, total=False):
    """Strictly typed document chunk structure."""
    id: int
    tenant_id: int
    document_id: int
    chunk_index: int
    start_offset: int
    end_offset: int
    content: str
    source_title: Optional[str]
    qdrant_point_id: Optional[str]
    created_at: datetime


class QdrantSearchResultDict(TypedDict):
    """Qdrant search result structure."""
    chunk_id: int
    document_id: int
    content: str
    score: float
    metadata: Dict


# ===== REPOSITORY PROTOCOLS =====

class IDocumentRepository(Protocol):
    """Protocol for document database operations."""
    
    def insert_document(
        self,
        tenant_id: int,
        user_id: int,
        visibility: Literal["private", "tenant"],
        source: str,
        title: str,
        content: str
    ) -> int:
        """
        Insert a new document and return its ID.
        
        Raises:
            psycopg2.Error: If database operation fails
            ValueError: If validation constraints are violated
        """
        ...
    
    def get_document_by_id(self, document_id: int) -> Optional[DocumentDict]:
        """
        Retrieve a document by ID.
        
        Raises:
            psycopg2.Error: If database query fails
        """
        ...


class IDocumentChunkRepository(Protocol):
    """Protocol for document chunk database operations."""
    
    def insert_chunks(
        self,
        tenant_id: int,
        document_id: int,
        chunks: List[dict]
    ) -> List[int]:
        """
        Insert multiple chunks and return their IDs.
        
        Raises:
            psycopg2.Error: If database insert fails
            KeyError: If required chunk dictionary keys are missing
        """
        ...
    
    def get_chunks_by_document(self, document_id: int) -> List[DocumentChunkDict]:
        """
        Retrieve all chunks for a document.
        
        Raises:
            psycopg2.Error: If database query fails
        """
        ...
    
    def update_qdrant_point_id(self, chunk_id: int, qdrant_point_id: str) -> None:
        """
        Update Qdrant point ID for a chunk.
        
        Raises:
            psycopg2.Error: If database update fails
        """
        ...
    
    def get_chunk_by_id(self, chunk_id: int) -> Optional[DocumentChunkDict]:
        """
        Retrieve a chunk by ID.
        
        Raises:
            psycopg2.Error: If database query fails
        """
        ...


# ===== SERVICE PROTOCOLS =====

class IConfigService(Protocol):
    """Protocol for configuration management."""
    
    def get(self, section: str, key: str, default: str = "") -> str: ...
    def get_int(self, section: str, key: str, default: int = 0) -> int: ...
    def get_float(self, section: str, key: str, default: float = 0.0) -> float: ...
    def get_bool(self, section: str, key: str, default: bool = False) -> bool: ...
    
    # RAG settings
    def get_chunking_strategy(self) -> str: ...
    def get_chunk_size_tokens(self) -> int: ...
    def get_chunk_overlap_tokens(self) -> int: ...
    def get_embedding_model(self) -> str: ...
    def get_embedding_dimensions(self) -> int: ...
    def get_embedding_batch_size(self) -> int: ...
    def get_top_k_documents(self) -> int: ...
    def get_min_score_threshold(self) -> float: ...
    def get_qdrant_upload_batch_size(self) -> int: ...
    
    # LLM settings
    def get_chat_model(self) -> str: ...


class IEmbeddingService(Protocol):
    """Protocol for embedding generation."""
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Raises:
            openai.OpenAIError: If API call fails
            ValueError: If text is empty or invalid
        """
        ...
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.
        
        Raises:
            openai.OpenAIError: If API call fails
            ValueError: If texts list is empty or contains invalid items
        """
        ...


class IQdrantService(Protocol):
    """Protocol for Qdrant vector database operations."""
    
    def upsert_document_chunks(
        self,
        chunks: List[Dict],
        batch_size: int = 50
    ) -> List[Dict]:
        """Insert or update document chunks in Qdrant."""
        ...
    
    def search_document_chunks(
        self,
        query_vector: List[float],
        tenant_id: int,
        user_id: int,
        limit: Optional[int] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Search for similar document chunks with access control."""
        ...
    
    def upsert_long_term_memory(
        self,
        memory_id: int,
        embedding: List[float],
        tenant_id: int,
        user_id: int,
        content: str,
        memory_type: str
    ) -> str:
        """Store a long-term memory in Qdrant."""
        ...
    
    def search_long_term_memories(
        self,
        query_vector: List[float],
        tenant_id: int,
        user_id: int,
        limit: Optional[int] = None,
        score_threshold: Optional[float] = None
    ) -> List[Dict]:
        """Search for similar long-term memories."""
        ...


class IChunkingService(Protocol):
    """Protocol for document chunking operations."""
    
    def chunk_document(
        self,
        document_id: int,
        tenant_id: int,
        content: str,
        source_title: str
    ) -> List[int]:
        """
        Split document into chunks and store in database.
        
        Raises:
            ValueError: If content is empty or invalid
            psycopg2.Error: If database insert fails
        """
        ...
    
    def get_document_chunks(self, document_id: int) -> List[DocumentChunkDict]:
        """
        Retrieve all chunks for a document.
        
        Raises:
            psycopg2.Error: If database query fails
        """
        ...


class IDocumentService(Protocol):
    """Protocol for document upload and processing."""
    
    async def upload_document(
        self,
        filename: str,
        content: bytes,
        file_type: str,
        tenant_id: int,
        user_id: int,
        visibility: Literal["private", "tenant"]
    ) -> int:
        """
        Process uploaded document and store in database.
        
        Raises:
            ValueError: If document is empty or file type is unsupported
            psycopg2.Error: If database insert fails
            PyPDF2.PdfReadError: If PDF parsing fails
        """
        ...
