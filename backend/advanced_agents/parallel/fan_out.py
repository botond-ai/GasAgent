"""
Fan-Out Node - Spawns parallel tasks for concurrent execution.

This module implements the "fan-out" pattern for parallel execution.

WHY Fan-Out?
- Execute multiple independent tasks simultaneously
- Reduce overall latency (3 sequential 1s tasks = 3s, parallel = 1s)
- Better resource utilization
- Essential for real-world AI workflows (gather data from multiple sources)

HOW it works:
1. Receives list of tasks to execute in parallel
2. Identifies independent tasks (no dependencies)
3. Spawns each as separate execution path
4. LangGraph handles actual parallel execution
5. Each parallel branch updates state independently

CRITICAL: LangGraph Parallelism
- LangGraph doesn't execute nodes in parallel by default
- We use Send() API to spawn parallel branches
- Each Send() creates independent execution path
- Reducers merge results when branches converge

Following SOLID:
- Single Responsibility: Only task spawning, not execution
- Open/Closed: Easy to add new spawning strategies
"""

import logging
from typing import Dict, Any, List

from ..state import AdvancedAgentState, ParallelTask

logger = logging.getLogger(__name__)


class FanOutNode:
    """
    LangGraph node that spawns parallel execution branches.
    
    This node:
    1. Reads parallel_tasks from state
    2. Validates task independence (no shared dependencies)
    3. Prepares task-specific state for each branch
    4. Returns routing instructions for LangGraph
    
    NOTE: Actual parallel execution happens via LangGraph's Send() API
    in the graph builder, not in this node directly.
    """
    
    def __init__(self):
        """Initialize fan-out node."""
        pass
    
    async def __call__(self, state: AdvancedAgentState) -> Dict[str, Any]:
        """
        Prepare parallel tasks for execution.
        
        WHY not execute here?
        - LangGraph handles parallelism at graph level
        - Node emits instructions, graph executes them
        - Separation of concerns: node = logic, graph = orchestration
        
        Args:
            state: Current agent state with parallel_tasks
            
        Returns:
            Updated state marking parallel execution as active
        """
        tasks = state.get("parallel_tasks", [])
        
        if not tasks:
            logger.warning("[FAN-OUT] No tasks to fan out")
            return {
                "parallel_execution_active": False,
                "debug_logs": ["[FAN-OUT] No parallel tasks to execute"]
            }
        
        logger.info(f"[FAN-OUT] Fanning out {len(tasks)} tasks")
        
        # Validate task independence
        if not self._tasks_are_independent(tasks):
            logger.error("[FAN-OUT] Tasks have circular dependencies!")
            return {
                "parallel_execution_active": False,
                "debug_logs": ["[FAN-OUT] ✗ Cannot execute - tasks have dependencies"]
            }
        
        # Log task details
        task_names = [f"{t.tool_name}({t.task_id})" for t in tasks]
        logger.info(f"[FAN-OUT] Tasks: {', '.join(task_names)}")
        
        return {
            "parallel_execution_active": True,
            "debug_logs": [
                f"[FAN-OUT] ✓ Spawning {len(tasks)} parallel tasks",
                f"[FAN-OUT] Tasks: {', '.join(task_names)}"
            ]
        }
    
    def _tasks_are_independent(self, tasks: List[ParallelTask]) -> bool:
        """
        Verify that tasks can run in parallel (no inter-dependencies).
        
        WHY important?
        - Parallel execution assumes tasks don't depend on each other
        - Dependencies would cause race conditions
        - Educational: shows importance of task independence
        
        Args:
            tasks: List of tasks to validate
            
        Returns:
            True if tasks are independent
        """
        # For parallel tasks, we assume they're independent
        # In a more sophisticated system, we'd check for:
        # - Shared mutable state
        # - Data dependencies
        # - Resource conflicts
        
        # Simple check: all tasks should have unique task_ids
        task_ids = [t.task_id for t in tasks]
        return len(task_ids) == len(set(task_ids))
    
    def create_parallel_tasks(
        self,
        task_definitions: List[Dict[str, Any]]
    ) -> List[ParallelTask]:
        """
        Helper to create ParallelTask objects from definitions.
        
        WHY helper method?
        - Makes it easy to create tasks in other nodes
        - Validates task structure
        - Centralized task creation logic
        
        Args:
            task_definitions: List of task specs
            
        Returns:
            List of validated ParallelTask objects
        """
        tasks = []
        for i, task_def in enumerate(task_definitions):
            task = ParallelTask(
                task_id=task_def.get("task_id", f"task_{i}"),
                task_type=task_def.get("task_type", "api_call"),
                tool_name=task_def["tool_name"],
                arguments=task_def.get("arguments", {}),
                timeout_seconds=task_def.get("timeout_seconds", 30.0)
            )
            tasks.append(task)
        
        return tasks
