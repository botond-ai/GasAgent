# Chat Workflow - Knowledge Router

## Mit csinál (felhasználói nézőpont)

A chat workflow kezeli a teljes user interakciót: a query feldolgozásától a válasz generálásáig. Biztosítja a session kontinuitást, context megőrzést és a multi-tenant izolációt minden beszélgetés során.

## Használat

### Alapvető chat interakció
```python
# Új beszélgetés indítás
from services.chat_workflow_service import ChatWorkflowService
chat_service = ChatWorkflowService()

result = chat_service.process_chat_query(
    query="Mi a vállalati szabályzat a távmunkáról?",
    tenant_id=1,
    user_id=1,
    session_id=None  # Új session lesz létrehozva
)

print(f"Válasz: {result.final_answer}")
print(f"Session ID: {result.session_id}")
```

### Session folytatás
```python
# Beszélgetés folytatása
result = chat_service.process_chat_query(
    query="És mi a helyzet a rugalmas munkaidővel?",
    tenant_id=1,
    user_id=1,
    session_id=result.session_id  # Meglévő session használata
)
```

### Batch chat processing
```python
# Több query egymás után ugyanabban a session-ben
queries = [
    "Mi a szabályzat a távmunkáról?",
    "Milyen dokumentumok kellenek a kérelem benyújtásához?",
    "Ki hagytja jóvá a távmunka kérelmeket?"
]

session_id = None
for query in queries:
    result = chat_service.process_chat_query(query, 1, 1, session_id)
    session_id = result.session_id
    print(f"Q: {query}\nA: {result.final_answer}\n---")
```

## Technikai implementáció

### Chat Workflow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CHAT WORKFLOW SERVICE                        │
│                 (FastAPI → LangGraph Bridge)                    │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  INPUT VALIDATION & PREPROCESSING                               │
│  • Query sanitization and validation                           │
│  • User/tenant authorization check                             │
│  • Rate limiting enforcement                                   │
│  • Request correlation ID assignment                           │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  SESSION MANAGEMENT                                             │
│  • Create new session or resume existing                       │
│  • Load conversation history                                   │
│  • Apply session-level context                                 │
│  • Update session activity timestamp                           │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  UNIFIED CHAT WORKFLOW (LangGraph)                             │
│  • initialize → prepare_query → agent_decide → tools → finalize│
│  • Full state tracking and node execution logging             │
│  • Multi-iteration support with safety limits                 │
│  • Error recovery and graceful degradation                    │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  RESPONSE POST-PROCESSING                                       │
│  • Message persistence to database                             │
│  • Session state update                                        │
│  • Analytics and metrics logging                               │
│  • Response formatting and validation                          │
└─────────────────────────────────────────────────────────────────┘
```

### Chat Service Implementation

#### ChatWorkflowService Class
```python
class ChatWorkflowService:
    def __init__(self):
        self.workflow = UnifiedChatWorkflow()
        self.rate_limiter = RateLimiter()
        self.session_manager = SessionManager()
        self.metrics_logger = MetricsLogger()
    
    async def process_chat_query(
        self,
        query: str,
        tenant_id: int,
        user_id: int,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> ChatResponse:
        """
        Main chat processing endpoint.
        
        Args:
            query: User's question or message
            tenant_id: Tenant identifier for isolation
            user_id: User identifier
            session_id: Optional existing session ID
            request_id: Optional request correlation ID
            
        Returns:
            ChatResponse with answer, session info, and metadata
        """
        
        # Generate correlation ID
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Input validation
        await self._validate_chat_input(query, tenant_id, user_id)
        
        # Rate limiting check
        await self._check_rate_limits(tenant_id, user_id)
        
        # Session handling
        session = await self._handle_session(session_id, tenant_id, user_id)
        
        try:
            # Execute main workflow
            workflow_result = await self.workflow.run({
                "query": query,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "session_id": session.id,
                "request_id": request_id
            })
            
            # Post-process results
            response = await self._post_process_response(
                workflow_result, session, request_id
            )
            
            # Log metrics
            await self._log_chat_metrics(workflow_result, response)
            
            return response
            
        except Exception as e:
            # Error handling and recovery
            return await self._handle_chat_error(e, session, query, request_id)
```

#### Input Validation
```python
async def _validate_chat_input(self, query: str, tenant_id: int, user_id: int):
    """Comprehensive input validation for chat requests."""
    
    # Query validation
    if not query or not query.strip():
        raise ValidationError("Query cannot be empty")
    
    if len(query) > config.MAX_QUERY_LENGTH:
        raise ValidationError(f"Query too long (max: {config.MAX_QUERY_LENGTH} chars)")
    
    # Malicious content detection
    if await self._detect_malicious_content(query):
        raise SecurityError("Query contains prohibited content")
    
    # User authorization
    user = await self._load_and_validate_user(user_id, tenant_id)
    if not user.is_active:
        raise AuthorizationError("User account inactive")
    
    # Tenant authorization
    tenant = await self._load_and_validate_tenant(tenant_id)
    if not tenant.is_active:
        raise AuthorizationError("Tenant account inactive")

async def _detect_malicious_content(self, query: str) -> bool:
    """Basic malicious content detection."""
    
    # SQL injection patterns
    sql_patterns = [
        r";\s*(drop|delete|update|insert|create)\s+",
        r"union\s+select",
        r"--\s*$",
        r"/\*.*\*/"
    ]
    
    for pattern in sql_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return True
    
    # Prompt injection patterns
    prompt_injection_patterns = [
        r"ignore\s+previous\s+instructions",
        r"you\s+are\s+now\s+a\s+different\s+ai",
        r"forget\s+everything\s+above",
        r"system:\s*new\s+role"
    ]
    
    for pattern in prompt_injection_patterns:
        if re.search(pattern, query, re.IGNORECASE):
            return True
    
    return False
```

#### Session Management
```python
class SessionManager:
    def __init__(self):
        self.db = get_database_connection()
        self.cache = RedisCache()  # Optional Redis for session caching
    
    async def handle_session(
        self, 
        session_id: Optional[str], 
        tenant_id: int, 
        user_id: int
    ) -> ChatSession:
        """Create new session or resume existing one."""
        
        if session_id:
            # Try to resume existing session
            session = await self._resume_session(session_id, tenant_id, user_id)
            if session:
                return session
            else:
                log_warning(f"Session {session_id} not found or expired, creating new")
        
        # Create new session
        return await self._create_new_session(tenant_id, user_id)
    
    async def _resume_session(
        self, 
        session_id: str, 
        tenant_id: int, 
        user_id: int
    ) -> Optional[ChatSession]:
        """Resume existing session with validation."""
        
        # Load session from database
        session = await self.db.load_session(session_id)
        
        if not session:
            return None
        
        # Validate session ownership
        if session.tenant_id != tenant_id or session.user_id != user_id:
            raise SecurityError("Session access denied")
        
        # Check session expiration
        if self._is_session_expired(session):
            await self._end_session(session_id)
            return None
        
        # Update last activity
        await self._update_session_activity(session_id)
        
        return session
    
    async def _create_new_session(self, tenant_id: int, user_id: int) -> ChatSession:
        """Create new chat session."""
        
        session_id = str(uuid.uuid4())
        
        session = ChatSession(
            id=session_id,
            tenant_id=tenant_id,
            user_id=user_id,
            created_at=datetime.utcnow(),
            last_message_at=datetime.utcnow(),
            is_deleted=False,
            processed_for_ltm=False
        )
        
        await self.db.save_session(session)
        
        # Cache session for quick access
        if self.cache:
            await self.cache.set_session(session_id, session, ttl=3600)
        
        return session
    
    def _is_session_expired(self, session: ChatSession) -> bool:
        """Check if session has expired due to inactivity."""
        
        if not session.last_message_at:
            return True
        
        inactive_duration = datetime.utcnow() - session.last_message_at
        return inactive_duration.total_seconds() > config.SESSION_TIMEOUT_SECONDS
    
    async def get_conversation_history(
        self, 
        session_id: str, 
        limit: int = 20
    ) -> List[ChatMessage]:
        """Load recent conversation history for context."""
        
        messages = await self.db.load_chat_messages(
            session_id=session_id,
            limit=limit,
            order_by="created_at DESC"
        )
        
        # Reverse to get chronological order
        return list(reversed(messages))
```

#### Rate Limiting
```python
class RateLimiter:
    def __init__(self):
        self.redis = RedisConnection()
        
    async def check_rate_limits(self, tenant_id: int, user_id: int):
        """Enforce rate limiting for chat requests."""
        
        # User-level rate limiting
        user_key = f"rate_limit:user:{user_id}"
        user_requests = await self.redis.incr(user_key)
        
        if user_requests == 1:
            await self.redis.expire(user_key, 60)  # 1-minute window
        
        if user_requests > config.USER_REQUESTS_PER_MINUTE:
            raise RateLimitError(f"User rate limit exceeded: {user_requests}/min")
        
        # Tenant-level rate limiting
        tenant_key = f"rate_limit:tenant:{tenant_id}"
        tenant_requests = await self.redis.incr(tenant_key)
        
        if tenant_requests == 1:
            await self.redis.expire(tenant_key, 60)
        
        if tenant_requests > config.TENANT_REQUESTS_PER_MINUTE:
            raise RateLimitError(f"Tenant rate limit exceeded: {tenant_requests}/min")
        
        # Check for burst protection
        await self._check_burst_limits(user_id, tenant_id)
    
    async def _check_burst_limits(self, user_id: int, tenant_id: int):
        """Prevent rapid-fire requests (burst protection)."""
        
        burst_key = f"burst:user:{user_id}"
        
        # Use sliding window for burst detection
        current_time = time.time()
        window_start = current_time - config.BURST_WINDOW_SECONDS
        
        # Remove old timestamps
        await self.redis.zremrangebyscore(burst_key, 0, window_start)
        
        # Add current request timestamp
        await self.redis.zadd(burst_key, {str(current_time): current_time})
        
        # Check request count in window
        request_count = await self.redis.zcard(burst_key)
        
        if request_count > config.BURST_REQUEST_LIMIT:
            raise RateLimitError("Burst limit exceeded")
        
        # Set expiration for cleanup
        await self.redis.expire(burst_key, config.BURST_WINDOW_SECONDS)
```

### Context Management

#### Conversation Context
```python
class ConversationContext:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.message_history = []
        self.entities_mentioned = {}
        self.topics_discussed = []
        self.user_preferences = {}
    
    async def load_context(self, limit: int = 10) -> dict:
        """Load conversation context for LLM."""
        
        # Recent message history
        recent_messages = await self._load_recent_messages(limit)
        
        # Extract entities and topics
        entities = await self._extract_entities_from_history(recent_messages)
        topics = await self._extract_topics_from_history(recent_messages)
        
        # Build context summary
        context = {
            "recent_messages": recent_messages,
            "entities_mentioned": entities,
            "topics_discussed": topics,
            "session_summary": await self._generate_session_summary()
        }
        
        return context
    
    async def _generate_session_summary(self) -> Optional[str]:
        """Generate AI summary of conversation so far."""
        
        if len(self.message_history) < 4:
            return None  # Too short for meaningful summary
        
        # Use LLM to summarize conversation
        summary_prompt = f"""
        Summarize this conversation in 2-3 sentences:
        
        {self._format_messages_for_summary()}
        
        Focus on main topics, decisions made, and key information shared.
        """
        
        try:
            response = await call_openai_gpt4(
                messages=[{"role": "user", "content": summary_prompt}],
                model="gpt-4o-2024-11-20",
                temperature=0.3,
                max_tokens=200
            )
            return response.content.strip()
        except Exception as e:
            log_warning("Failed to generate session summary", error=str(e))
            return None
```

#### Multi-turn Conversation Handling
```python
def enhance_query_with_context(
    query: str, 
    conversation_history: List[ChatMessage]
) -> str:
    """Enhance query with conversation context for better understanding."""
    
    if not conversation_history:
        return query
    
    # Find references that need context
    context_indicators = [
        r"\b(ez|az|ezt|azt|erre|arra)\b",  # Hungarian demonstratives
        r"\b(this|that|it|they|them)\b",   # English pronouns
        r"\b(és|and)\b.*\?",              # Follow-up questions
        r"^(igen|nem|yes|no)\b",          # Yes/no responses
    ]
    
    needs_context = any(
        re.search(pattern, query, re.IGNORECASE) 
        for pattern in context_indicators
    )
    
    if not needs_context:
        return query
    
    # Build contextual query
    recent_context = conversation_history[-3:]  # Last 3 messages
    context_text = "\n".join([
        f"{msg.role}: {msg.content}" 
        for msg in recent_context
    ])
    
    enhanced_query = f"""
    Beszélgetés kontextus:
    {context_text}
    
    Jelenlegi kérdés: {query}
    """
    
    return enhanced_query
```

### Response Processing

#### Response Formatting
```python
class ResponseFormatter:
    def __init__(self, user_context: UserContext):
        self.user_context = user_context
        self.language = user_context.language
        self.timezone = user_context.timezone
    
    def format_final_response(
        self, 
        answer: str, 
        sources: List[Source],
        metadata: dict
    ) -> str:
        """Format complete response with citations and metadata."""
        
        # Base response
        formatted_response = self._format_answer_text(answer)
        
        # Add citations
        if sources:
            formatted_response += self._format_citations(sources)
        
        # Add helpful metadata (if relevant)
        if self._should_include_metadata(metadata):
            formatted_response += self._format_response_metadata(metadata)
        
        return formatted_response
    
    def _format_answer_text(self, answer: str) -> str:
        """Format the main answer text."""
        
        # Ensure proper markdown formatting
        answer = self._fix_markdown_formatting(answer)
        
        # Add language-specific formatting
        if self.language == "hu":
            answer = self._apply_hungarian_formatting(answer)
        
        return answer
    
    def _format_citations(self, sources: List[Source]) -> str:
        """Format source citations."""
        
        if self.language == "hu":
            citations_header = "\n\n**Források:**\n"
        else:
            citations_header = "\n\n**Sources:**\n"
        
        citation_list = []
        for i, source in enumerate(sources, 1):
            citation = self._format_single_citation(source, i)
            citation_list.append(citation)
        
        return citations_header + "\n".join(citation_list)
    
    def _format_single_citation(self, source: Source, number: int) -> str:
        """Format individual source citation."""
        
        if source.type == "document":
            citation = f"[{number}] {source.title}"
            if source.chapter:
                citation += f" - {source.chapter}"
            if source.page:
                if self.language == "hu":
                    citation += f" (oldal {source.page})"
                else:
                    citation += f" (page {source.page})"
        
        elif source.type == "memory":
            if self.language == "hu":
                citation = f"[{number}] Személyes emlék"
            else:
                citation = f"[{number}] Personal memory"
            
            if source.memory_type == "session_summary":
                if self.language == "hu":
                    citation += " (korábbi beszélgetésből)"
                else:
                    citation += " (from previous conversation)"
        
        else:
            citation = f"[{number}] {source.title or 'Unknown source'}"
        
        return citation
```

### Error Handling

#### Chat-Specific Error Handling
```python
class ChatErrorHandler:
    @staticmethod
    async def handle_chat_error(
        error: Exception,
        session: ChatSession,
        query: str,
        request_id: str
    ) -> ChatResponse:
        """Handle various chat workflow errors gracefully."""
        
        error_type = type(error).__name__
        
        # Different handling strategies by error type
        if isinstance(error, ValidationError):
            return await ChatErrorHandler._handle_validation_error(
                error, session, request_id
            )
        
        elif isinstance(error, RateLimitError):
            return await ChatErrorHandler._handle_rate_limit_error(
                error, session, request_id
            )
        
        elif isinstance(error, WorkflowTimeoutError):
            return await ChatErrorHandler._handle_timeout_error(
                error, session, query, request_id
            )
        
        elif isinstance(error, LLMError):
            return await ChatErrorHandler._handle_llm_error(
                error, session, query, request_id
            )
        
        else:
            return await ChatErrorHandler._handle_generic_error(
                error, session, query, request_id
            )
    
    @staticmethod
    async def _handle_timeout_error(
        error: WorkflowTimeoutError,
        session: ChatSession,
        query: str,
        request_id: str
    ) -> ChatResponse:
        """Handle workflow timeout with helpful message."""
        
        # Log detailed error for debugging
        log_error(
            "Chat workflow timeout",
            session_id=session.id,
            query=query,
            request_id=request_id,
            error=str(error)
        )
        
        # Generate helpful response
        if session.user_context.language == "hu":
            error_message = """
            Sajnálom, a kérés feldolgozása túl sokáig tartott. 
            Kérem próbálja újra egy egyszerűbb kérdéssel, vagy 
            vegye fel a kapcsolatot a támogatással.
            """
        else:
            error_message = """
            Sorry, your request took too long to process. 
            Please try again with a simpler question or 
            contact support for assistance.
            """
        
        return ChatResponse(
            final_answer=error_message,
            session_id=session.id,
            status="timeout_error",
            error_message=str(error),
            request_id=request_id
        )
```

### Performance Monitoring

#### Chat Workflow Metrics
```python
class ChatMetricsLogger:
    def __init__(self):
        self.prometheus = PrometheusMetrics()
        self.db_logger = DatabaseMetricsLogger()
    
    async def log_chat_metrics(
        self, 
        workflow_result: dict, 
        response: ChatResponse
    ):
        """Log comprehensive chat workflow metrics."""
        
        # Basic performance metrics
        self.prometheus.chat_request_duration.observe(
            workflow_result.get("total_execution_time_ms", 0) / 1000
        )
        
        self.prometheus.chat_requests_total.inc(
            labels={
                "tenant_id": str(workflow_result["tenant_id"]),
                "status": response.status,
                "workflow_path": workflow_result.get("workflow_path", "unknown")
            }
        )
        
        # Token usage tracking
        if "llm_tokens_used" in workflow_result:
            self.prometheus.llm_tokens_total.inc(
                workflow_result["llm_tokens_used"],
                labels={"model": workflow_result.get("llm_model_used", "unknown")}
            )
        
        # Tool usage metrics
        for tool_name in workflow_result.get("tools_executed", []):
            self.prometheus.tool_usage_total.inc(
                labels={"tool": tool_name}
            )
        
        # Response quality metrics
        if workflow_result.get("sources_cited"):
            self.prometheus.responses_with_citations.inc()
        
        # Database logging for analytics
        await self.db_logger.log_chat_execution({
            "execution_id": workflow_result["workflow_execution_id"],
            "session_id": response.session_id,
            "query_length": len(workflow_result.get("original_query", "")),
            "response_length": len(response.final_answer),
            "sources_count": len(response.sources_cited),
            "tools_used": workflow_result.get("tools_executed", []),
            "execution_time_ms": workflow_result.get("total_execution_time_ms"),
            "node_count": len(workflow_result.get("node_execution_log", [])),
            "iteration_count": workflow_result.get("iteration_count", 0),
            "confidence_score": workflow_result.get("confidence_score"),
            "timestamp": datetime.utcnow()
        })
```

## Funkció-specifikus konfiguráció

### Chat Workflow Configuration
```ini
# Query processing
MAX_QUERY_LENGTH=2000
ENABLE_QUERY_REWRITING=true
ENABLE_MALICIOUS_CONTENT_DETECTION=true

# Session management
SESSION_TIMEOUT_SECONDS=3600
MAX_SESSIONS_PER_USER=10
ENABLE_SESSION_CACHING=true

# Rate limiting
USER_REQUESTS_PER_MINUTE=30
TENANT_REQUESTS_PER_MINUTE=1000
BURST_REQUEST_LIMIT=5
BURST_WINDOW_SECONDS=10

# Response formatting
MAX_RESPONSE_LENGTH=4000
ENABLE_CITATION_FORMATTING=true
DEFAULT_CITATION_STYLE=numbered

# Error handling
ENABLE_GRACEFUL_DEGRADATION=true
MAX_ERROR_RETRIES=2
ERROR_RETRY_DELAY_SECONDS=1
```

### Multi-tenant Chat Isolation
```python
# Every chat operation enforces tenant isolation
chat_service = ChatWorkflowService()

# All database queries filtered by tenant_id
messages = await db.load_chat_messages(
    session_id=session_id,
    tenant_id=tenant_id  # Always required
)

# Vector searches filtered by tenant
rag_results = await qdrant_search(
    query_vector=embedding,
    collection="documents",
    filter={"tenant_id": tenant_id}  # Tenant isolation
)
```

### Customization per Tenant
```python
# Tenant-specific chat behavior
class TenantChatCustomization:
    @staticmethod
    def get_chat_config(tenant_id: int) -> dict:
        return {
            "response_style": "formal",      # formal/casual
            "citation_required": True,       # Always cite sources
            "language_preference": "hu",     # Default language
            "enable_memory_creation": True,  # Allow "jegyezd meg" 
            "max_response_length": 2000,     # Tenant-specific limits
            "enable_external_tools": False   # Restrict tool access
        }
```

### Advanced Session Management
```python
# Session lifecycle management
class AdvancedSessionManager:
    async def end_session_and_create_summary(self, session_id: str):
        """End session and create long-term memory summary."""
        
        session = await self.load_session(session_id)
        conversation_history = await self.get_full_conversation(session_id)
        
        # Generate session summary
        summary = await self._generate_session_summary(conversation_history)
        
        # Create long-term memory
        if summary and len(summary) > 50:
            await create_long_term_memory(
                user_id=session.user_id,
                content=summary,
                memory_type="session_summary",
                source_session_id=session_id
            )
        
        # Mark session as ended and processed
        await self.db.update_session(session_id, {
            "ended_at": datetime.utcnow(),
            "processed_for_ltm": True
        })
```