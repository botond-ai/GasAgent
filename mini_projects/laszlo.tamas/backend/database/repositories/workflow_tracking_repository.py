"""
Workflow Tracking Repository - PostgreSQL tracking for tenant/user-level metrics

Purpose:
- Store workflow execution details (tenant_id, user_id, duration, tokens, cost)
- Store node-level execution traces (metadata or full state based on config)
- Enable high-cardinality aggregation queries (NOT suitable for Prometheus)
- Support business analytics (usage per tenant, user patterns)

Schema: workflow_executions table
- request_id (PK)
- tenant_id (high-cardinality - for business queries)
- user_id (high-cardinality - for user analytics)
- session_id (chat session FK)
- intent (search_knowledge, list_documents, store_memory)
- total_duration_ms
- llm_tokens_total
- llm_cost_usd
- tool_calls_count
- chunks_retrieved_count
- success
- error_message (if failed)
- created_at

Node-level tracking (runtime-configurable):
- OFF: No node tracking
- METADATA_ONLY: Store node metadata (~2KB per node)
- FULL_STATE: Store full state snapshots (~200KB per node)

Usage:
```python
from database.repositories.workflow_tracking_repository import workflow_tracking_repo
from services.state_helpers import serialize_state_for_db

# In workflow finalize node:
tracking_data = serialize_state_for_db(state)
workflow_tracking_repo.insert_workflow_execution(tracking_data)

# After each node (conditional):
asyncio.create_task(
    workflow_tracking_repo.insert_node_execution_async(...)
)
```
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import asyncio
import json
import psycopg2.extras
from database.pg_connection import get_db_connection as get_connection

logger = logging.getLogger(__name__)


def _serialize_for_jsonb(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Serialize dict for JSONB storage (convert datetime to ISO string)."""
    if not data:
        return None
    
    def convert_value(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: convert_value(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_value(item) for item in obj]
        else:
            return obj
    
    return convert_value(data)


class WorkflowTrackingRepository:
    """
    Repository for workflow_executions table.
    
    CRITICAL: This table handles HIGH-CARDINALITY data (tenant_id, user_id)
    - Prometheus CANNOT handle this → time series explosion
    - PostgreSQL aggregation queries → business analytics
    """
    
    def __init__(self):
        self.table_name = "workflow_executions"
    
    def create_workflow_execution(
        self,
        execution_id: str,
        session_id: str,
        tenant_id: int,
        user_id: int,
        query: str,
        request_id: str
    ) -> bool:
        """
        CRITICAL FIX 1.3: Create new workflow execution record at workflow start.
        
        Args:
            execution_id: UUID for this workflow execution
            session_id: Chat session UUID
            tenant_id: Tenant identifier  
            user_id: User identifier
            query: Original user query
            request_id: API request identifier
            
        Returns:
            bool: True if created successfully
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    insert_sql = f"""
                        INSERT INTO {self.table_name} (
                            execution_id, tenant_id, user_id, session_id,
                            query_original, intent, status, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """
                    
                    cur.execute(insert_sql, (
                        execution_id,
                        tenant_id,
                        user_id,
                        session_id,
                        query,
                        "chat_query",  # Default intent
                        "in_progress",  # Initial status
                        datetime.utcnow()
                    ))
                    conn.commit()
                    
                    logger.info(f"[TRACKING] Created workflow execution: {execution_id}")
                    return True
                
        except Exception as e:
            logger.error(f"[TRACKING] Failed to create workflow execution {execution_id}: {e}")
            return False
    
    def complete_workflow_execution(
        self,
        execution_id: str,
        final_answer: Optional[str] = None,
        total_duration_ms: int = 0,
        success: bool = True,
        error_message: Optional[str] = None,
        actions_taken: List[str] = None,
        tools_called: List[Dict[str, Any]] = None
    ) -> bool:
        """
        CRITICAL FIX 1.3: Complete workflow execution record at workflow end.
        
        Args:
            execution_id: UUID for this workflow execution
            final_answer: LLM final response
            total_duration_ms: Total execution time
            success: Whether workflow completed successfully
            error_message: Error message if failed
            actions_taken: List of actions performed
            tools_called: List of tools invoked
            
        Returns:
            bool: True if updated successfully
        """
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    update_sql = f"""
                        UPDATE {self.table_name} 
                        SET 
                            total_duration_ms = %s,
                            duration_ms = %s,
                            status = %s,
                            success = %s,
                            error_message = %s,
                            tool_calls_count = %s,
                            completed_at = %s
                        WHERE execution_id = %s
                    """
                    
                    tools_count = len(tools_called) if tools_called else 0
                    status = 'completed' if success else 'failed'
                    
                    cur.execute(update_sql, (
                        total_duration_ms,
                        total_duration_ms,  # Same value for both fields
                        status,
                        success,
                        error_message,
                        tools_count,
                        datetime.utcnow(),
                        execution_id
                    ))
                    conn.commit()
                    
                    logger.info(f"[TRACKING] Completed workflow execution: {execution_id} (success={success})")
                    return True
                
        except Exception as e:
            logger.error(f"[TRACKING] Failed to complete workflow execution {execution_id}: {e}")
            return False
    
    
    def insert_workflow_execution(self, tracking_data: Dict[str, Any]) -> bool:
        """
        Insert workflow execution record.
        
        Args:
            tracking_data: Dict from serialize_state_for_db()
                - request_id (str)
                - tenant_id (int) - HIGH-CARDINALITY
                - user_id (int) - HIGH-CARDINALITY
                - session_id (str)
                - intent (str)
                - total_duration_ms (float)
                - llm_tokens_total (int)
                - llm_cost_usd (float)
                - tool_calls_count (int)
                - chunks_retrieved_count (int)
                - success (bool)
                - error_message (str | None)
        
        Returns:
            bool: True if inserted successfully
        """
        conn = None
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                insert_sql = f"""
                    INSERT INTO {self.table_name} (
                        request_id, tenant_id, user_id, session_id,
                        query_original, query_rewritten, query_intent,
                        intent, total_duration_ms,
                        llm_tokens_total, llm_cost_usd,
                        tool_calls_count, chunks_retrieved_count,
                        success, error_message, created_at
                    ) VALUES (
                        %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s, %s
                    )
                    ON CONFLICT (request_id) DO NOTHING
                """
                
                cur.execute(insert_sql, (
                    tracking_data["request_id"],
                    tracking_data["tenant_id"],
                    tracking_data["user_id"],
                    tracking_data["session_id"],
                    tracking_data.get("query_original"),
                    tracking_data.get("query_rewritten"),
                    tracking_data.get("query_intent"),
                    tracking_data.get("intent", "unknown"),
                    tracking_data.get("total_duration_ms", 0),
                    tracking_data.get("llm_tokens_total", 0),
                    tracking_data.get("llm_cost_usd", 0.0),
                    tracking_data.get("tool_calls_count", 0),
                    tracking_data.get("chunks_retrieved_count", 0),
                    tracking_data.get("success", True),
                    tracking_data.get("error_message"),
                    tracking_data.get("created_at", datetime.utcnow())
                ))
                conn.commit()
                
                logger.debug(
                    f"✅ Workflow execution tracked: {tracking_data['request_id']} "
                    f"(tenant={tracking_data['tenant_id']}, user={tracking_data['user_id']})"
                )
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to insert workflow execution: {e}", exc_info=True)
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def get_tenant_usage_summary(
        self, 
        tenant_id: int, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate usage statistics for a tenant.
        
        Example query:
        - Total workflows executed
        - Total tokens consumed
        - Total cost (USD)
        - Average duration
        - Success rate
        
        Args:
            tenant_id: Tenant identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            Dict with aggregated metrics
        """
        conn = None
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                filters = ["tenant_id = %s"]
                params = [tenant_id]
                
                if start_date:
                    filters.append("created_at >= %s")
                    params.append(start_date)
                
                if end_date:
                    filters.append("created_at <= %s")
                    params.append(end_date)
                
                where_clause = " AND ".join(filters)
                
                query_sql = f"""
                    SELECT
                        COUNT(*) as total_executions,
                        SUM(llm_tokens_total) as total_tokens,
                        SUM(llm_cost_usd) as total_cost_usd,
                        AVG(total_duration_ms) as avg_duration_ms,
                        COUNT(CASE WHEN success = true THEN 1 END)::float / COUNT(*) as success_rate,
                        SUM(tool_calls_count) as total_tool_calls,
                        SUM(chunks_retrieved_count) as total_chunks_retrieved
                    FROM {self.table_name}
                    WHERE {where_clause}
                """
                
                cur.execute(query_sql, params)
                row = cur.fetchone()
                
                if not row:
                    return {}
                
                return {
                    "tenant_id": tenant_id,
                    "total_executions": row[0] or 0,
                    "total_tokens": row[1] or 0,
                    "total_cost_usd": float(row[2] or 0.0),
                    "avg_duration_ms": float(row[3] or 0.0),
                    "success_rate": float(row[4] or 0.0),
                    "total_tool_calls": row[5] or 0,
                    "total_chunks_retrieved": row[6] or 0,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get tenant usage summary: {e}", exc_info=True)
            return {}
        finally:
            if conn:
                conn.close()
    
    def get_user_usage_summary(
        self,
        tenant_id: int,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Aggregate usage statistics for a specific user.
        
        Similar to get_tenant_usage_summary but filtered by user_id.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            start_date: Optional start date filter
            end_date: Optional end date filter
        
        Returns:
            Dict with aggregated metrics
        """
        conn = None
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                filters = ["tenant_id = %s", "user_id = %s"]
                params = [tenant_id, user_id]
                
                if start_date:
                    filters.append("created_at >= %s")
                    params.append(start_date)
                
                if end_date:
                    filters.append("created_at <= %s")
                    params.append(end_date)
                
                where_clause = " AND ".join(filters)
                
                query_sql = f"""
                    SELECT
                        COUNT(*) as total_executions,
                        SUM(llm_tokens_total) as total_tokens,
                        SUM(llm_cost_usd) as total_cost_usd,
                        AVG(total_duration_ms) as avg_duration_ms,
                        COUNT(CASE WHEN success = true THEN 1 END)::float / COUNT(*) as success_rate,
                        intent,
                        COUNT(*) as count_per_intent
                    FROM {self.table_name}
                    WHERE {where_clause}
                    GROUP BY intent
                """
                
                cur.execute(query_sql, params)
                rows = cur.fetchall()
                
                if not rows:
                    return {}
                
                # Aggregate by intent
                intent_breakdown = []
                total_executions = 0
                total_tokens = 0
                total_cost = 0.0
                
                for row in rows:
                    intent_breakdown.append({
                        "intent": row[5],
                        "count": row[6]
                    })
                    total_executions += row[0]
                    total_tokens += row[1] or 0
                    total_cost += float(row[2] or 0.0)
                
                return {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "total_executions": total_executions,
                    "total_tokens": total_tokens,
                    "total_cost_usd": total_cost,
                    "intent_breakdown": intent_breakdown,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get user usage summary: {e}", exc_info=True)
            return {}
        finally:
            if conn:
                conn.close()
    
    def get_recent_failures(
        self,
        tenant_id: Optional[int] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent failed workflow executions for debugging.
        
        Args:
            tenant_id: Optional tenant filter
            limit: Max number of records to return
        
        Returns:
            List of failed execution records
        """
        conn = None
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                if tenant_id:
                    query_sql = f"""
                        SELECT
                            request_id, tenant_id, user_id, session_id,
                            intent, total_duration_ms, error_message, created_at
                        FROM {self.table_name}
                        WHERE success = false AND tenant_id = %s
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cur.execute(query_sql, (tenant_id, limit))
                else:
                    query_sql = f"""
                        SELECT
                            request_id, tenant_id, user_id, session_id,
                            intent, total_duration_ms, error_message, created_at
                        FROM {self.table_name}
                        WHERE success = false
                        ORDER BY created_at DESC
                        LIMIT %s
                    """
                    cur.execute(query_sql, (limit,))
                
                rows = cur.fetchall()
                
                failures = []
                for row in rows:
                    failures.append({
                        "request_id": row[0],
                        "tenant_id": row[1],
                        "user_id": row[2],
                        "session_id": row[3],
                        "intent": row[4],
                        "total_duration_ms": row[5],
                        "error_message": row[6],
                        "created_at": row[7].isoformat() if row[7] else None
                    })
                
                return failures
                
        except Exception as e:
            logger.error(f"❌ Failed to get recent failures: {e}", exc_info=True)
            return []
        finally:
            if conn:
                conn.close()
    
    # ===== NODE-LEVEL TRACKING (Runtime-configurable) =====
    
    async def insert_node_execution_async(
        self,
        execution_id: str,
        node_name: str,
        node_index: int,
        duration_ms: float,
        status: str = "success",
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        state_snapshot: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Insert node execution record (async background task).
        
        Args:
            execution_id: Workflow execution ID (request_id)
            node_name: Node identifier (e.g. "agent_decide")
            node_index: Node execution order (0-based)
            duration_ms: Node execution duration
            status: "success" | "error" | "skipped"
            error_message: Error message if failed
            metadata: Node-specific metadata (METADATA_ONLY level)
                - llm_tokens, llm_model, tool_name, cache_hit, etc.
            state_snapshot: Full state (FULL_STATE level, optional)
        
        Returns:
            bool: Success status
        
        Note: This is an async wrapper. The actual DB write is synchronous.
        """
        return await asyncio.to_thread(
            self._insert_node_execution_sync,
            execution_id,
            node_name,
            node_index,
            duration_ms,
            status,
            error_message,
            metadata,
            state_snapshot
        )
    
    def _insert_node_execution_sync(
        self,
        execution_id: str,
        node_name: str,
        node_index: int,
        duration_ms: float,
        status: str,
        error_message: Optional[str],
        metadata: Optional[Dict[str, Any]],
        state_snapshot_before: Optional[Dict[str, Any]] = None,
        state_snapshot_after: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Synchronous node execution insert (called from async wrapper)."""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    insert_sql = """
                        INSERT INTO node_executions (
                            execution_id, node_name, node_index,
                            duration_ms, status, error_message,
                            metadata, state_before, state_after, created_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """
                    
                    cur.execute(insert_sql, (
                        execution_id,
                        node_name,
                        node_index,
                        duration_ms,
                        status,
                        error_message,
                        psycopg2.extras.Json(_serialize_for_jsonb(metadata)) if metadata else None,
                        psycopg2.extras.Json(_serialize_for_jsonb(state_snapshot_before)) if state_snapshot_before else None,
                        psycopg2.extras.Json(_serialize_for_jsonb(state_snapshot_after)) if state_snapshot_after else None,
                        datetime.utcnow()
                    ))
                    conn.commit()
                    
                    logger.info(
                        f"✅ Node execution recorded: {execution_id} / {node_name} "
                        f"(idx={node_index}, dur={duration_ms:.0f}ms, status={status})"
                    )
                    return True
                
        except Exception as e:
            logger.error(f"❌ Failed to insert node execution: {e}", exc_info=True)
            return False
    
    # ===== API QUERY METHODS =====
    
    async def get_execution_by_id(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow execution by ID for API endpoints."""
        try:
            return await asyncio.to_thread(self._get_execution_by_id_sync, execution_id)
        except RuntimeError:
            # Fallback to sync execution if no event loop
            return self._get_execution_by_id_sync(execution_id)
    
    def _get_execution_by_id_sync(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous execution lookup."""
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    query_sql = f"""
                        SELECT
                            execution_id, session_id, tenant_id, user_id,
                            query_original as query, query_rewritten, query_intent,
                            created_at as started_at, completed_at, total_duration_ms as duration_ms, status,
                            null as final_answer, error_message,
                            0 as total_nodes_executed, 0 as iteration_count, 0 as reflection_count,
                            null as tools_called, null as final_state,
                            llm_tokens_total, llm_cost_usd,
                            request_id, null as trace_id
                        FROM workflow_executions
                        WHERE execution_id = %s
                    """
                    
                    cur.execute(query_sql, (execution_id,))
                    row = cur.fetchone()
                    
                    if row:
                        return dict(row)
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to get execution {execution_id}: {e}")
            return None
    
    async def get_executions_filtered(
        self,
        filters: Dict[str, Any],
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get workflow executions with filtering."""
        try:
            return await asyncio.to_thread(self._get_executions_filtered_sync, filters, limit, offset)
        except RuntimeError:
            # Fallback to sync execution if no event loop
            return self._get_executions_filtered_sync(filters, limit, offset)
    
    def _get_executions_filtered_sync(
        self,
        filters: Dict[str, Any],
        limit: int,
        offset: int
    ) -> List[Dict[str, Any]]:
        """Synchronous filtered executions query."""
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    where_conditions = []
                    params = []
                    
                    for key, value in filters.items():
                        where_conditions.append(f"{key} = %s")
                        params.append(value)
                    
                    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                    
                    query_sql = f"""
                        SELECT
                            execution_id, session_id, tenant_id, user_id,
                            query_original as query, query_rewritten, query_intent,
                            created_at as started_at, completed_at, total_duration_ms as duration_ms, status,
                            null as final_answer, error_message,
                            0 as total_nodes_executed, 0 as iteration_count, 0 as reflection_count,
                            null as tools_called, null as final_state,
                            llm_tokens_total, llm_cost_usd,
                            request_id, null as trace_id
                        FROM workflow_executions
                        WHERE {where_clause}
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                    """
                    
                    params.extend([limit, offset])
                    cur.execute(query_sql, params)
                    rows = cur.fetchall()
                    
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            logger.error(f"Failed to get filtered executions: {e}")
            return []
    
    async def get_node_executions(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get node executions for a workflow."""
        try:
            return await asyncio.to_thread(self._get_node_executions_sync, execution_id)
        except RuntimeError:
            # Fallback to sync execution if no event loop
            return self._get_node_executions_sync(execution_id)
    
    def _get_node_executions_sync(self, execution_id: str) -> List[Dict[str, Any]]:
        """Synchronous node executions query."""
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    query_sql = """
                        SELECT
                            id as node_execution_id, execution_id, node_name, node_index,
                            COALESCE(
                                (metadata->>'started_at')::timestamptz,
                                created_at
                            ) as started_at,
                            COALESCE(
                                (metadata->>'completed_at')::timestamptz,
                                CASE WHEN status = 'success' THEN created_at + (duration_ms || ' milliseconds')::INTERVAL ELSE NULL END
                            ) as completed_at,
                            duration_ms, status, error_message,
                            state_before,
                            state_after,
                            '{}'::jsonb as state_diff,
                            metadata,
                            metadata->>'parent_node' as parent_node
                        FROM node_executions
                        WHERE execution_id = %s
                        ORDER BY 
                            COALESCE((metadata->>'started_at')::timestamptz, created_at) ASC,
                            node_index ASC
                    """
                    
                    cur.execute(query_sql, (execution_id,))
                    rows = cur.fetchall()
                    
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            logger.error(f"Failed to get node executions for {execution_id}: {e}")
            return []


# Singleton instance for global import
workflow_tracking_repo = WorkflowTrackingRepository()
