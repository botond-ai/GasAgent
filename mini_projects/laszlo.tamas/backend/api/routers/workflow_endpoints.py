"""
Workflow Tracking API Endpoints - PHASE 3 Implementation

Provides REST API for workflow execution history, debugging, and analytics.
Supports prompt lineage visualization, state inspection, and cost analysis.

Key Features:
- Historical workflow execution queries
- Node-level execution traces
- Prompt lineage reconstruction
- State diff visualization
- Cost breakdown analysis
- RAG relevance metrics
- Trace context correlation

Usage:
GET /api/workflow-executions/{execution_id}          # Full execution details
GET /api/workflow-executions?session_id=X&limit=20  # Session history
GET /api/workflow-executions/{id}/nodes             # Node execution traces
GET /api/workflow-executions/{id}/prompt-lineage    # Agent decision chain
GET /api/workflow-executions/{id}/state-timeline    # State mutations
GET /api/workflow-executions/{id}/cost-breakdown    # Token/cost analysis
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from database.repositories.workflow_tracking_repository import workflow_tracking_repo
from database.models import (
    WorkflowExecutionResponse,
    NodeExecutionResponse, 
    PromptLineageResponse,
    StateTimelineResponse,
    CostBreakdownResponse,
    TraceContextResponse
)

router = APIRouter()

# ===============================
# CORE WORKFLOW TRACKING ENDPOINTS
# ===============================

@router.get("/workflow-executions/{execution_id}", response_model=WorkflowExecutionResponse)
async def get_workflow_execution(execution_id: UUID):
    """
    Get complete workflow execution details.
    
    Returns:
    - Execution metadata (duration, status, tokens, cost)
    - Input query and final answer
    - Tool invocations summary
    - Error details if failed
    """
    try:
        execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
        
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")
            
        return WorkflowExecutionResponse(**execution)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/workflow-executions", response_model=List[WorkflowExecutionResponse])
async def list_workflow_executions(
    session_id: Optional[UUID] = Query(None, description="Filter by chat session"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant"),
    user_id: Optional[int] = Query(None, description="Filter by user"),
    status: Optional[str] = Query(None, description="Filter by status (running, success, error, timeout)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results (1-100)"),
    offset: int = Query(0, ge=0, description="Results offset for pagination")
):
    """
    List workflow executions with filtering and pagination.
    
    Supports filtering by:
    - session_id: All executions in a chat session
    - tenant_id: All executions for a tenant
    - user_id: All executions for a user
    - status: Filter by execution status
    
    Results ordered by started_at DESC (most recent first).
    """
    try:
        filters = {}
        if session_id:
            filters["session_id"] = str(session_id)
        if tenant_id:
            filters["tenant_id"] = tenant_id
        if user_id:
            filters["user_id"] = user_id
        if status:
            filters["status"] = status
            
        executions = await workflow_tracking_repo.get_executions_filtered(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return [WorkflowExecutionResponse(**exec) for exec in executions]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/workflow-executions/{execution_id}/nodes", response_model=List[NodeExecutionResponse])
async def get_node_executions(execution_id: UUID):
    """
    Get all node executions for a workflow.
    
    Returns:
    - Node execution timeline (ordered by node_index)
    - Duration and status per node
    - State diffs (before/after snapshots)
    - Node-specific metadata (LLM tokens, tool results)
    """
    try:
        nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
        
        if not nodes:
            # Check if execution exists
            execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
            if not execution:
                raise HTTPException(status_code=404, detail="Workflow execution not found")
            
            # Execution exists but no node data
            return []
            
        return [NodeExecutionResponse(**node) for node in nodes]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ===============================
# PROMPT LINEAGE & DEBUGGING
# ===============================

@router.get("/workflow-executions/{execution_id}/prompt-lineage", response_model=PromptLineageResponse)
async def get_prompt_lineage(execution_id: UUID):
    """
    Get agent decision chain and prompt lineage.
    
    Reconstructs:
    - Agent reasoning steps (decision → reflection → finalize)
    - LLM prompt/response pairs with token counts
    - Tool invocation results and context
    - Decision confidence scores and alternatives considered
    """
    try:
        # Get workflow execution
        execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")
            
        # Get node executions to reconstruct lineage
        nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
        
        # Build prompt lineage chain
        prompt_chain = []
        decision_points = []
        
        for node in nodes:
            metadata = node.get("metadata", {}) or {}
            
            # Extract LLM interactions
            if node["node_name"] in ["agent_decide", "agent_reflection", "agent_finalize"]:
                llm_data = metadata.get("llm_call", {})
                if llm_data:
                    prompt_chain.append({
                        "node_name": node["node_name"],
                        "iteration": metadata.get("iteration_count", 1),
                        "llm_call": {
                            "prompt_tokens": llm_data.get("prompt_tokens", 0),
                            "completion_tokens": llm_data.get("completion_tokens", 0),
                            "model": llm_data.get("model", "unknown"),
                            "prompt_preview": llm_data.get("prompt_preview", ""),
                            "response_preview": llm_data.get("response_preview", ""),
                            "reasoning_trace": llm_data.get("reasoning_trace", "")
                        },
                        "tools_called": metadata.get("tools_called", []),
                        "state_mutations": metadata.get("state_mutations", [])
                    })
                    
                # Extract decision points
                decision_data = metadata.get("decision", {})
                if decision_data:
                    decision_points.append({
                        "node": node["node_name"],
                        "decision": decision_data.get("action", "unknown"),
                        "confidence": decision_data.get("confidence", 0.0),
                        "alternatives_considered": decision_data.get("alternatives", [])
                    })
        
        return PromptLineageResponse(
            execution_id=execution_id,
            trace_id=execution.get("trace_id", ""),
            prompt_chain=prompt_chain,
            decision_points=decision_points
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/workflow-executions/{execution_id}/state-timeline", response_model=StateTimelineResponse)
async def get_state_timeline(execution_id: UUID):
    """
    Get state mutation timeline for debugging.
    
    Returns:
    - State snapshots before/after each node
    - Diff highlighting changed fields
    - Timeline visualization data
    """
    try:
        nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
        
        if not nodes:
            execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
            if not execution:
                raise HTTPException(status_code=404, detail="Workflow execution not found")
            return StateTimelineResponse(execution_id=execution_id, timeline=[])
        
        timeline = []
        for node in nodes:
            timeline.append({
                "node_index": node["node_index"],
                "node_name": node["node_name"],
                "started_at": node["started_at"],
                "duration_ms": node["duration_ms"],
                "state_before": node.get("state_before", {}),
                "state_after": node.get("state_after", {}),
                "state_diff": node.get("state_diff", {}),
                "status": node["status"]
            })
        
        return StateTimelineResponse(
            execution_id=execution_id,
            timeline=timeline
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ===============================
# COST & PERFORMANCE ANALYSIS
# ===============================

@router.get("/workflow-executions/{execution_id}/cost-breakdown", response_model=CostBreakdownResponse)
async def get_cost_breakdown(execution_id: UUID):
    """
    Get detailed cost and token analysis.
    
    Returns:
    - Cost breakdown by model and operation
    - Token usage flow (input → processing → output)
    - Cost per node analysis
    - Efficiency metrics
    """
    try:
        execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")
            
        nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
        
        # Aggregate cost data from nodes
        cost_by_model = {}
        cost_by_node = {}
        token_flow = {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "embedding_tokens": 0
        }
        
        for node in nodes:
            metadata = node.get("metadata", {}) or {}
            
            # LLM costs
            llm_data = metadata.get("llm_call", {})
            if llm_data:
                model = llm_data.get("model", "unknown")
                cost = llm_data.get("cost_usd", 0.0)
                prompt_tokens = llm_data.get("prompt_tokens", 0)
                completion_tokens = llm_data.get("completion_tokens", 0)
                
                if model not in cost_by_model:
                    cost_by_model[model] = {"cost": 0.0, "tokens": {"prompt": 0, "completion": 0}}
                
                cost_by_model[model]["cost"] += cost
                cost_by_model[model]["tokens"]["prompt"] += prompt_tokens
                cost_by_model[model]["tokens"]["completion"] += completion_tokens
                
                cost_by_node[node["node_name"]] = cost_by_node.get(node["node_name"], 0) + cost
                
                token_flow["total_prompt_tokens"] += prompt_tokens
                token_flow["total_completion_tokens"] += completion_tokens
            
            # Embedding costs
            embedding_data = metadata.get("embedding", {})
            if embedding_data:
                token_flow["embedding_tokens"] += embedding_data.get("tokens", 0)
        
        total_cost = execution.get("llm_cost_usd", 0.0)
        
        return CostBreakdownResponse(
            execution_id=execution_id,
            total_cost_usd=total_cost,
            cost_by_model=cost_by_model,
            cost_by_node=cost_by_node,
            token_flow=token_flow,
            efficiency_metrics={
                "cost_per_token": total_cost / max(token_flow["total_prompt_tokens"] + token_flow["total_completion_tokens"], 1),
                "tokens_per_second": (token_flow["total_prompt_tokens"] + token_flow["total_completion_tokens"]) / max(execution.get("duration_ms", 1) / 1000, 1)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ===============================
# TRACE CONTEXT & RAG ANALYSIS
# ===============================

@router.get("/workflow-executions/{execution_id}/trace-context", response_model=TraceContextResponse)
async def get_trace_context(execution_id: UUID):
    """
    Get distributed tracing context and correlation.
    
    Returns:
    - request_id, trace_id, session_id correlation
    - OpenTelemetry span hierarchy
    - Cross-service dependencies
    """
    try:
        execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
        if not execution:
            raise HTTPException(status_code=404, detail="Workflow execution not found")
            
        return TraceContextResponse(
            execution_id=execution_id,
            request_id=execution.get("request_id", ""),
            trace_id=execution.get("trace_id", ""),
            session_id=execution.get("session_id", ""),
            tenant_id=execution.get("tenant_id", 0),
            user_id=execution.get("user_id", 0),
            jaeger_trace_url=f"http://localhost:16686/trace/{execution.get('trace_id', '')}",
            tempo_trace_url=f"http://localhost:3200/trace/{execution.get('trace_id', '')}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/workflow-executions/{execution_id}/rag-relevance")
async def get_rag_relevance(execution_id: UUID):
    """
    Get RAG retrieval relevance analysis.
    
    Returns:
    - Retrieved chunks with relevance scores
    - Relevance distribution histogram
    - Empty result analysis
    """
    try:
        nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
        
        rag_data = []
        for node in nodes:
            if node["node_name"] in ["search_vectors", "fetch_documents"]:
                metadata = node.get("metadata", {}) or {}
                rag_results = metadata.get("rag_results", {})
                
                if rag_results:
                    rag_data.append({
                        "node_name": node["node_name"],
                        "chunks_retrieved": rag_results.get("chunks_retrieved", 0),
                        "average_relevance": rag_results.get("average_relevance", 0.0),
                        "relevance_scores": rag_results.get("relevance_scores", []),
                        "empty_result": rag_results.get("chunks_retrieved", 0) == 0
                    })
        
        if not rag_data:
            return {"execution_id": execution_id, "rag_operations": []}
            
        return {"execution_id": execution_id, "rag_operations": rag_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ===============================
# STATE INSPECTION ENDPOINTS
# ===============================

@router.get("/workflow-executions/{execution_id}/state-snapshot")
async def get_state_snapshot(execution_id: UUID, node_index: Optional[int] = Query(None)):
    """
    Get state snapshot at specific node or final state.
    
    Parameters:
    - node_index: Get state after specific node (0-based), or final if None
    """
    try:
        if node_index is not None:
            nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
            matching_node = next((n for n in nodes if n["node_index"] == node_index), None)
            
            if not matching_node:
                raise HTTPException(status_code=404, detail=f"Node {node_index} not found")
                
            return {
                "execution_id": execution_id,
                "node_index": node_index,
                "node_name": matching_node["node_name"],
                "state_after": matching_node.get("state_after", {})
            }
        else:
            # Return final state
            execution = await workflow_tracking_repo.get_execution_by_id(str(execution_id))
            if not execution:
                raise HTTPException(status_code=404, detail="Workflow execution not found")
                
            return {
                "execution_id": execution_id,
                "final_state": execution.get("final_state", {})
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/workflow-executions/{execution_id}/state-diff/{node_index}")
async def get_state_diff(execution_id: UUID, node_index: int):
    """
    Get state diff for specific node execution.
    
    Returns before/after state comparison with highlighted changes.
    """
    try:
        nodes = await workflow_tracking_repo.get_node_executions(str(execution_id))
        matching_node = next((n for n in nodes if n["node_index"] == node_index), None)
        
        if not matching_node:
            raise HTTPException(status_code=404, detail=f"Node {node_index} not found")
            
        return {
            "execution_id": execution_id,
            "node_index": node_index,
            "node_name": matching_node["node_name"],
            "state_before": matching_node.get("state_before", {}),
            "state_after": matching_node.get("state_after", {}),
            "state_diff": matching_node.get("state_diff", {}),
            "duration_ms": matching_node["duration_ms"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


# ===============================
# PERFORMANCE & ANALYTICS
# ===============================

@router.get("/workflow-executions/analytics/summary")
async def get_execution_summary(
    hours: int = Query(24, ge=1, le=168, description="Time window in hours (1-168)"),
    tenant_id: Optional[int] = Query(None, description="Filter by tenant")
):
    """
    Get workflow execution analytics summary.
    
    Returns:
    - Success rate and error breakdown
    - Average duration and latency percentiles
    - Cost analysis and trends
    - Most common error patterns
    """
    try:
        # This would require additional repository methods
        # For now, return a placeholder response
        return {
            "time_window_hours": hours,
            "tenant_id": tenant_id,
            "summary": {
                "total_executions": 0,
                "success_rate": 0.0,
                "average_duration_ms": 0,
                "total_cost_usd": 0.0
            },
            "note": "Analytics implementation in progress"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")