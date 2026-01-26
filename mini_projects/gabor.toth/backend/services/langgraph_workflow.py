"""Advanced LangGraph workflow with hybrid approach: Explicit Nodes + Tool Registry."""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, TypedDict, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from datetime import datetime

from domain.models import CategoryDecision, Message, MessageRole, RetrievedChunk
from domain.interfaces import (
    CategoryRouter, EmbeddingService, VectorStore,
    RAGAnswerer, ActivityCallback
)


# ============================================================================
# ENUMS & MODELS
# ============================================================================

class SearchStrategy(str, Enum):
    """Search strategy types."""
    CATEGORY_BASED = "category_based"
    FALLBACK_ALL_CATEGORIES = "fallback_all_categories"
    HYBRID_SEARCH = "hybrid_search"


class CitationSource(BaseModel):
    """Citation source information."""
    index: int = Field(..., description="Citation index in the answer")
    source: str = Field(..., description="Source document or reference")
    distance: float = Field(..., ge=0.0, le=1.0, description="Similarity distance (0=perfect, 1=worst)")
    preview: str = Field(..., description="Preview of the source text")


class SearchResult(BaseModel):
    """Result of a search operation."""
    chunks: List[RetrievedChunk]
    strategy_used: SearchStrategy
    search_time: float = Field(default=0.0, ge=0.0, description="Search execution time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if search failed")


class WorkflowInput(BaseModel):
    """Input for the workflow."""
    user_id: str = Field(..., min_length=1, description="User ID making the request")
    question: str = Field(..., min_length=5, description="Question to answer")
    available_categories: List[str] = Field(default_factory=list, description="Available categories to search")


class WorkflowOutput(BaseModel):
    """Output of the workflow."""
    final_answer: str = Field(..., description="Generated answer")
    answer_with_citations: str = Field(..., description="Answer with inline citations")
    citation_sources: List[CitationSource] = Field(default_factory=list, description="Citation metadata")
    context_chunks: List[RetrievedChunk] = Field(default_factory=list, description="Retrieved context chunks with full content")
    workflow_steps: List[str] = Field(default_factory=list, description="Audit trail of workflow steps")
    error_messages: List[str] = Field(default_factory=list, description="Any errors encountered")
    routed_category: Optional[str] = Field(default=None, description="Category the question was routed to")
    search_strategy: Optional[str] = Field(default=None, description="Search strategy used")
    fallback_triggered: bool = Field(default=False, description="Whether fallback search was triggered")
    workflow_log: Optional[Dict[str, Any]] = Field(default=None, description="Full workflow execution trace")
    debug_metadata: Optional[Dict[str, Any]] = Field(default=None, description="Debug and performance metadata")
    workflow_logs: List[Dict[str, Any]] = Field(default_factory=list, description="Step-by-step debug logs from each node")


class WorkflowState(TypedDict, total=False):
    """State representation for the workflow graph."""
    # Input
    user_id: str
    session_id: str
    question: str
    available_categories: List[str]
    activity_callback: Optional[ActivityCallback]
    
    # Category routing
    routed_category: Optional[str]
    category_confidence: float
    category_reason: str
    
    # Retrieval
    context_chunks: List[RetrievedChunk]
    search_strategy: SearchStrategy
    fallback_triggered: bool
    
    # Generation
    final_answer: str
    answer_with_citations: str
    citation_sources: List[Dict[str, Any]]
    
    # Error handling & recovery
    errors: List[str]
    error_count: int
    retry_count: int
    tool_failures: Dict[str, Optional[str]]
    recovery_actions: List[str]
    last_error_type: Optional[str]
    
    # Logging & tracking
    workflow_logs: List[Dict[str, Any]]
    workflow_start_time: Optional[float]
    workflow_steps: List[str]
    error_messages: List[str]


# ============================================================================
# RETRY HELPER - Exponential backoff retry mechanism
# ============================================================================

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 2,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs
) -> tuple[Any, Optional[str]]:
    """Execute async function with exponential backoff retry."""
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            result = await func(*args, **kwargs)
            return result, None
        except asyncio.TimeoutError:
            last_error = f"timeout_{attempt}"
        except json.JSONDecodeError:
            return None, "invalid_json"
        except ValueError as e:
            return None, f"validation_error: {str(e)[:50]}"
        except Exception as e:
            last_error = f"api_error_{attempt}"
        
        if attempt < max_retries:
            wait_time = initial_delay * (backoff_factor ** attempt)
            await asyncio.sleep(wait_time)
    
    return None, last_error or "unknown_error"


# ============================================================================
# TOOL REGISTRY
# ============================================================================

@dataclass
class Tool:
    """Tool definition with async function."""
    name: str
    func: Callable[..., Awaitable[Any]]
    description: str


class ToolRegistry:
    """Registry for managing workflow tools."""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
    
    def register_tool(self, name: str, func: Callable[..., Awaitable[Any]], description: str) -> None:
        """Register a tool."""
        self.tools[name] = Tool(name=name, func=func, description=description)
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all available tools."""
        return list(self.tools.keys())


def create_tool_registry(
    category_router: CategoryRouter,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    rag_answerer: RAGAnswerer,
) -> ToolRegistry:
    """Create tool registry with async tools."""
    
    registry = ToolRegistry()
    
    # Tool 1: Category Router
    async def category_router_tool(
        question: str,
        available_categories: List[str],
    ) -> Dict[str, Any]:
        """Route question to the most appropriate category."""
        start_time = time.time()
        
        async def _call():
            decision = await category_router.decide_category(question, available_categories)
            return {
                "routed_category": decision.category,
                "category_confidence": decision.confidence,
                "category_reason": getattr(decision, "reason", ""),
            }
        
        result, error = await retry_with_backoff(_call, max_retries=2)
        elapsed_ms = (time.time() - start_time) * 1000
        
        if error:
            return {
                "routed_category": None,
                "category_confidence": 0.0,
                "category_reason": "",
                "_error": error,
                "_error_type": "category_router_failed",
                "_time_ms": elapsed_ms,
            }
        else:
            result["_time_ms"] = elapsed_ms
            return result
    
    # Tool 2: Embedding Service
    async def embed_question_tool(question: str) -> Dict[str, Any]:
        """Convert question text into vector representation."""
        start_time = time.time()
        
        async def _call():
            embedding = await embedding_service.embed_text(question)
            return {"question_embedding": embedding}
        
        result, error = await retry_with_backoff(_call, max_retries=2)
        elapsed_ms = (time.time() - start_time) * 1000
        
        if error:
            return {
                "question_embedding": [],
                "_error": error,
                "_error_type": "embedding_failed",
                "_time_ms": elapsed_ms,
            }
        else:
            result["_time_ms"] = elapsed_ms
            return result
    
    # Tool 3: Vector Search
    async def search_vectors_tool(
        question_embedding: List[float],
        collection_name: str,
    ) -> Dict[str, Any]:
        """Search vector database for semantically similar chunks."""
        start_time = time.time()
        
        if not question_embedding:
            return {
                "retrieved_chunks": [],
                "_error": "empty_embedding",
                "_error_type": "invalid_input",
                "_time_ms": (time.time() - start_time) * 1000,
            }
        
        async def _call():
            chunks = await vector_store.query(question_embedding, collection_name, top_k=5)
            return {"retrieved_chunks": chunks}
        
        result, error = await retry_with_backoff(_call, max_retries=1)
        elapsed_ms = (time.time() - start_time) * 1000
        
        if error:
            return {
                "retrieved_chunks": [],
                "_error": error,
                "_error_type": "search_failed",
                "_time_ms": elapsed_ms,
            }
        else:
            result["_time_ms"] = elapsed_ms
            return result
    
    # Tool 4: Answer Generation
    async def generate_answer_tool(
        question: str,
        chunks: List[RetrievedChunk],
        category: str,
    ) -> Dict[str, Any]:
        """Generate answer using LLM with document context."""
        start_time = time.time()
        
        if not chunks:
            return {
                "generated_answer": "No documents available for answering.",
                "_time_ms": (time.time() - start_time) * 1000,
            }
        
        async def _call():
            answer = await rag_answerer.generate_answer(question, chunks, category or "All documents")
            return {"generated_answer": answer}
        
        result, error = await retry_with_backoff(_call, max_retries=2)
        elapsed_ms = (time.time() - start_time) * 1000
        
        if error:
            fallback_answer = "Simplified answer:\n\n" + "\n---\n".join(
                [f"• {chunk.content[:200]}..." for chunk in chunks[:3]]
            )
            return {
                "generated_answer": fallback_answer,
                "_error": error,
                "_error_type": "generation_failed",
                "_fallback": True,
                "_time_ms": elapsed_ms,
            }
        else:
            result["_time_ms"] = elapsed_ms
            return result
    
    # Register tools
    registry.register_tool("category_router", category_router_tool, "Route question to category")
    registry.register_tool("embed_question", embed_question_tool, "Embed question to vector")
    registry.register_tool("search_vectors", search_vectors_tool, "Search vector database")
    registry.register_tool("generate_answer", generate_answer_tool, "Generate answer with LLM")
    
    return registry


# ============================================================================
# EXPLICIT NODES
# ============================================================================

def validate_input_node(state: WorkflowState) -> Dict[str, Any]:
    """Validate input and initialize tracking."""
    question = state.get("question", "").strip()
    available_categories = state.get("available_categories", [])
    
    # Initialize fields
    if "workflow_logs" not in state:
        state["workflow_logs"] = []
    if "workflow_steps" not in state:
        state["workflow_steps"] = []
    if "workflow_start_time" not in state:
        state["workflow_start_time"] = time.time()
    if "errors" not in state:
        state["errors"] = []
    if "error_count" not in state:
        state["error_count"] = 0
    if "retry_count" not in state:
        state["retry_count"] = 0
    if "tool_failures" not in state:
        state["tool_failures"] = {}
    if "recovery_actions" not in state:
        state["recovery_actions"] = []
    if "last_error_type" not in state:
        state["last_error_type"] = None
    if "error_messages" not in state:
        state["error_messages"] = []
    
    if not question:
        state["errors"].append("Question is empty")
        state["error_messages"] = ["Question is empty"]
        return state
    
    if not available_categories:
        state["errors"].append("No categories available")
        state["error_messages"] = ["No categories available"]
        return state
    
    state["workflow_steps"].append("input_validated")
    state["workflow_logs"].append({
        "node": "validate_input",
        "status": "success",
        "timestamp": datetime.now().isoformat(),
    })
    return state


def evaluate_search_quality_node(state: WorkflowState) -> Dict[str, Any]:
    """Evaluate search result quality."""
    chunks = state.get("context_chunks", [])
    
    chunk_count = len(chunks)
    avg_similarity = sum(getattr(c, "distance", 0.0) for c in chunks) / max(chunk_count, 1) if chunks else 0.0
    
    # Only trigger fallback once - check if we already triggered or ran out of retries
    already_triggered = state.get("fallback_triggered", False)
    retry_count = state.get("retry_count", 0)
    
    # Only trigger fallback if we haven't already and we have retries left
    needs_fallback = (not already_triggered) and (chunk_count < 2 or avg_similarity < 0.2) and retry_count < 1
    state["fallback_triggered"] = needs_fallback or already_triggered
    state["workflow_steps"].append("search_evaluated")
    
    state["workflow_logs"].append({
        "event": "quality_evaluation",
        "chunk_count": chunk_count,
        "avg_similarity": round(avg_similarity, 3),
        "fallback_needed": needs_fallback,
        "timestamp": datetime.now().isoformat(),
    })
    
    return state


def deduplicate_chunks_node(state: WorkflowState) -> Dict[str, Any]:
    """Deduplicate retrieved chunks."""
    chunks = state.get("context_chunks", [])
    original_count = len(chunks)
    
    if not chunks:
        state["workflow_steps"].append("dedup_completed")
        state["workflow_logs"].append({
            "event": "deduplication",
            "original_count": 0,
            "final_count": 0,
            "timestamp": datetime.now().isoformat(),
        })
        return state
    
    seen = set()
    unique_chunks = []
    
    for chunk in chunks:
        content_hash = hash(chunk.content)
        if content_hash not in seen:
            seen.add(content_hash)
            unique_chunks.append(chunk)
    
    state["context_chunks"] = unique_chunks
    state["workflow_steps"].append("dedup_completed")
    
    final_count = len(unique_chunks)
    state["workflow_logs"].append({
        "event": "deduplication",
        "original_count": original_count,
        "final_count": final_count,
        "duplicates_removed": original_count - final_count,
        "timestamp": datetime.now().isoformat(),
    })
    
    return state


def handle_errors_node(state: WorkflowState) -> Dict[str, Any]:
    """Handle errors with retry logic."""
    error_count = state.get("error_count", 0)
    retry_count = state.get("retry_count", 0)
    last_error_type = state.get("last_error_type")
    
    if error_count == 0:
        state["workflow_logs"].append({
            "event": "error_check",
            "status": "no_errors",
            "next_node": "evaluate_search_quality",
            "timestamp": datetime.now().isoformat(),
        })
        return state
    
    if last_error_type in ["timeout", "api_error", "embedding_failed", "category_router_failed", "search_failed"]:
        if retry_count < 2:
            state["retry_count"] += 1
            state["recovery_actions"].append(f"retry_attempt_{retry_count + 1}")
            
            state["workflow_logs"].append({
                "event": "error_recovery",
                "decision": "retry",
                "retry_count": retry_count + 1,
                "error_type": last_error_type,
                "timestamp": datetime.now().isoformat(),
            })
            
            return state
        else:
            state["fallback_triggered"] = True
            state["recovery_actions"].append("fallback_after_retries")
            
            state["workflow_logs"].append({
                "event": "error_recovery",
                "decision": "fallback",
                "reason": "retries_exhausted",
                "error_type": last_error_type,
                "timestamp": datetime.now().isoformat(),
            })
            
            return state
    
    state["workflow_logs"].append({
        "event": "error_recovery",
        "decision": "skip",
        "reason": "non_recoverable_error",
        "error_type": last_error_type,
        "timestamp": datetime.now().isoformat(),
    })
    
    return state


def format_response_node(state: WorkflowState) -> Dict[str, Any]:
    """Format final response."""
    chunks = state.get("context_chunks", [])
    
    citation_sources = []
    for idx, chunk in enumerate(chunks[:5], 1):
        citation_sources.append({
            "index": idx,
            "source": getattr(chunk, "source", "Unknown"),
            "distance": getattr(chunk, "distance", 0.0),
            "preview": chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
        })
    
    state["citation_sources"] = citation_sources
    state["answer_with_citations"] = state.get("final_answer", "")
    state["workflow_steps"].append("response_formatted")
    
    start_time = state.get("workflow_start_time", time.time())
    total_time_ms = (time.time() - start_time) * 1000
    
    error_count = state.get("error_count", 0)
    
    state["workflow_log"] = {
        "session_id": state.get("session_id", ""),
        "user_id": state.get("user_id", ""),
        "question": state.get("question", ""),
        "total_time_ms": round(total_time_ms, 2),
        "status": "success" if error_count == 0 else "completed_with_errors",
        "error_count": error_count,
        "retry_count": state.get("retry_count", 0),
        "fallback_triggered": state.get("fallback_triggered", False),
        "answer_generated": bool(state.get("final_answer")),
        "chunk_count": len(chunks),
        "citation_count": len(citation_sources),
        "logs": state.get("workflow_logs", []),
        "recovery_actions": state.get("recovery_actions", []),
    }
    
    state["debug_metadata"] = {
        "tool_failures": state.get("tool_failures", {}),
        "error_messages": state.get("error_messages", []),
        "last_error_type": state.get("last_error_type"),
        "search_strategy": state.get("search_strategy", "").value if isinstance(state.get("search_strategy"), SearchStrategy) else None,
    }
    
    state["workflow_logs"].append({
        "event": "workflow_complete",
        "total_time_ms": round(total_time_ms, 2),
        "status": state["workflow_log"]["status"],
        "timestamp": datetime.now().isoformat(),
    })
    
    return state


def process_tool_results_node(state: WorkflowState) -> Dict[str, Any]:
    """Process tool results."""
    return state


def route_errors(state: WorkflowState) -> str:
    """Routing function for error handling decision - only retries, then continues."""
    error_count = state.get("error_count", 0)
    
    # Only retry if we have errors and haven't retried yet
    if error_count > 0 and state.get("retry_count", 0) < 1:
        return "tools"
    else:
        return "continue_to_eval"


def route_to_fallback_decision_node(state: WorkflowState) -> str:
    """Route to fallback or continue."""
    # Only trigger fallback once
    if state.get("fallback_triggered") and state.get("retry_count", 0) == 0:
        return "tools"
    else:
        return "dedup_chunks"


# ============================================================================
# ASYNC LOGGING TO DISK
# ============================================================================

async def write_workflow_log_async(user_id: str, session_id: str, workflow_log: Dict) -> None:
    """Asynchronously write workflow log to disk as JSON."""
    import os
    import json
    
    log_dir = os.path.join("data", "logs", user_id)
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{session_id}.json"
    filepath = os.path.join(log_dir, filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(workflow_log, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Failed to write workflow log to {filepath}: {str(e)}")


# ============================================================================
# WORKFLOW FACTORY
# ============================================================================

# ============================================================================
# WORKFLOW FACTORY
# ============================================================================

def create_advanced_rag_workflow(
    category_router: CategoryRouter,
    embedding_service: EmbeddingService,
    vector_store: VectorStore,
    rag_answerer: RAGAnswerer,
):
    """Create advanced LangGraph workflow."""
    
    tool_registry = create_tool_registry(
        category_router,
        embedding_service,
        vector_store,
        rag_answerer
    )
    
    # INLINE TOOLS EXECUTOR (with closure access to parameters) - SYNC with async calls
    def tools_executor_inline(state: WorkflowState) -> Dict[str, Any]:
        """Execute all tools within workflow context - SYNC WRAPPER FOR ASYNC CALLS."""
        print(f"🔧 tools_executor_inline CALLED! Question: {state.get('question', '')[:50]}")
        question = state.get("question", "")
        available_categories = state.get("available_categories", [])
        
        if not question or not available_categories:
            state["error_messages"].append("Missing question or categories")
            state["error_count"] = state.get("error_count", 0) + 1
            return state
        
        # Helper: run async function in sync context
        def run_async(coro):
            """Run async function in sync context - create new loop if needed."""
            try:
                loop = asyncio.get_running_loop()
                # If we're here, there's already a running loop - this shouldn't happen in sync code
                raise RuntimeError("Cannot run_until_complete in already-running loop")
            except RuntimeError:
                # No running loop, safe to create one
                pass
            
            # Create a fresh event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
                return result
            finally:
                loop.close()
        
        # Tool 1: Category Routing
        try:
            decision = run_async(category_router.decide_category(question, available_categories))
            state["routed_category"] = decision.category
            state["category_reason"] = decision.reason
            state["category_confidence"] = getattr(decision, 'confidence', 0.5)
            state["workflow_logs"].append({
                "node": "tools_executor",
                "step": "category_routing",
                "routed_category": decision.category,
                "timestamp": datetime.now().isoformat(),
            })
            print(f"✅ Routed to category: {decision.category}")
        except Exception as e:
            state["error_messages"].append(f"Category routing failed: {str(e)}")
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error_type"] = "category_router_failed"
            print(f"❌ Category routing error: {e}")
        
        # Tool 2: Embed Question
        question_embedding = None
        try:
            question_embedding = run_async(embedding_service.embed_text(question))
            state["workflow_logs"].append({
                "node": "tools_executor",
                "step": "embedding",
                "embedding_dim": len(question_embedding) if question_embedding else 0,
                "timestamp": datetime.now().isoformat(),
            })
            print(f"✅ Embedded question")
        except Exception as e:
            state["error_messages"].append(f"Embedding failed: {str(e)}")
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error_type"] = "embedding_failed"
            print(f"❌ Embedding error: {e}")
        
        # Tool 3: Vector Search
        context_chunks = []
        if question_embedding and state.get("routed_category"):
            routed_category = state.get("routed_category")
            
            # Build collection name
            import unicodedata
            text = unicodedata.normalize('NFKD', routed_category)
            text = text.encode('ascii', 'ignore').decode('ascii')
            text = text.lower().replace(" ", "_").replace("/", "_")
            text = ''.join(c if c.isalnum() or c in '_-' else '' for c in text)
            text = text.strip('_-')
            if len(text) < 3:
                text = text + 'x' * (3 - len(text))
            if len(text) > 63:
                text = text[:63]
            
            collection_name = f"cat_{text}"
            
            try:
                chunks = run_async(vector_store.query(collection_name, question_embedding, top_k=5))
                context_chunks = chunks if chunks else []
                state["context_chunks"] = context_chunks
                state["workflow_logs"].append({
                    "node": "tools_executor",
                    "step": "vector_search",
                    "collection": collection_name,
                    "chunks_found": len(context_chunks),
                    "timestamp": datetime.now().isoformat(),
                })
                print(f"✅ Found {len(context_chunks)} chunks")
            except Exception as e:
                state["error_messages"].append(f"Vector search failed: {str(e)}")
                state["error_count"] = state.get("error_count", 0) + 1
                state["last_error_type"] = "search_failed"
                print(f"❌ Vector search error: {e}")
        
        # Tool 4: Generate Answer
        if context_chunks:
            try:
                answer = run_async(rag_answerer.generate_answer(
                    question, 
                    context_chunks, 
                    state.get("routed_category") or "General"
                ))
                state["final_answer"] = answer
                state["workflow_logs"].append({
                    "node": "tools_executor",
                    "step": "answer_generation",
                    "answer_length": len(answer),
                    "timestamp": datetime.now().isoformat(),
                })
                print(f"✅ Generated answer ({len(answer)} chars)")
            except Exception as e:
                state["error_messages"].append(f"Answer generation failed: {str(e)}")
                state["error_count"] = state.get("error_count", 0) + 1
                state["last_error_type"] = "generation_failed"
                # Fallback: use chunk content
                state["final_answer"] = "Nem tudok megfelelő választ adni, de itt vannak az elérhető dokumentumok:\n\n" + \
                    "\n---\n".join([chunk.content[:200] for chunk in context_chunks[:3]])
                print(f"❌ Answer generation error, using fallback: {e}")
        else:
            # No chunks found
            state["final_answer"] = "Nincs megfelelő dokumentum a feltöltött anyagok között."
            state["fallback_triggered"] = True
            print(f"⚠️  No chunks found, using fallback")
        
        state["workflow_steps"].append("tools_executed")
        return state

    
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    print(f"📝 Adding nodes...")
    workflow.add_node("validate_input", validate_input_node)
    workflow.add_node("evaluate_search_quality", evaluate_search_quality_node)
    workflow.add_node("dedup_chunks", deduplicate_chunks_node)
    workflow.add_node("format_response", format_response_node)
    workflow.add_node("process_tool_results", process_tool_results_node)
    workflow.add_node("handle_errors", handle_errors_node)
    workflow.add_node("tools", tools_executor_inline)  # ✅ CLOSURE-BASED TOOL EXECUTOR
    print(f"📝 Nodes added: {list(workflow.nodes.keys())}")

    
    # Set entry point
    print(f"📝 Setting entry point to validate_input")
    workflow.set_entry_point("validate_input")
    
    # Add edges - simple linear flow without loops for now
    print(f"📝 Adding edges...")
    workflow.add_edge("validate_input", "tools")
    workflow.add_edge("tools", "process_tool_results")
    workflow.add_edge("process_tool_results", "handle_errors")
    workflow.add_edge("handle_errors", "evaluate_search_quality")
    workflow.add_edge("evaluate_search_quality", "dedup_chunks")
    workflow.add_edge("dedup_chunks", "format_response")
    
    workflow.set_finish_point("format_response")
    
    return workflow.compile(), tool_registry


# ============================================================================
# ADVANCED RAG AGENT
# ============================================================================

class AdvancedRAGAgent:
    """Advanced RAG agent with hybrid workflow."""

    def __init__(self, compiled_graph, tool_registry: ToolRegistry):
        self.graph = compiled_graph
        self.tool_registry = tool_registry

    async def answer_question(
        self,
        user_id: str,
        question: str,
        available_categories: List[str],
        activity_callback: Optional[ActivityCallback] = None,
    ) -> WorkflowOutput:
        """Run workflow to answer question."""
        session_id = str(int(time.time() * 1000))
        
        initial_state: WorkflowState = {
            "user_id": user_id,
            "session_id": session_id,
            "question": question,
            "available_categories": available_categories,
            "routed_category": None,
            "category_confidence": 0.0,
            "category_reason": "",
            "context_chunks": [],
            "search_strategy": SearchStrategy.CATEGORY_BASED,
            "fallback_triggered": False,
            "final_answer": "",
            "answer_with_citations": "",
            "citation_sources": [],
            "workflow_steps": [],
            "error_messages": [],
            "activity_callback": activity_callback,
            "workflow_logs": [],
            "workflow_start_time": time.time(),
            "errors": [],
            "error_count": 0,
            "retry_count": 0,
            "tool_failures": {},
            "recovery_actions": [],
            "last_error_type": None,
        }

        result = self.graph.invoke(initial_state, {"recursion_limit": 50})

        citation_sources = []
        for source_dict in result.get("citation_sources", []):
            try:
                citation_sources.append(CitationSource(**source_dict))
            except Exception:
                pass

        return WorkflowOutput(
            final_answer=result.get("final_answer", ""),
            answer_with_citations=result.get("answer_with_citations", result.get("final_answer", "")),
            citation_sources=citation_sources,
            context_chunks=result.get("context_chunks", []),
            workflow_steps=result.get("workflow_steps", []),
            error_messages=result.get("error_messages", []),
            routed_category=result.get("routed_category"),
            search_strategy=result.get("search_strategy", SearchStrategy.CATEGORY_BASED).value if isinstance(result.get("search_strategy"), SearchStrategy) else None,
            fallback_triggered=result.get("fallback_triggered", False),
            workflow_log=result.get("workflow_log"),
            debug_metadata=result.get("debug_metadata"),
            workflow_logs=result.get("workflow_logs", []),
        )
