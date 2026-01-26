from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from config.settings import DEFAULT_SEARCH_MODE, DEFAULT_VECTOR_WEIGHT, DEFAULT_KEYWORD_WEIGHT


class SearchMode(str, Enum):
    """Search mode for RAG retrieval."""
    VECTOR = "vector"      # Pure semantic search (embeddings only)
    KEYWORD = "keyword"    # Pure lexical search (BM25-like full-text)
    HYBRID = "hybrid"      # Combination of vector + keyword with RRF fusion


class UserContextRequest(BaseModel):
    """User context for chat requests (groups authentication/authorization fields)."""
    tenant_id: int = Field(..., description="ID of the tenant")
    user_id: int = Field(..., description="ID of the user sending the message")


class UnifiedChatRequest(BaseModel):
    """Request for unified chat endpoint (agent-based routing: CHAT | RAG | LIST | LTM)."""
    query: str = Field(..., min_length=1, description="User's question")
    user_context: UserContextRequest = Field(..., description="User authentication context")
    session_id: Optional[str] = Field(None, description="Session ID (auto-generated if not provided)")
    search_mode: SearchMode = Field(SearchMode(DEFAULT_SEARCH_MODE), description="Search mode: vector, keyword, or hybrid (default: hybrid)")
    vector_weight: float = Field(DEFAULT_VECTOR_WEIGHT, ge=0.0, le=1.0, description="Vector search weight for hybrid mode (default: 0.7)")
    keyword_weight: float = Field(DEFAULT_KEYWORD_WEIGHT, ge=0.0, le=1.0, description="Keyword search weight for hybrid mode (default: 0.3)")
    enable_query_rewrite: Optional[bool] = Field(None, description="Override query rewrite feature flag for A/B testing (None=use config default)")


class ConsolidateSessionRequest(BaseModel):
    """Request for session memory consolidation (STM → LTM)."""
    user_context: UserContextRequest = Field(..., description="User authentication context")



class DocumentSource(BaseModel):
    """Source reference (document or long-term memory)."""
    id: Optional[int] = Field(None, description="Document ID (if type=document)")
    title: Optional[str] = Field(None, description="Document title (if type=document)")
    type: str = Field("document", description="Source type: 'document' or 'long_term_memory'")
    content: Optional[str] = Field(None, description="Memory content (if type=long_term_memory)")
    ltm_id: Optional[int] = Field(None, description="Long-term memory ID (if type=long_term_memory)")


class RAGParams(BaseModel):
    """RAG search parameters used for retrieval."""
    top_k: int = Field(..., description="Number of top results retrieved")
    min_score_threshold: float = Field(..., description="Minimum similarity score threshold")


class RAGChatResponse(BaseModel):
    """Response from unified chat endpoint (supports CHAT | RAG | LIST | LTM modes)."""
    answer: str = Field(..., description="Generated answer from workflow")
    sources: List[DocumentSource] = Field(..., description="List of source documents with titles")
    error: Optional[str] = Field(None, description="Error message if any")
    session_id: str = Field(..., description="Session ID for the conversation")
    prompt_details: Optional[Dict[str, Any]] = Field(None, description="Debug info: prompt structure sent to LLM")
    rag_params: Optional[RAGParams] = Field(None, description="RAG parameters used (only when RAG was triggered)")
    llm_cache_info: Optional[Dict[str, Any]] = Field(None, description="LLM cache metrics for the request")


# ALIAS for consistency with KA_CHAT naming
UnifiedChatResponse = RAGChatResponse


class MessageResponse(BaseModel):
    message_id: int
    session_id: str
    user_id: int
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: str


class UnifiedChatResponse(BaseModel):
    """Response from unified chat endpoint (supports CHAT | RAG | LIST | LTM modes)."""
    answer: str = Field(..., description="Generated answer from workflow")
    sources: List[DocumentSource] = Field(..., description="List of source documents with titles")
    error: Optional[str] = Field(None, description="Error message if any")
    session_id: str = Field(..., description="Session ID for the conversation")
    execution_id: Optional[str] = Field(None, description="Workflow execution ID for debugging")
    prompt_details: Optional[Dict[str, Any]] = Field(None, description="Debug info: prompt structure sent to LLM")
    rag_params: Optional[RAGParams] = Field(None, description="RAG parameters used (only when RAG was triggered)")
    llm_cache_info: Optional[Dict[str, Any]] = Field(None, description="LLM cache metrics for the request")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")


class UserUpdateRequest(BaseModel):
    """Request for updating user data."""
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    nickname: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    default_lang: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class TenantUpdateRequest(BaseModel):
    """Request for updating tenant data."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[Dict[str, Any]] = None


# ============================================================================
# P0.17 - Cache Control Schemas
# ============================================================================

class MemoryCacheStats(BaseModel):
    """In-memory cache statistics (Tier 1)."""
    enabled: bool = Field(..., description="Whether memory cache is enabled")
    size: int = Field(..., description="Number of cached entries")
    keys: List[str] = Field(..., description="List of cache keys")
    ttl_seconds: int = Field(..., description="Time-to-live in seconds")
    debug_mode: bool = Field(False, description="Whether cache debug mode is enabled")


class DBCacheStats(BaseModel):
    """PostgreSQL cache statistics (Tier 2)."""
    enabled: bool = Field(..., description="Whether DB cache is enabled")
    cached_users: int = Field(..., description="Number of users with cached prompts")
    total_entries: int = Field(..., description="Total number of cache entries")
    error: Optional[str] = Field(None, description="Error message if stats unavailable")


class CacheConfig(BaseModel):
    """Cache configuration flags from system.ini."""
    memory_enabled: bool = Field(..., description="ENABLE_MEMORY_CACHE")
    db_enabled: bool = Field(..., description="ENABLE_DB_CACHE")
    browser_enabled: bool = Field(..., description="ENABLE_BROWSER_CACHE")
    llm_enabled: bool = Field(..., description="ENABLE_LLM_CACHE")


class CacheStatsResponse(BaseModel):
    """Comprehensive cache statistics for all layers."""
    memory_cache: MemoryCacheStats = Field(..., description="In-memory cache stats")
    db_cache: DBCacheStats = Field(..., description="PostgreSQL cache stats")
    config: CacheConfig = Field(..., description="Current cache configuration")
    timestamp: str = Field(..., description="ISO timestamp of stats collection")


class CacheInvalidateResponse(BaseModel):
    """Response from cache invalidation operations."""
    user_id: Optional[int] = Field(None, description="User ID that was invalidated")
    tenant_id: Optional[int] = Field(None, description="Tenant ID that was invalidated")
    memory_cleared: int = Field(0, description="Number of memory cache entries cleared")
    db_cleared: int = Field(0, description="Number of DB cache entries cleared")
    users_affected: Optional[int] = Field(None, description="Number of users affected (tenant invalidation)")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class CacheClearResponse(BaseModel):
    """Response from clear all caches operation."""
    memory_cleared: bool = Field(..., description="Whether memory cache was cleared")
    db_cleared: int = Field(..., description="Number of DB cache entries cleared")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class DevModeResponse(BaseModel):
    """Development mode configuration from system.ini."""
    dev_mode: bool = Field(..., description="Whether development mode is enabled (disables all caches)")
