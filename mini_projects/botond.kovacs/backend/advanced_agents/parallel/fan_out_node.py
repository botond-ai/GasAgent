from langgraph import Node
from typing import List, Dict, Any
import threading

class FanOutNode(Node):
    """
    A node that triggers multiple independent nodes simultaneously.
    """
    def run(self, input_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = []
        threads = []

        def execute_task(task_input):
            result = self.execute_task(task_input)
            results.append(result)

        for task_input in input_data.get("tasks", []):
            thread = threading.Thread(target=execute_task, args=(task_input,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        return results

    def execute_task(self, task_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single task. Override this method for custom logic.
        """
        # Example implementation
        return {"task": task_input, "status": "completed"}