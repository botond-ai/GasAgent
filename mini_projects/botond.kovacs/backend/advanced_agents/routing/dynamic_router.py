from langgraph import Node
from typing import Dict, Any, List

class DynamicRouter(Node):
    """
    A node that decides at runtime which nodes/tools should be executed.
    Routing decisions are explainable and logged.
    """
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        routing_plan = self.generate_routing_plan(input_data)
        self.log_routing_decision(routing_plan)
        return routing_plan

    def generate_routing_plan(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a routing plan based on input data.
        """
        # Example: Replace with actual LLM call or logic
        if input_data.get("type") == "parallel":
            return {
                "next_nodes": ["node_a", "node_b"],
                "execution_mode": "parallel"
            }
        else:
            return {
                "next_nodes": ["node_c"],
                "execution_mode": "sequential"
            }

    def log_routing_decision(self, routing_plan: Dict[str, Any]):
        """
        Log the routing decision for explainability.
        """
        print(f"Routing decision: {routing_plan}")