"""Knowledge Router Tools - LangChain Tool implementations for Tool Execution Layer.

These tools encapsulate external API calls and database operations,
following SOLID principles for clean separation of concerns.

Tools:
- GenerateEmbeddingTool: Embedding generation via EmbeddingService (Pydantic-validated)
- SearchVectorsTool: Vector search via Qdrant (Pydantic-validated)
- SearchFulltextTool: Fulltext search via PostgreSQL
- ListDocumentsTool: Document listing via PostgreSQL
- StoreMemoryTool: User fact storage in long-term memory with embedding

Architecture: Layer 3 (Tool Execution Layer)
"""

import logging
from typing import Optional, Type, List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from services.embedding_service import EmbeddingService, GenerateEmbeddingRequest
from services.qdrant_service import QdrantService, SearchDocumentChunksRequest
from services.hybrid_search_service import HybridSearchService
from database.document_chunk_repository import DocumentChunkRepository

logger = logging.getLogger(__name__)


# ===== TOOL INPUT SCHEMAS =====

class GenerateEmbeddingInput(BaseModel):
    """Input schema for GenerateEmbeddingTool."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=8000,
        description="The text query to generate embedding for (max 8000 chars for OpenAI)"
    )


class SearchVectorsInput(BaseModel):
    """Input schema for SearchVectorsTool."""
    query_embedding: List[float] = Field(
        ...,
        min_length=1,
        description="The query embedding vector (must match embedding dimensions)"
    )
    tenant_id: int = Field(..., ge=1, description="Tenant ID for filtering (must be positive)")
    user_id: int = Field(..., ge=1, description="User ID for access control (must be positive)")
    limit: int = Field(default=5, ge=1, le=100, description="Maximum number of results to return (1-100)")


class SearchFulltextInput(BaseModel):
    """Input schema for SearchFulltextTool."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The search query text (1-500 chars)"
    )
    tenant_id: int = Field(..., ge=1, description="Tenant ID for filtering (must be positive)")
    user_id: int = Field(..., ge=1, description="User ID for access control (must be positive)")
    limit: int = Field(default=5, ge=1, le=100, description="Maximum number of results to return (1-100)")


class SearchHybridInput(BaseModel):
    """Input schema for SearchHybridTool - combines vector and keyword search."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="The search query text"
    )
    tenant_id: int = Field(..., ge=1, description="Tenant ID for filtering")
    user_id: int = Field(..., ge=1, description="User ID for access control")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results (1-100)")


class ListDocumentsInput(BaseModel):
    """Input schema for ListDocumentsTool."""
    tenant_id: int = Field(..., ge=1, description="Tenant ID for filtering (must be positive)")
    user_id: int = Field(..., ge=1, description="User ID for access control (must be positive)")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of documents to list (1-100)")


class StoreMemoryInput(BaseModel):
    """Input schema for StoreMemoryTool (LLM provides fact, workflow injects context)."""
    fact: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="The fact to store in long-term memory (e.g. 'My dog is named Teddy, born in September 2025')"
    )
    # Context fields: LLM should NOT provide these (workflow will inject them)
    # But we need them in schema so ToolNode passes them to _run()
    tenant_id: Optional[int] = Field(None, description="[AUTO-INJECTED] Tenant ID (do not provide)")
    user_id: Optional[int] = Field(None, description="[AUTO-INJECTED] User ID (do not provide)")
    session_id: Optional[str] = Field(None, description="[AUTO-INJECTED] Session ID (do not provide)")


class WeatherInput(BaseModel):
    """Input schema for WeatherTool."""
    city: Optional[str] = Field(None, description="City name (e.g., 'Budapest', 'Paris', 'New York')")
    lat: Optional[float] = Field(None, description="Latitude coordinate (alternative to city)")
    lon: Optional[float] = Field(None, description="Longitude coordinate (alternative to city)")
    days: Optional[int] = Field(2, description="Number of forecast days (max 16). Use 16 for precipitation analysis.")
    include_precipitation: Optional[bool] = Field(False, description="Include daily forecast data (min/max temps, precipitation). Set True for detailed daily temperature lists or precipitation analysis.")


class CurrencyInput(BaseModel):
    """Input schema for CurrencyTool."""
    base: str = Field(..., description="Base currency code (e.g., 'EUR', 'USD', 'HUF')")
    target: str = Field(..., description="Target currency code (e.g., 'HUF', 'USD', 'EUR')")
    date: Optional[str] = Field(None, description="Historical date in YYYY-MM-DD format (optional, defaults to latest)")
    date_range: Optional[str] = Field(
        None, 
        description="Date range for multi-day data in 'START_DATE..END_DATE' format (e.g., '2026-01-01..2026-01-31'). Use for daily breakdown requests."
    )


# ===== TOOL IMPLEMENTATIONS =====

class GenerateEmbeddingTool(BaseTool):
    """
    Tool for generating embeddings via EmbeddingService.
    
    Layer 3: Tool Execution Layer
    Responsibility: External API call to embedding service
    
    Dependencies injected via constructor (DI pattern).
    """
    name: str = "generate_embedding"
    description: str = "Generate an embedding vector for the given query text using the embedding service."
    args_schema: Type[BaseModel] = GenerateEmbeddingInput
    
    # Service dependency (constructor injected, no default_factory)
    embedding_service: EmbeddingService
    
    def _run(self, query: str) -> List[float]:
        """
        Generate embedding synchronously.
        
        Args:
            query: Text to generate embedding for
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            logger.info(f"[TOOL: generate_embedding] Generating embedding for query: {query[:50]}...")
            
            # Create Pydantic request
            request = GenerateEmbeddingRequest(query=query)
            embedding = self.embedding_service.generate_embedding(request)
            
            logger.info(f"[TOOL: generate_embedding] Generated {len(embedding)} dimensions")
            return embedding
        
        except Exception as e:
            logger.error(f"[TOOL: generate_embedding] Failed: {e}", exc_info=True)
            raise
    
    async def _arun(self, query: str) -> List[float]:
        """Async version (delegates to sync for now)."""
        return self._run(query)


class SearchVectorsTool(BaseTool):
    """
    Tool for vector search via Qdrant.
    
    Layer 3: Tool Execution Layer
    Responsibility: External API call to vector database
    
    Dependencies injected via constructor (DI pattern).
    """
    name: str = "search_vectors"
    description: str = (
        "🔍 PRIMARY SEARCH METHOD - Use for ALL document content questions. "
        "Semantic vector search finds relevant information even if exact keywords don't match. "
        "ALWAYS prefer this over search_fulltext for better results."
    )
    args_schema: Type[BaseModel] = SearchVectorsInput
    
    # Service dependency (constructor injected, no default_factory)
    qdrant_service: QdrantService
    
    def _run(
        self,
        query_embedding: List[float],
        tenant_id: int,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search vectors synchronously.
        
        Args:
            query_embedding: Query vector
            tenant_id: Tenant ID for filtering
            user_id: User ID for access control
            limit: Maximum results
            
        Returns:
            List of search results with chunk_id, document_id, score
        """
        try:
            logger.info(f"[TOOL: search_vectors] Searching with tenant_id={tenant_id}, user_id={user_id}, limit={limit}")
            
            # Create Pydantic request
            request = SearchDocumentChunksRequest(
                query_vector=query_embedding,
                tenant_id=tenant_id,
                user_id=user_id,
                limit=limit
            )
            results = self.qdrant_service.search_document_chunks(request)
            
            logger.info(f"[TOOL: search_vectors] Found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"[TOOL: search_vectors] Failed: {e}", exc_info=True)
            raise
    
    async def _arun(
        self,
        query_embedding: List[float],
        tenant_id: int,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Async version (delegates to sync for now)."""
        return self._run(query_embedding, tenant_id, user_id, limit)


class SearchFulltextTool(BaseTool):
    """
    Tool for fulltext search via PostgreSQL.
    
    Layer 3: Tool Execution Layer
    Responsibility: Database query operation
    
    Dependencies injected via constructor (DI pattern).
    """
    name: str = "search_fulltext"
    description: str = (
        "⚠️ FALLBACK ONLY - PostgreSQL keyword search. "
        "Use ONLY when search_vectors returns no results. "
        "Prefer search_vectors for better semantic matching."
    )
    args_schema: Type[BaseModel] = SearchFulltextInput
    
    # Service dependency (constructor injected, no default_factory)
    chunk_repo: DocumentChunkRepository
    
    def _run(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search fulltext synchronously.
        
        Args:
            query: Search query text
            tenant_id: Tenant ID for filtering
            user_id: User ID for access control
            limit: Maximum results
            
        Returns:
            List of chunk dictionaries with chunk_id, document_id, content, rank
        """
        try:
            logger.info(f"[TOOL: search_fulltext] Searching '{query}' with tenant_id={tenant_id}, user_id={user_id}")
            results = self.chunk_repo.search_fulltext(query, tenant_id, limit)
            logger.info(f"[TOOL: search_fulltext] Found {len(results)} results")
            return results
        
        except Exception as e:
            logger.error(f"[TOOL: search_fulltext] Failed: {e}", exc_info=True)
            raise
    
    async def _arun(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Async version (delegates to sync for now)."""
        return self._run(query, tenant_id, user_id, limit)


class SearchHybridTool(BaseTool):
    """
    Tool for hybrid search combining vector and keyword search.
    
    Layer 3: Tool Execution Layer
    Responsibility: LangChain interface adapter + embedding generation orchestration
    
    SOLID Compliance:
    - Single Responsibility: Tool = LLM interface adapter (delegates to services)
    - Dependency Inversion: Depends on service abstractions (embedding + hybrid search)
    
    Dependencies injected via constructor (DI pattern).
    Generates query embedding internally to simplify LLM usage (1 call instead of 2).
    """
    name: str = "search_hybrid"
    description: str = (
        "🎯 BEST SEARCH METHOD - Combines semantic (vector) and keyword search. "
        "Use for ALL document content questions for most comprehensive results. "
        "Automatically generates query embedding and weights both search types (70% semantic, 30% keyword). "
        "Single call replaces: generate_embedding → search_vectors/search_fulltext."
    )
    args_schema: Type[BaseModel] = SearchHybridInput
    
    # Service dependencies (constructor injected)
    embedding_service: Any  # EmbeddingService (avoid circular import)
    hybrid_search_service: HybridSearchService
    
    def _run(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute hybrid search synchronously.
        
        Args:
            query: Query text for both keyword and semantic search
            tenant_id: Tenant ID for filtering
            user_id: User ID for access control
            limit: Maximum results
            
        Returns:
            List of merged and ranked search results
        """
        try:
            logger.info(
                f"[TOOL: search_hybrid] Query: '{query[:50]}...', "
                f"tenant_id={tenant_id}, user_id={user_id}, limit={limit}"
            )
            
            # Step 1: Generate embedding (delegate to embedding service)
            logger.info(f"[TOOL: search_hybrid] Generating embedding for query")
            query_embedding = self.embedding_service.generate_embedding(query)
            logger.info(f"[TOOL: search_hybrid] Generated {len(query_embedding)}-dim embedding")
            
            # Step 2: Execute hybrid search (delegate to hybrid search service)
            results = self.hybrid_search_service.search(
                query=query,
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                user_id=user_id,
                limit=limit
            )
            
            logger.info(f"[TOOL: search_hybrid] Returned {len(results)} merged results")
            return results
        
        except Exception as e:
            logger.error(f"[TOOL: search_hybrid] Failed: {e}", exc_info=True)
            raise
    
    
    async def _arun(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Async version (delegates to sync for now)."""
        return self._run(query, tenant_id, user_id, limit)


class ListDocumentsTool(BaseTool):
    """
    Tool for listing documents from PostgreSQL.
    
    Layer 3: Tool Execution Layer
    Responsibility: Database query operation
    """
    name: str = "list_documents"
    description: str = "List available documents for a tenant from the database."
    args_schema: Type[BaseModel] = ListDocumentsInput
    
    def _run(
        self,
        tenant_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List documents synchronously.
        
        Args:
            tenant_id: Tenant ID for filtering
            user_id: User ID for access control
            limit: Maximum number of documents
            
        Returns:
            List of document dictionaries with id, title, filename, upload_date
        """
        try:
            from database.pg_init import get_documents_by_tenant
            
            logger.info(f"[TOOL: list_documents] Listing docs for tenant_id={tenant_id}, user_id={user_id}, limit={limit}")
            documents = get_documents_by_tenant(tenant_id, limit)
            logger.info(f"[TOOL: list_documents] Found {len(documents)} documents")
            
            # Format results
            return [
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "filename": doc.get("filename"),
                    "upload_date": doc.get("upload_date").isoformat() if doc.get("upload_date") else None,
                    "chunk_count": doc.get("chunk_count", 0)
                }
                for doc in documents
            ]
        
        except Exception as e:
            logger.error(f"[TOOL: list_documents] Failed: {e}", exc_info=True)
            raise
    
    async def _arun(
        self,
        tenant_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Async version (delegates to sync for now)."""
        return self._run(tenant_id, user_id, limit)


class StoreMemoryTool(BaseTool):
    """
    Tool for storing user facts in long-term memory.
    
    WORKFLOW_REFACTOR_PLAN Step 3: State accessor pattern (SOLID DIP compliance)
    
    Workflow:
    1. Store fact in PostgreSQL (long_term_memories table, memory_type='explicit_fact')
    2. Generate embedding for the fact (via EmbeddingService)
    3. Store embedding in Qdrant (k_r__document_chunks collection, source_type='memory')
    4. Update PostgreSQL with qdrant_point_id
    
    Layer 3: Tool Execution Layer
    Responsibility: Long-term memory persistence with embedding
    
    Use cases:
    - User says: "jegyezd meg: kutyám neve Teddy"
    - User says: "remember that I prefer morning meetings"
    """
    name: str = "store_memory"
    description: str = (
        "🚨 MANDATORY TOOL FOR MEMORY REQUESTS 🚨\n\n"
        "USE THIS TOOL when user explicitly asks you to remember/store/note something.\n\n"
        "TRIGGER PHRASES (Hungarian): 'jegyezd meg', 'emlékezz', 'tárold el', 'mentsd el', 'ne felejtsd'\n"
        "TRIGGER PHRASES (English): 'remember', 'remember this', 'note that', 'keep in mind', 'store', 'save this fact', 'don't forget'\n\n"
        "EXAMPLES:\n"
        "- User: 'jegyezd meg: van egy uszkár kutyám' → CALL THIS TOOL with fact='van egy uszkár kutyám'\n"
        "- User: 'remember that my dog is named Teddy' → CALL THIS TOOL with fact='my dog is named Teddy'\n"
        "- User: 'note that I prefer morning meetings' → CALL THIS TOOL with fact='I prefer morning meetings'\n\n"
        "⚠️ DO NOT answer with plain text when user says 'jegyezd meg' - you MUST call this tool!"
    )
    args_schema: Type[BaseModel] = StoreMemoryInput
    
    # Service dependencies (constructor injected)
    embedding_service: EmbeddingService
    qdrant_service: QdrantService
    
    # WORKFLOW_REFACTOR_PLAN Step 3: State accessor for DI pattern 
    # Replaces manual context injection with clean architecture
    state_accessor: Optional[Any] = None  # Pydantic field declaration
    
    def __init__(self, state_accessor=None, embedding_service=None, qdrant_service=None):
        """
        Initialize with state accessor (Dependency Injection).
        
        Args:
            state_accessor: Callable that returns current ChatState
            embedding_service: Optional EmbeddingService instance
            qdrant_service: Optional QdrantService instance
        """
        # Initialize services if not provided
        if not embedding_service:
            embedding_service = EmbeddingService()
        if not qdrant_service:
            qdrant_service = QdrantService()
        
        # Initialize Pydantic base class with required fields FIRST
        super().__init__(
            embedding_service=embedding_service,
            qdrant_service=qdrant_service,
            state_accessor=state_accessor  # Pass to Pydantic constructor
        )
    
    def _run(
        self,
        fact: str,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store fact in long-term memory with embedding.
        
        WORKFLOW_REFACTOR_PLAN Step 3: Auto-context resolution from state.
        
        Args:
            fact: The fact to store
            tenant_id: Optional override (auto-filled from state if not provided)
            user_id: Optional override (auto-filled from state if not provided)
            session_id: Optional override (auto-filled from state if not provided)
            
        Returns:
            {
                "success": True,
                "memory_id": 123,
                "fact": "...",
                "embedded": True
            }
        """
        import uuid
        from database.pg_init import insert_long_term_memory
        
        try:
            # WORKFLOW_REFACTOR_PLAN Step 3: Auto-fill context from state if missing
            if tenant_id is None or user_id is None or session_id is None:
                if self.state_accessor is None:
                    raise RuntimeError("No state accessor provided and context parameters missing")
                
                state = self.state_accessor()  # Get current state
                user_ctx = state.get("user_context", {})
                
                tenant_id = tenant_id or user_ctx.get("tenant_id")
                user_id = user_id or user_ctx.get("user_id")
                session_id = session_id or state.get("session_id")
            
            # Validate required fields
            if not all([tenant_id, user_id, session_id]):
                return {
                    "success": False,
                    "error": "Cannot store memory - missing tenant/user/session context",
                    "message": "❌ Context resolution failed"
                }
            
            logger.info(f"[TOOL: store_memory] Storing fact for user_id={user_id}: '{fact[:50]}...'")
            
            # Step 1: Insert into PostgreSQL
            memory_id = insert_long_term_memory(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                content=fact,
                memory_type='explicit_fact'
            )
            
            logger.info(f"[TOOL: store_memory] PostgreSQL insert OK: memory_id={memory_id}")
            
            # Step 2: Generate embedding
            embedding_vector = self.embedding_service.generate_embedding(
                GenerateEmbeddingRequest(query=fact)
            )
            
            if not embedding_vector or len(embedding_vector) == 0:
                logger.warning(f"[TOOL: store_memory] Embedding generation failed, storing without vector")
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "fact": fact,
                    "embedded": False,
                    "message": "Fact stored but embedding failed"
                }
            
            logger.info(f"[TOOL: store_memory] Embedding generated: {len(embedding_vector)} dims")
            
            # Step 3: Store in Qdrant (returns list of {memory_id, qdrant_point_id})
            results = self.qdrant_service.upsert_memories([{
                "memory_id": memory_id,
                "embedding": embedding_vector,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "content": fact,
                "memory_type": "explicit_fact",
                "session_id": session_id
            }])
            
            point_id = results[0]["qdrant_point_id"] if results else None
            
            if not point_id:
                logger.warning(f"[TOOL: store_memory] Qdrant returned no point_id")
                return {
                    "success": True,
                    "memory_id": memory_id,
                    "fact": fact,
                    "embedded": False,
                    "message": "Fact stored but Qdrant embedding failed"
                }
            
            logger.info(f"[TOOL: store_memory] Qdrant insert OK: point_id={point_id}")
            
            # Step 4: Update PostgreSQL with qdrant_point_id
            from database.pg_connection import get_db_connection
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        UPDATE long_term_memories
                        SET qdrant_point_id = %s, embedded_at = NOW()
                        WHERE id = %s
                    """, (point_id, memory_id))
                    conn.commit()
            
            logger.info(f"[TOOL: store_memory] ✅ Memory stored and embedded successfully: memory_id={memory_id}")
            
            return {
                "success": True,
                "memory_id": memory_id,
                "fact": fact,
                "embedded": True,
                "message": "Fact successfully stored in long-term memory"
            }
        
        except Exception as e:
            logger.error(f"[TOOL: store_memory] Failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to store memory"
            }
    
    async def _arun(
        self,
        fact: str,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Async version (delegates to sync for now)."""
        return self._run(fact, tenant_id, user_id, session_id)


class WeatherTool(BaseTool):
    """
    Tool for fetching weather forecasts via External API Service.
    
    Layer 3: Tool Execution Layer
    Responsibility: External Weather API call with retry logic
    
    HW 07-08: External API integration with Pydantic validation.
    """
    name: str = "get_weather"
    description: str = (
        "Get weather forecast for a city or coordinates. "
        "Use when user asks about weather, temperature, rain, or precipitation. "
        "IMPORTANT: Maximum forecast range is 16 days due to free API limitations. "
        "For detailed daily data (min/max temperatures, precipitation patterns), set include_precipitation=True. "
        "For precipitation analysis or multi-day temperature lists, set include_precipitation=True and days=16. "
        "If user asks for more than 16 days, inform them of this limitation. "
        "Provide either city name OR coordinates (lat/lon)."
    )
    args_schema: Type[BaseModel] = WeatherInput
    
    # Dependency injection
    api_service: Any = None  # ExternalAPIService instance
    
    def _run(
        self,
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        days: Optional[int] = 2,
        include_precipitation: Optional[bool] = False
    ) -> str:
        """
        Sync wrapper (LangChain compatibility).
        
        Returns:
            JSON string with weather data or error message
        """
        import asyncio
        import json
        
        # Check for days > 16 and provide explicit feedback
        if days and days > 16:
            return json.dumps({
                "success": False,
                "error": f"Weather forecast limited to 16 days maximum (requested: {days} days). Free weather APIs only provide 16-day forecasts. Please request 16 days or fewer.",
                "max_days_available": 16
            }, ensure_ascii=False)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self.api_service.get_forecast_extended(
                    city=city, lat=lat, lon=lon, 
                    days=days, include_precipitation=include_precipitation
                )
            )
        finally:
            loop.close()
        
        # Format response for LLM
        if response.success:
            result = {
                "success": True,
                "location": response.location,
                "current_temperature": response.current_temperature,
                "tomorrow": response.tomorrow_summary
            }
            
            # Add precipitation analysis if requested
            if include_precipitation and response.low_precipitation_days:
                result["low_precipitation_days"] = response.low_precipitation_days[:10]  # Top 10
                result["daily_forecast"] = response.daily_forecast
            
            logger.info(f"✅ Weather tool success: {city or (lat, lon)}")
        else:
            result = {
                "success": False,
                "error": response.error
            }
            logger.warning(f"⚠️ Weather tool error: {response.error}")
        
        return json.dumps(result, ensure_ascii=False)
    
    async def _arun(
        self,
        city: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        days: Optional[int] = 2,
        include_precipitation: Optional[bool] = False
    ) -> str:
        """Async version."""
        import json
        
        # Check for days > 16 and provide explicit feedback
        if days and days > 16:
            return json.dumps({
                "success": False,
                "error": f"Weather forecast limited to 16 days maximum (requested: {days} days). Free weather APIs only provide 16-day forecasts. Please request 16 days or fewer.",
                "max_days_available": 16
            }, ensure_ascii=False)
        
        response = await self.api_service.get_forecast_extended(
            city=city, lat=lat, lon=lon, 
            days=days, include_precipitation=include_precipitation
        )
        
        if response.success:
            result = {
                "success": True,
                "location": response.location,
                "current_temperature": response.current_temperature,
                "tomorrow": response.tomorrow_summary
            }
            
            # Add precipitation analysis if requested
            if include_precipitation and response.low_precipitation_days:
                result["low_precipitation_days"] = response.low_precipitation_days[:10]  # Top 10
                result["daily_forecast"] = response.daily_forecast
            
            logger.info(f"✅ Weather tool success: {city or (lat, lon)}")
        else:
            result = {
                "success": False,
                "error": response.error
            }
            logger.warning(f"⚠️ Weather tool error: {response.error}")
        
        return json.dumps(result, ensure_ascii=False)


class CurrencyTool(BaseTool):
    """
    Tool for fetching currency exchange rates via External API Service.
    
    Layer 3: Tool Execution Layer
    Responsibility: External Currency API call with retry logic
    
    HW 07-08: External API integration with Pydantic validation.
    """
    name: str = "get_currency_rate"
    description: str = (
        "Get current or historical exchange rate between two currencies. "
        "Use when user asks about currency conversion, exchange rates, FX, or daily breakdown of rates. "
        "Supports all major world currencies (EUR, USD, HUF, GBP, etc.). "
        "Keywords: árfolyam, exchange rate, currency, valuta, deviza, naponta, daily, listázva (in currency context), "
        "historical, visszamenőleg, time series, multi-day."
    )
    args_schema: Type[BaseModel] = CurrencyInput
    
    # Dependency injection
    api_service: Any = None  # ExternalAPIService instance
    
    def _run(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
        date_range: Optional[str] = None
    ) -> str:
        """
        Sync wrapper (LangChain compatibility).
        
        Returns:
            JSON string with exchange rate data or error message
        """
        import asyncio
        import json
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(
                self.api_service.get_currency_rate(
                    base=base, target=target, date=date, date_range=date_range
                )
            )
        finally:
            loop.close()
        
        # Format response for LLM
        if response.success:
            result = {
                "success": True,
                "base": response.base,
                "target": response.target
            }
            
            # Multi-day response
            if response.rates_by_date:
                result["rates_by_date"] = response.rates_by_date
                result["date_range"] = date_range
                
                # Add statistical analysis if available
                if response.statistics:
                    result["statistics"] = {
                        "min": response.statistics.min,
                        "max": response.statistics.max,
                        "avg": response.statistics.avg,
                        "median": response.statistics.median,
                        "std_dev": response.statistics.std_dev,
                        "trend_direction": response.statistics.trend_direction,
                        "trend_strength": response.statistics.trend_strength,
                        "change_percent": response.statistics.change_percent,
                        "volatility": response.statistics.volatility,
                        "moving_avg_7d": response.statistics.moving_avg_7d,
                        "moving_avg_30d": response.statistics.moving_avg_30d,
                        "data_points": response.statistics.data_points
                    }
                
                logger.info(
                    f"✅ Currency tool success (multi-day): {base}/{target} - "
                    f"{len(response.rates_by_date)} days"
                )
            # Single-day response
            else:
                result["rate"] = response.rate
                result["date"] = response.date
                logger.info(f"✅ Currency tool success: {base}/{target} = {response.rate}")
        else:
            result = {
                "success": False,
                "error": response.error
            }
            logger.warning(f"⚠️ Currency tool error: {response.error}")
        
        return json.dumps(result, ensure_ascii=False)
    
    async def _arun(
        self,
        base: str,
        target: str,
        date: Optional[str] = None,
        date_range: Optional[str] = None
    ) -> str:
        """Async version."""
        import json
        
        response = await self.api_service.get_currency_rate(
            base=base, target=target, date=date, date_range=date_range
        )
        
        if response.success:
            result = {
                "success": True,
                "base": response.base,
                "target": response.target
            }
            
            # Multi-day response
            if response.rates_by_date:
                result["rates_by_date"] = response.rates_by_date
                result["date_range"] = date_range
                
                # Add statistical analysis if available
                if response.statistics:
                    result["statistics"] = {
                        "min": response.statistics.min,
                        "max": response.statistics.max,
                        "avg": response.statistics.avg,
                        "median": response.statistics.median,
                        "std_dev": response.statistics.std_dev,
                        "trend_direction": response.statistics.trend_direction,
                        "trend_strength": response.statistics.trend_strength,
                        "change_percent": response.statistics.change_percent,
                        "volatility": response.statistics.volatility,
                        "moving_avg_7d": response.statistics.moving_avg_7d,
                        "moving_avg_30d": response.statistics.moving_avg_30d,
                        "data_points": response.statistics.data_points
                    }
                
                logger.info(
                    f"✅ Currency tool success (multi-day): {base}/{target} - "
                    f"{len(response.rates_by_date)} days"
                )
            # Single-day response
            else:
                result["rate"] = response.rate
                result["date"] = response.date
                logger.info(f"✅ Currency tool success: {base}/{target} = {response.rate}")
        else:
            result = {
                "success": False,
                "error": response.error
            }
            logger.warning(f"⚠️ Currency tool error: {response.error}")
        
        return json.dumps(result, ensure_ascii=False)


# ===== TOOL FACTORY =====

def create_knowledge_tools(state_accessor=None) -> List[BaseTool]:
    """
    Factory function to create all knowledge router tools with DI.
    
    WORKFLOW_REFACTOR_PLAN Step 3: State accessor injection for SOLID compliance.
    
    Uses dependency injection container to provide singleton services,
    ensuring proper resource pooling and connection reuse.
    
    Args:
        state_accessor: Callable that returns current ChatState (WORKFLOW_REFACTOR_PLAN Step 3)
    
    Tools:
    - RAG tools: generate_embedding, search_vectors, search_fulltext, list_documents
    - Memory tools: store_memory (with state accessor)
    - External API tools: get_weather, get_currency_rate
    
    Benefits:
    - Singleton service instances (connection pooling)
    - Consistent configuration across tools
    - Testability via dependency injection
    - SOLID compliance (DIP: tools depend on abstract state accessor)
    
    Returns:
        List of instantiated tool objects with injected dependencies
    """
    from core.dependencies import (
        get_embedding_service,
        get_qdrant_service,
        get_document_chunk_repository,
        get_document_repository
    )
    from services.external_api_service import ExternalAPIService
    
    # Initialize services
    api_service = ExternalAPIService()
    hybrid_search_service = HybridSearchService(
        qdrant_service=get_qdrant_service(),
        chunk_repo=get_document_chunk_repository(),
        document_repo=get_document_repository()
    )
    
    # Inject singleton services from DI container
    tools = [
        # RAG Tools
        GenerateEmbeddingTool(embedding_service=get_embedding_service()),
        # SearchVectorsTool(qdrant_service=get_qdrant_service()),  # DISABLED: LLM generates fake embeddings
        SearchFulltextTool(chunk_repo=get_document_chunk_repository()),
        SearchHybridTool(
            embedding_service=get_embedding_service(),
            hybrid_search_service=hybrid_search_service
        ),  # NEW: Hybrid search with embedding generation
        ListDocumentsTool(),
        # Memory Tools (WORKFLOW_REFACTOR_PLAN Step 3: State accessor pattern)
        StoreMemoryTool(
            state_accessor=state_accessor,
            embedding_service=get_embedding_service(),
            qdrant_service=get_qdrant_service()
        ),
        # External API Tools (HW 07-08)
        WeatherTool(api_service=api_service),
        CurrencyTool(api_service=api_service)
    ]
    
    logger.info(f"✅ Created {len(tools)} knowledge tools with DI: {[t.name for t in tools]}")
    return tools
