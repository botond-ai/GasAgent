from langgraph import Node
from typing import List, Dict, Any

class FanInNode(Node):
    """
    A node that waits for all parallel executions and merges results deterministically.
    """
    def run(self, parallel_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.aggregate_results(parallel_results)

    def aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate results from parallel nodes.
        """
        aggregated = {}
        for result in results:
            for key, value in result.items():
                if key not in aggregated:
                    aggregated[key] = []
                aggregated[key].append(value)
        return aggregated