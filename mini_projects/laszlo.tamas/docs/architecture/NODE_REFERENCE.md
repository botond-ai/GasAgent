# Node Reference - Knowledge Router

## Mit csinál (felhasználói nézőpont)

Ez a dokumentum minden LangGraph workflow node teljes technikai dokumentációját tartalmazza. Minden node input/output specifikációival, konfigurációs lehetőségeivel és hibakezelési logikájával.

## Használat

### Node-specific debugging
```python
# Egyedi node tesztelése
from services.unified_chat_workflow import UnifiedChatWorkflow
workflow = UnifiedChatWorkflow()
state = {"query": "test", "user_id": 1, "tenant_id": 1}

# Node közvetlen futtatás
result = workflow.nodes["agent_decide"](state)
print(f"Decision: {result['agent_decision']}")
```

### State inspection utilities
```python
# Node execution követése
def inspect_node_execution(node_name: str, state_before: dict, state_after: dict):
    changes = {}
    for key, value in state_after.items():
        if key not in state_before or state_before[key] != value:
            changes[key] = {'before': state_before.get(key), 'after': value}
    return changes
```

## Technikai implementáció

### Node 1: initialize

**Purpose:** Initialize workflow execution with user context and session management.

#### Input State Requirements
```python
# Required fields
{
    "user_id": int,              # Valid user ID
    "tenant_id": int,            # Valid tenant ID  
    "query": str,                # User query (non-empty)
}

# Optional fields
{
    "session_id": str,           # Resume existing session (UUID)
    "request_id": str,           # HTTP request correlation
    "debug_mode": bool,          # Enable detailed logging
}
```

#### Output State Modifications
```python
{
    "user_id": int,              # Preserved from input
    "tenant_id": int,            # Preserved from input
    "session_id": str,           # Created or reused UUID
    "original_query": str,       # Exact user input
    "user_context": UserContext, # Loaded from database
    "workflow_execution_id": str,# Unique execution ID
    "started_at": float,         # Unix timestamp
    "status": "running",         # Workflow status
    "iteration_count": 0,        # Agent loop counter
    "max_iterations": int,       # Configuration limit
}
```

#### Implementation Logic
```python
def initialize_node(state: ChatState) -> ChatState:
    # Input validation
    validate_required_fields(state, ["user_id", "tenant_id", "query"])
    
    # Load user and tenant context
    user_context = load_user_context(state["user_id"], state["tenant_id"])
    if not user_context.is_active:
        raise WorkflowError("User or tenant inactive")
    
    # Session management
    if "session_id" in state and state["session_id"]:
        session = resume_session(state["session_id"])
    else:
        session = create_new_session(
            tenant_id=state["tenant_id"],
            user_id=state["user_id"]
        )
    
    # Execution tracking initialization
    execution_id = str(uuid.uuid4())
    start_workflow_tracking(
        execution_id=execution_id,
        session_id=session.id,
        query=state["query"],
        user_id=state["user_id"],
        tenant_id=state["tenant_id"]
    )
    
    # State updates
    return {
        **state,
        "session_id": session.id,
        "original_query": state["query"],
        "user_context": user_context,
        "workflow_execution_id": execution_id,
        "started_at": time.time(),
        "status": "running",
        "iteration_count": 0,
        "max_iterations": config.MAX_AGENT_ITERATIONS
    }
```

#### Error Handling
```python
# Database errors
try:
    user_context = load_user_context(user_id, tenant_id)
except DatabaseError as e:
    log_error("Failed to load user context", error=str(e))
    raise WorkflowError("Unable to initialize user session")

# Validation errors
if not query.strip():
    raise ValidationError("Query cannot be empty")
    
# Session creation failures  
try:
    session = create_new_session(tenant_id, user_id)
except SessionCreationError as e:
    # Fallback to in-memory session
    session = InMemorySession(tenant_id, user_id)
    log_warning("Using in-memory session as fallback")
```

#### Configuration
```ini
# Max concurrent sessions per user
MAX_USER_SESSIONS=10

# Session timeout (minutes)
SESSION_TIMEOUT_MINUTES=60

# Debug mode settings
ENABLE_NODE_STATE_LOGGING=false
LOG_USER_QUERIES=true
```

---

### Node 2: prepare_query

**Purpose:** Optimize and enrich user query for better processing.

#### Input State Requirements
```python
{
    "original_query": str,       # From initialize node
    "user_context": UserContext, # User preferences
    "session_id": str,           # Session for context
}
```

#### Output State Modifications
```python
{
    "query": str,                # Processed query (may be rewritten)
    "rewritten_query": str,      # LLM-optimized version (if rewritten)
    "query_intent": str,         # Classified intent (optional)
    "query_language": str,       # Detected language (hu/en)
    "query_complexity": str,     # simple/moderate/complex
    "context_enhanced": bool,    # Whether context was added
}
```

#### Implementation Logic
```python
def prepare_query_node(state: ChatState) -> ChatState:
    original_query = state["original_query"]
    user_context = state["user_context"]
    
    # Language detection
    detected_lang = detect_language(original_query)
    
    # Query complexity assessment
    complexity = assess_query_complexity(original_query)
    
    # Context enhancement from session history
    session_context = get_recent_session_context(state["session_id"], limit=3)
    
    # Query rewriting logic
    should_rewrite = (
        len(original_query.split()) < 3 or  # Too short
        complexity == "complex" or           # Complex queries need clarity
        user_context.language != detected_lang  # Language mismatch
    )
    
    if should_rewrite and config.ENABLE_QUERY_REWRITING:
        rewritten_query = rewrite_query_with_llm(
            original_query=original_query,
            user_language=user_context.language,
            session_context=session_context,
            user_preferences=user_context.preferences
        )
        final_query = rewritten_query
    else:
        rewritten_query = None
        final_query = original_query
    
    # Intent classification (if enabled)
    query_intent = None
    if config.ENABLE_INTENT_CLASSIFICATION:
        query_intent = classify_query_intent(final_query)
    
    return {
        **state,
        "query": final_query,
        "rewritten_query": rewritten_query,
        "query_intent": query_intent,
        "query_language": detected_lang,
        "query_complexity": complexity,
        "context_enhanced": bool(session_context)
    }
```

#### Query Rewriting Examples
```python
# Hungarian short queries
"szabályzat távmunka" -> "Mi a vállalati szabályzat a távmunkával kapcsolatban?"
"projekt státusz" -> "Mi a jelenlegi projekt státusza és mik a következő lépések?"

# English clarification
"budget Q2" -> "What is the Q2 budget breakdown and current spending status?"

# Context-enhanced queries
Original: "Mi a deadline?"
Context: Previous discussion about marketing campaign
Enhanced: "Mi a marketing kampány deadline-ja?"
```

#### Error Handling
```python
# LLM rewriting failures
try:
    rewritten_query = rewrite_query_with_llm(original_query)
except LLMError as e:
    log_warning("Query rewriting failed, using original", error=str(e))
    rewritten_query = None
    final_query = original_query

# Language detection failures
try:
    detected_lang = detect_language(original_query)
except LanguageDetectionError:
    detected_lang = user_context.language  # Fallback to user preference
```

---

### Node 3: agent_decide

**Purpose:** GPT-4 powered decision making for workflow routing.

#### Input State Requirements
```python
{
    "query": str,                # Prepared query
    "user_context": UserContext, # User preferences & system prompts
    "session_id": str,           # For conversation history
    "iteration_count": int,      # Current loop iteration
}
```

#### Output State Modifications
```python
{
    "agent_decision": str,       # CALL_TOOLS / ANSWER / ASK_CLARIFICATION
    "agent_reasoning": str,      # LLM explanation for decision
    "tools_to_call": List[str],  # Planned tool invocations
    "workflow_path": str,        # Current execution path
    "confidence_score": float,   # Decision confidence (0.0-1.0)
    "llm_model_used": str,       # Model identifier
    "llm_tokens_used": int,      # Token consumption
}
```

#### Implementation Logic
```python
def agent_decide_node(state: ChatState) -> ChatState:
    # Prevent infinite loops
    if state["iteration_count"] >= state["max_iterations"]:
        return {
            **state,
            "agent_decision": "ANSWER",
            "final_answer": "Sorry, I've reached the maximum number of processing steps. Please rephrase your question or contact support.",
            "status": "error",
            "error_message": "Max iterations exceeded"
        }
    
    # Build hierarchical system prompt
    system_prompt = build_agent_system_prompt(
        tenant_prompt=state["user_context"].tenant_system_prompt,
        user_prompt=state["user_context"].user_system_prompt,
        user_language=state["user_context"].language,
        user_timezone=state["user_context"].timezone,
        available_tools=get_available_tools()
    )
    
    # Get conversation context
    conversation_history = get_conversation_history(
        session_id=state["session_id"],
        limit=10
    )
    
    # Prepare LLM input
    messages = [
        {"role": "system", "content": system_prompt},
        *conversation_history,
        {"role": "user", "content": state["query"]}
    ]
    
    # LLM decision making
    try:
        response = call_openai_gpt4(
            messages=messages,
            model="gpt-4o-2024-11-20",
            temperature=0.1,  # Low temperature for consistent decisions
            max_tokens=500
        )
        
        # Parse structured decision
        decision_data = parse_agent_decision(response.content)
        
        return {
            **state,
            "agent_decision": decision_data["decision"],
            "agent_reasoning": decision_data["reasoning"],
            "tools_to_call": decision_data.get("tools", []),
            "workflow_path": f"iteration_{state['iteration_count']}_tools" if decision_data["decision"] == "CALL_TOOLS" else "direct_answer",
            "confidence_score": decision_data.get("confidence", 0.8),
            "llm_model_used": "gpt-4o-2024-11-20",
            "llm_tokens_used": response.usage.total_tokens
        }
        
    except Exception as e:
        log_error("Agent decision failed", error=str(e))
        # Fallback decision
        return {
            **state,
            "agent_decision": "ASK_CLARIFICATION",
            "agent_reasoning": "I encountered an issue processing your request. Could you please rephrase your question?",
            "error_message": str(e)
        }
```

#### System Prompt Structure
```python
def build_agent_system_prompt(tenant_prompt, user_prompt, user_language, user_timezone, available_tools):
    return f"""
# KNOWLEDGE ROUTER AGENT - DECISION FRAMEWORK

## TENANT CONTEXT
{tenant_prompt}

## USER CONTEXT  
{user_prompt}
Language: {user_language}
Timezone: {user_timezone}

## DECISION OPTIONS
You must respond with exactly one of these decisions:

**CALL_TOOLS** - Use when you need information not available in conversation context
Tools available: {', '.join(available_tools)}

**ANSWER** - Use when you can provide a complete response from available context

**ASK_CLARIFICATION** - Use when the query is ambiguous or lacks necessary details

## OUTPUT FORMAT
{{
  "decision": "CALL_TOOLS|ANSWER|ASK_CLARIFICATION",
  "reasoning": "Explain your decision in 1-2 sentences",
  "tools": ["tool1", "tool2"] // Only if CALL_TOOLS
  "confidence": 0.85 // How confident you are (0.0-1.0)
}}

## DECISION GUIDELINES
- Prefer CALL_TOOLS for factual questions requiring current data
- Use ANSWER for questions you can answer from conversation context
- Choose ASK_CLARIFICATION only when the query is genuinely ambiguous
- Always consider user's language and cultural context
- Include confidence score based on clarity of query and available context
"""
```

#### Decision Parsing
```python
def parse_agent_decision(llm_response: str) -> dict:
    try:
        # Try JSON parsing first
        decision_data = json.loads(llm_response)
        
        # Validate required fields
        if "decision" not in decision_data:
            raise ValueError("Missing 'decision' field")
            
        if decision_data["decision"] not in ["CALL_TOOLS", "ANSWER", "ASK_CLARIFICATION"]:
            raise ValueError(f"Invalid decision: {decision_data['decision']}")
            
        return decision_data
        
    except json.JSONDecodeError:
        # Fallback: extract decision from text
        if "CALL_TOOLS" in llm_response.upper():
            return {"decision": "CALL_TOOLS", "reasoning": "Extracted from text"}
        elif "ASK_CLARIFICATION" in llm_response.upper():
            return {"decision": "ASK_CLARIFICATION", "reasoning": "Extracted from text"}
        else:
            return {"decision": "ANSWER", "reasoning": "Default fallback"}
```

---

### Node 4: tools

**Purpose:** Execute selected tools and gather information.

#### Input State Requirements
```python
{
    "agent_decision": "CALL_TOOLS", # Must be CALL_TOOLS
    "tools_to_call": List[str],     # Tool names to execute
    "query": str,                   # Query for tool execution
    "user_id": int,                 # For user-specific tools
    "tenant_id": int,               # For tenant isolation
}
```

#### Output State Modifications
```python
{
    "tool_outputs": Dict[str, Any], # Results from each tool
    "rag_results": List[DocumentChunk], # RAG search results
    "memory_results": List[Memory], # Long-term memory results
    "documents_retrieved": List[Document], # Full document retrievals
    "tools_executed": List[str],    # Successfully executed tools
    "tool_errors": Dict[str, str],  # Tool execution errors
    "total_tool_time_ms": int,      # Combined tool execution time
}
```

#### Implementation Logic
```python
def tools_node(state: ChatState) -> ChatState:
    if state.get("agent_decision") != "CALL_TOOLS":
        # Should not reach here, but handle gracefully
        return state
    
    tools_to_call = state.get("tools_to_call", [])
    tool_outputs = {}
    tool_errors = {}
    tools_executed = []
    
    start_time = time.time()
    
    # Execute each requested tool
    for tool_name in tools_to_call:
        try:
            tool_result = execute_tool(
                tool_name=tool_name,
                query=state["query"],
                user_id=state["user_id"],
                tenant_id=state["tenant_id"],
                session_id=state["session_id"],
                state=state
            )
            
            tool_outputs[tool_name] = tool_result
            tools_executed.append(tool_name)
            
        except Exception as e:
            log_error(f"Tool execution failed: {tool_name}", error=str(e))
            tool_errors[tool_name] = str(e)
    
    total_time_ms = int((time.time() - start_time) * 1000)
    
    # Process and structure results
    processed_results = process_tool_results(tool_outputs)
    
    return {
        **state,
        "tool_outputs": tool_outputs,
        "rag_results": processed_results.get("rag_results", []),
        "memory_results": processed_results.get("memory_results", []),
        "documents_retrieved": processed_results.get("documents", []),
        "tools_executed": tools_executed,
        "tool_errors": tool_errors,
        "total_tool_time_ms": total_time_ms
    }
```

#### Available Tools

**1. RAG Document Search Tool**
```python
def rag_search_tool(query: str, tenant_id: int, user_id: int = None, **kwargs) -> dict:
    """
    Semantic search in tenant documents using Qdrant vector database.
    
    Args:
        query: Search query
        tenant_id: Tenant isolation
        user_id: Optional user context for personalization
        top_k: Number of results (default: 5)
        min_score: Minimum similarity threshold (default: 0.7)
        
    Returns:
        {
            "chunks": List[DocumentChunk],
            "search_time_ms": int,
            "total_results": int,
            "query_vector": List[float] // For debugging
        }
    """
    
    start_time = time.time()
    
    # Generate query embedding
    query_vector = generate_embedding(query)
    
    # Qdrant search with tenant filter
    search_results = qdrant_client.search(
        collection_name="document_chunks",
        query_vector=query_vector,
        limit=kwargs.get("top_k", 5),
        score_threshold=kwargs.get("min_score", 0.7),
        query_filter={
            "must": [
                {"key": "tenant_id", "match": {"value": tenant_id}}
            ]
        }
    )
    
    # Convert to structured format
    chunks = []
    for hit in search_results:
        chunk = DocumentChunk(
            id=hit.payload["chunk_id"],
            content=hit.payload["content"],
            source_title=hit.payload["source_title"],
            chapter_name=hit.payload.get("chapter_name"),
            page_start=hit.payload.get("page_start"),
            similarity_score=hit.score,
            tenant_id=tenant_id
        )
        chunks.append(chunk)
    
    search_time = int((time.time() - start_time) * 1000)
    
    return {
        "chunks": chunks,
        "search_time_ms": search_time,
        "total_results": len(chunks),
        "query_vector": query_vector[:5]  # First 5 dims for debugging
    }
```

**2. Long-Term Memory Search Tool**
```python
def memory_search_tool(query: str, user_id: int, **kwargs) -> dict:
    """
    Search user's long-term memories using semantic similarity.
    
    Args:
        query: Memory search query
        user_id: User-specific memory search
        memory_type: Filter by type ('explicit_fact', 'session_summary')
        top_k: Number of results (default: 3)
        
    Returns:
        {
            "memories": List[Memory],
            "search_time_ms": int,
            "total_results": int
        }
    """
    
    start_time = time.time()
    
    # Generate query embedding
    query_vector = generate_embedding(query)
    
    # Build Qdrant filter
    memory_filter = {"must": [{"key": "user_id", "match": {"value": user_id}}]}
    
    if "memory_type" in kwargs:
        memory_filter["must"].append({
            "key": "memory_type", 
            "match": {"value": kwargs["memory_type"]}
        })
    
    # Qdrant search in memories collection
    search_results = qdrant_client.search(
        collection_name="long_term_memories",
        query_vector=query_vector,
        limit=kwargs.get("top_k", 3),
        score_threshold=0.6,  # Lower threshold for memories
        query_filter=memory_filter
    )
    
    # Convert to Memory objects
    memories = []
    for hit in search_results:
        memory = Memory(
            id=hit.payload["memory_id"],
            content=hit.payload["content"],
            memory_type=hit.payload["memory_type"],
            created_at=hit.payload["created_at"],
            similarity_score=hit.score,
            user_id=user_id
        )
        memories.append(memory)
    
    search_time = int((time.time() - start_time) * 1000)
    
    return {
        "memories": memories,
        "search_time_ms": search_time,
        "total_results": len(memories)
    }
```

**3. Document Retrieval Tool**
```python
def document_retrieval_tool(document_id: int, tenant_id: int, **kwargs) -> dict:
    """
    Retrieve full document by ID with tenant isolation.
    
    Args:
        document_id: Document identifier
        tenant_id: Tenant isolation
        include_chunks: Whether to include chunk breakdown (default: False)
        
    Returns:
        {
            "document": Document,
            "chunks": List[DocumentChunk] // If include_chunks=True
        }
    """
    
    # Load document with tenant check
    document = load_document_by_id(document_id, tenant_id)
    if not document:
        raise ToolExecutionError(f"Document {document_id} not found or not accessible")
    
    result = {"document": document}
    
    # Optional chunk inclusion
    if kwargs.get("include_chunks", False):
        chunks = load_document_chunks(document_id, tenant_id)
        result["chunks"] = chunks
    
    return result
```

**4. Memory Creation Tool**
```python
def create_memory_tool(content: str, user_id: int, memory_type: str = "explicit_fact", **kwargs) -> dict:
    """
    Create new long-term memory for user.
    
    Args:
        content: Memory content text
        user_id: User to associate memory with
        memory_type: 'explicit_fact' or 'session_summary'
        source_session_id: Optional session reference
        
    Returns:
        {
            "memory_id": int,
            "created_at": str,
            "embedded": bool
        }
    """
    
    # Validate memory type
    if memory_type not in ["explicit_fact", "session_summary"]:
        raise ToolExecutionError(f"Invalid memory type: {memory_type}")
    
    # Create database entry
    memory_id = create_long_term_memory(
        user_id=user_id,
        content=content,
        memory_type=memory_type,
        source_session_id=kwargs.get("source_session_id")
    )
    
    # Generate and store embedding
    try:
        embedding = generate_embedding(content)
        qdrant_point_id = store_memory_embedding(
            memory_id=memory_id,
            content=content,
            embedding=embedding,
            user_id=user_id,
            memory_type=memory_type
        )
        embedded = True
    except Exception as e:
        log_error("Failed to create memory embedding", error=str(e))
        embedded = False
    
    return {
        "memory_id": memory_id,
        "created_at": datetime.now().isoformat(),
        "embedded": embedded
    }
```

#### Tool Execution Framework
```python
def execute_tool(tool_name: str, **kwargs) -> Any:
    """
    Generic tool execution with error handling and timing.
    """
    
    # Tool registry
    AVAILABLE_TOOLS = {
        "rag_search": rag_search_tool,
        "memory_search": memory_search_tool, 
        "document_retrieval": document_retrieval_tool,
        "create_memory": create_memory_tool,
    }
    
    if tool_name not in AVAILABLE_TOOLS:
        raise ToolExecutionError(f"Unknown tool: {tool_name}")
    
    tool_func = AVAILABLE_TOOLS[tool_name]
    
    # Execute with timeout
    try:
        with timeout(seconds=config.TOOL_EXECUTION_TIMEOUT_SEC):
            result = tool_func(**kwargs)
            
        # Log successful execution
        log_info(f"Tool executed successfully: {tool_name}")
        return result
        
    except TimeoutError:
        raise ToolExecutionError(f"Tool {tool_name} timed out after {config.TOOL_EXECUTION_TIMEOUT_SEC}s")
    except Exception as e:
        raise ToolExecutionError(f"Tool {tool_name} failed: {str(e)}")
```

---

### Node 5: finalize

**Purpose:** Generate final response with proper formatting and citations.

#### Input State Requirements
```python
{
    "query": str,                # Original processed query
    "agent_decision": str,       # ANSWER or tool results available
    "tool_outputs": Dict,        # Results from tools (if CALL_TOOLS)
    "rag_results": List,         # Structured RAG results
    "memory_results": List,      # Structured memory results
    "user_context": UserContext, # For language/formatting preferences
}
```

#### Output State Modifications
```python
{
    "final_answer": str,         # Complete formatted response
    "sources_cited": List[Source], # Citation information
    "response_language": str,    # Response language used
    "citation_count": int,       # Number of sources cited
    "response_length_chars": int,# Response length for analytics
    "confidence_score": float,   # Overall response confidence
    "status": "success",         # Workflow completion status
    "completed_at": float,       # Unix timestamp
}
```

#### Implementation Logic
```python
def finalize_node(state: ChatState) -> ChatState:
    user_context = state["user_context"]
    response_lang = user_context.language
    
    # Generate response based on workflow path
    if state.get("agent_decision") == "ASK_CLARIFICATION":
        final_answer = generate_clarification_response(
            query=state["query"],
            language=response_lang,
            reasoning=state.get("agent_reasoning", "")
        )
        sources_cited = []
        confidence_score = 0.9  # High confidence in clarification requests
        
    elif state.get("agent_decision") == "ANSWER":
        # Direct answer without tools
        final_answer = generate_direct_answer(
            query=state["query"],
            conversation_context=get_conversation_history(state["session_id"]),
            language=response_lang,
            user_context=user_context
        )
        sources_cited = []
        confidence_score = 0.7  # Lower confidence without external sources
        
    else:
        # Answer with tool results
        final_answer, sources_cited, confidence_score = generate_tool_based_response(
            query=state["query"],
            rag_results=state.get("rag_results", []),
            memory_results=state.get("memory_results", []),
            tool_outputs=state.get("tool_outputs", {}),
            language=response_lang,
            user_preferences=user_context.preferences
        )
    
    # Format final response
    formatted_response = format_response_with_citations(
        answer=final_answer,
        sources=sources_cited,
        language=response_lang,
        citation_style=user_context.preferences.get("citation_style", "numbered")
    )
    
    # Calculate completion metrics
    completion_time = time.time()
    total_execution_time = int((completion_time - state["started_at"]) * 1000)
    
    # Save final message to database
    save_chat_message(
        session_id=state["session_id"],
        user_id=state["user_id"],
        tenant_id=state["tenant_id"],
        role="assistant",
        content=formatted_response,
        metadata={
            "workflow_execution_id": state["workflow_execution_id"],
            "sources_count": len(sources_cited),
            "confidence_score": confidence_score,
            "execution_time_ms": total_execution_time,
            "tools_used": state.get("tools_executed", [])
        }
    )
    
    return {
        **state,
        "final_answer": formatted_response,
        "sources_cited": sources_cited,
        "response_language": response_lang,
        "citation_count": len(sources_cited),
        "response_length_chars": len(formatted_response),
        "confidence_score": confidence_score,
        "status": "success",
        "completed_at": completion_time,
        "total_execution_time_ms": total_execution_time
    }
```

#### Response Generation Functions

**Tool-based Response Generation:**
```python
def generate_tool_based_response(query, rag_results, memory_results, tool_outputs, language, user_preferences):
    # Combine all information sources
    all_sources = []
    source_texts = []
    
    # Process RAG results
    for chunk in rag_results:
        source_texts.append(f"[RAG] {chunk.content}")
        all_sources.append(Source(
            type="document",
            title=chunk.source_title,
            chapter=chunk.chapter_name,
            page=chunk.page_start,
            similarity_score=chunk.similarity_score
        ))
    
    # Process memory results
    for memory in memory_results:
        source_texts.append(f"[MEMORY] {memory.content}")
        all_sources.append(Source(
            type="memory",
            content=memory.content,
            memory_type=memory.memory_type,
            created_at=memory.created_at,
            similarity_score=memory.similarity_score
        ))
    
    # Generate response using LLM
    system_prompt = build_response_generation_prompt(language, user_preferences)
    
    user_prompt = f"""
    User Query: {query}
    
    Available Information:
    {chr(10).join(source_texts)}
    
    Generate a comprehensive answer using the provided information. Use proper citations.
    """
    
    try:
        response = call_openai_gpt4(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="gpt-4o-2024-11-20",
            temperature=0.3,
            max_tokens=1000
        )
        
        # Calculate confidence based on source quality and relevance
        confidence_score = calculate_response_confidence(
            query=query,
            sources=all_sources,
            response=response.content
        )
        
        return response.content, all_sources, confidence_score
        
    except Exception as e:
        log_error("Response generation failed", error=str(e))
        # Fallback response
        fallback_response = generate_fallback_response(query, language)
        return fallback_response, all_sources, 0.3
```

**Citation Formatting:**
```python
def format_response_with_citations(answer, sources, language, citation_style):
    if not sources:
        return answer
    
    if citation_style == "numbered":
        # Format: "According to the policy [1], remote work is allowed [2]."
        formatted_answer = answer
        
        # Add source list
        if language == "hu":
            sources_header = "\n\n**Források:**\n"
        else:
            sources_header = "\n\n**Sources:**\n"
            
        source_list = []
        for i, source in enumerate(sources, 1):
            if source.type == "document":
                citation = f"[{i}] {source.title}"
                if source.chapter:
                    citation += f" - {source.chapter}"
                if source.page:
                    citation += f" (oldal {source.page})"
            elif source.type == "memory":
                citation = f"[{i}] Személyes emlék ({source.memory_type})"
            
            source_list.append(citation)
        
        return formatted_answer + sources_header + "\n".join(source_list)
    
    elif citation_style == "inline":
        # Format: "According to the HR Manual (page 5), remote work..."
        return format_inline_citations(answer, sources, language)
    
    else:
        # Default numbered style
        return format_response_with_citations(answer, sources, language, "numbered")
```

---

### Routing Logic

#### Conditional Node Routing
```python
def should_continue_to_tools(state: ChatState) -> str:
    """
    Routing function determining next node after agent_decide.
    """
    agent_decision = state.get("agent_decision")
    
    if agent_decision == "CALL_TOOLS":
        return "tools"
    elif agent_decision == "ANSWER":
        return "finalize"  
    elif agent_decision == "ASK_CLARIFICATION":
        return "finalize"
    else:
        # Fallback for malformed decisions
        log_warning(f"Unknown agent decision: {agent_decision}")
        return "finalize"

def should_continue_after_tools(state: ChatState) -> str:
    """
    Routing after tools execution - either loop back to agent or finalize.
    """
    # Check if we have sufficient results
    has_results = (
        len(state.get("rag_results", [])) > 0 or
        len(state.get("memory_results", [])) > 0 or
        len(state.get("tool_outputs", {})) > 0
    )
    
    # Check iteration limit
    if state["iteration_count"] >= state["max_iterations"]:
        return "finalize"
    
    # If tools found nothing, may need different strategy
    if not has_results:
        # Increment iteration and try again with different approach
        state["iteration_count"] += 1
        return "agent_decide"
    
    # Success path - finalize response
    return "finalize"
```

## Funkció-specifikus konfiguráció

### Node Timeout Configuration
```ini
# Individual node timeouts (seconds)
INITIALIZE_TIMEOUT_SEC=5
PREPARE_QUERY_TIMEOUT_SEC=10  
AGENT_DECIDE_TIMEOUT_SEC=15
TOOLS_TIMEOUT_SEC=30
FINALIZE_TIMEOUT_SEC=20

# Tool-specific timeouts
RAG_SEARCH_TIMEOUT_SEC=10
MEMORY_SEARCH_TIMEOUT_SEC=5
DOCUMENT_RETRIEVAL_TIMEOUT_SEC=15
CREATE_MEMORY_TIMEOUT_SEC=8
```

### Performance Monitoring
```python
# Node execution metrics automatically tracked
{
    "node_name": "agent_decide",
    "duration_ms": 1250,
    "status": "success", 
    "input_size_bytes": 2048,
    "output_size_bytes": 512,
    "llm_tokens": 245,
    "llm_cost_usd": 0.00123
}
```

### Error Recovery Strategies
```python
# Node-level error handling configuration
NODE_ERROR_STRATEGIES = {
    "initialize": "fail_workflow",        # Critical node - must succeed
    "prepare_query": "continue_original", # Use original query if processing fails  
    "agent_decide": "default_tools",      # Use default tool set if decision fails
    "tools": "partial_results",           # Continue with available results
    "finalize": "basic_response"          # Generate simple response if formatting fails
}
```

### Multi-tenant Node Behavior
```python
# All nodes enforce tenant isolation
def enforce_tenant_isolation(node_func):
    def wrapper(state: ChatState):
        # Validate tenant_id in state
        if "tenant_id" not in state:
            raise WorkflowError("Missing tenant_id in state")
            
        # Log tenant-specific metrics
        log_node_execution(
            node_name=node_func.__name__,
            tenant_id=state["tenant_id"],
            execution_start=time.time()
        )
        
        # Execute node with tenant context
        return node_func(state)
    
    return wrapper
```