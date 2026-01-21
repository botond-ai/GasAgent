"""Debug script to test agent."""
import sys
from dotenv import load_dotenv
load_dotenv()

from src.agent.graph import create_graph

# Create graph
print("Creating graph...")
graph = create_graph()

# Initialize state
initial_state = {
    "user_prompt": "milyen idő van most Pécsett?",
    "tool_results": [],
    "iteration_count": 0,
    "decision": None,
    "final_answer": None
}

print("Running agent...")
print("=" * 60)

# Run the graph with streaming
for i, state in enumerate(graph.stream(initial_state)):
    print(f"\n--- Step {i+1} ---")
    for key, value in state.items():
        if key == "decision" and value:
            print(f"  {key}: action={value.get('decision').action if isinstance(value.get('decision'), dict) else value.get('decision')}")
        elif key == "tool_results" and value:
            results = value.get('tool_results', [])
            print(f"  {key}: {len(results)} results")
            if results:
                latest = results[-1]
                print(f"    Latest: {latest.tool_name} - success={latest.success}")
        elif key == "final_answer" and value:
            print(f"  {key}: {value.get('final_answer')}")
        elif key == "iteration_count":
            print(f"  {key}: {value.get('iteration_count', 0)}")

print("\n" + "=" * 60)
print("DONE")
