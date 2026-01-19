"""
RAG-related Pydantic models for document processing and retrieval.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Document(BaseModel):
    """A document in the knowledge base."""

    doc_id: str = Field(
        description="Unique document identifier (e.g., KB-001)"
    )
    title: str = Field(
        description="Document title"
    )
    content: str = Field(
        description="Full document content"
    )
    doc_type: Literal["aszf", "faq", "user_guide", "policy", "other"] = Field(
        description="Type of document"
    )
    language: str = Field(
        default="hu",
        description="Original language of the document"
    )
    url: Optional[str] = Field(
        default=None,
        description="URL or path to the original document"
    )
    version: str = Field(
        default="1.0",
        description="Document version"
    )


class Chunk(BaseModel):
    """A chunk of a document for vector storage."""

    chunk_id: str = Field(
        description="Unique chunk identifier"
    )
    doc_id: str = Field(
        description="Parent document ID"
    )
    content_hu: str = Field(
        description="Original Hungarian content"
    )
    content_en: str = Field(
        description="Translated English content (for embedding)"
    )
    title: str = Field(
        description="Document or section title"
    )
    doc_type: str = Field(
        description="Type of the parent document"
    )
    chunk_index: int = Field(
        description="Index of this chunk within the document"
    )
    start_char: int = Field(
        description="Start character position in original document"
    )
    end_char: int = Field(
        description="End character position in original document"
    )
    token_count: int = Field(
        description="Number of tokens in this chunk"
    )
    url: Optional[str] = Field(
        default=None,
        description="URL to the section if available"
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Extracted keywords for BM25 search"
    )


class SearchResult(BaseModel):
    """A search result from the vector store."""

    chunk_id: str
    doc_id: str
    content_hu: str
    content_en: str
    title: str
    doc_type: str
    score: float = Field(
        ge=0.0, le=1.0,
        description="Relevance score"
    )
    url: Optional[str] = None
    search_type: Literal["vector", "bm25", "hybrid"] = "hybrid"


class RerankedResult(BaseModel):
    """A reranked search result."""

    chunk_id: str
    doc_id: str
    content_hu: str
    title: str
    original_score: float
    reranked_score: float
    reasoning: Optional[str] = Field(
        default=None,
        description="Why this result is relevant"
    )


class ExpandedQuery(BaseModel):
    """Expanded search queries for better retrieval."""

    original: str = Field(
        description="Original user query"
    )
    expanded: list[str] = Field(
        description="List of expanded/reformulated queries"
    )
    language: str = Field(
        default="hu",
        description="Original query language"
    )
    translated: str = Field(
        description="English translation for embedding search"
    )


class DocumentUpload(BaseModel):
    """Request model for document upload."""

    content: str = Field(
        description="Document content (markdown or plain text)"
    )
    title: str = Field(
        description="Document title"
    )
    doc_type: Literal["aszf", "faq", "user_guide", "policy", "other"] = Field(
        description="Type of document"
    )
    language: str = Field(
        default="hu",
        description="Document language"
    )


class DocumentInfo(BaseModel):
    """Information about an indexed document."""

    doc_id: str
    title: str
    doc_type: str
    language: str
    chunks_count: int
    indexed_at: str
    status: Literal["indexed", "pending", "error"] = "indexed"
