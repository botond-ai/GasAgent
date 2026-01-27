from typing import List, Dict, Any

class ExecutorLoop:
    """
    A node responsible for executing steps in a structured plan.
    Handles retries, failure handling, and state updates.
    """
    def run(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        state = {}
        for step in plan:
            retries = 3
            while retries > 0:
                try:
                    self.execute_step(step, state)
                    break  # Exit retry loop on success
                except Exception as e:
                    retries -= 1
                    self.log_failure(step, e, retries)
                    if retries == 0:
                        raise e  # Re-raise after exhausting retries
        return state

    def log_failure(self, step: Dict[str, Any], error: Exception, retries_left: int):
        """
        Log failure details for debugging.
        """
        print(f"Failed to execute step: {step}. Error: {error}. Retries left: {retries_left}")

    def execute_step(self, step: Dict[str, Any], state: Dict[str, Any]):
        """
        Execute a single step in the plan.
        """
        if not isinstance(step, dict):
            print(f"Skipping invalid step: Expected dictionary, got {type(step).__name__}")
            return

        action = step["action"]
        params = step.get("params", {})
        # Route to the correct node or tool based on action
        if action == "fetch_data":
            state["data"] = self.fetch_data(params)
        elif action == "process_data":
            state["processed_data"] = self.process_data(state["data"], params)
        elif action == "store_results":
            self.store_results(state["processed_data"], params)

    def fetch_data(self, params: Dict[str, Any]) -> Any:
        """
        Fetch data from a source.
        """
        # Example implementation
        return {"example_key": "example_value"}

    def process_data(self, data: Any, params: Dict[str, Any]) -> Any:
        """
        Process data using a specified method.
        """
        # Example implementation
        return {"processed_key": "processed_value"}

    def store_results(self, processed_data: Any, params: Dict[str, Any]):
        """
        Store processed data in a destination.
        """
        # Example implementation
        print("Results stored successfully.")