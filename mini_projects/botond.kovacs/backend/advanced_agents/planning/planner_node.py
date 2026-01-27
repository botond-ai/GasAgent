from typing import List, Dict, Any
from datetime import datetime

class PlannerNode:
    """
    A node responsible for generating a structured execution plan.
    Outputs a dictionary with messages, next action, tools called, iteration count, memory, and plan.
    """
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a structured execution plan and return it in the expected state format.
        """
        plan = self.generate_plan(input_data)
        memory = input_data.get("memory")

        # Deep serialization of nested objects, including datetime handling
        def deep_serialize(obj):
            if isinstance(obj, dict):
                return {k: deep_serialize(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [deep_serialize(v) for v in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()  # Serialize datetime to ISO 8601 string
            elif hasattr(obj, "dict"):
                return deep_serialize(obj.dict())
            return obj

        serialized_memory = deep_serialize(memory.dict()) if memory else {}

        # Debugging: Log the state structure
        import logging
        logger = logging.getLogger(__name__)
        logger.debug("PlannerNode state: %s", {
            "messages": input_data.get("messages", []),
            "next_action": "call_tool",
            "tools_called": [],
            "iteration_count": input_data.get("iteration_count", 0),
            "memory": serialized_memory,
            "plan": plan
        })

        # Debugging: Log the state being returned
        state = {
            "messages": input_data.get("messages", []),
            "next_action": "call_tool",  # Default next action
            "tools_called": [],
            "iteration_count": input_data.get("iteration_count", 0),
            "memory": serialized_memory,
            "current_user_id": input_data.get("current_user_id", None),
            "tool_decision": input_data.get("tool_decision", None)  # Restore tool_decision
        }

        # Remove tool_decision if it is None
        if state["tool_decision"] is None:
            del state["tool_decision"]

        logger.debug("State being returned by PlannerNode: %s", state)

        # Debugging: Log the state before returning
        logger.debug("State being returned by PlannerNode: %s", state)

        # Log the state before validation
        logger.debug("State before validation in PlannerNode: %s", {
            "messages": input_data.get("messages", []),
            "next_action": "call_tool",  # Default next action
            "tools_called": [],
            "iteration_count": input_data.get("iteration_count", 0),
            "memory": serialized_memory
        })

        # Validate state structure before returning
        required_keys = ["messages", "memory", "tools_called", "current_user_id", "next_action", "iteration_count"]  # Adjusted required keys
        for key in required_keys:
            if key not in state:
                raise ValueError(f"PlannerNode returned invalid state: Missing key '{key}'")
        return state

    def generate_plan(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate a structured execution plan based on input data.
        """
        # Example: Replace with actual LLM call or logic
        return [
            {"step": 1, "action": "fetch_data", "params": {"source": "api1"}},
            {"step": 2, "action": "process_data", "params": {"method": "aggregation"}},
            {"step": 3, "action": "store_results", "params": {"destination": "db"}}
        ]