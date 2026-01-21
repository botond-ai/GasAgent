"""Direct test of agent graph."""
import sys
from dotenv import load_dotenv
load_dotenv()

from src.agent.graph import create_graph

# Create graph
graph = create_graph()

# Initialize state
initial_state = {
    "user_prompt": "milyen idő van most Pécsett?",
    "tool_results": [],
    "iteration_count": 0,
    "decision": None,
    "final_answer": None
}

print("Starting agent execution...")
print("=" * 60)

# Run with streaming to see each step
try:
    for i, output in enumerate(graph.stream(initial_state)):
        print(f"\n--- Step {i+1}: {list(output.keys())[0]} ---")
        state = list(output.values())[0]
        
        # Print decision
        if 'decision' in state and state['decision']:
            dec = state['decision']
            print(f"  Action: {dec.action}")
            if hasattr(dec, 'tool_name') and dec.tool_name:
                print(f"  Tool: {dec.tool_name}")
                print(f"  Input: {dec.tool_input}")
        
        # Print tool results
        if 'tool_results' in state and state['tool_results']:
            latest = state['tool_results'][-1]
            print(f"  Last tool: {latest.tool_name}")
            print(f"  Success: {latest.success}")
            if latest.success:
                print(f"  Data keys: {list(latest.data.keys()) if latest.data else None}")
            else:
                print(f"  Error: {latest.error_message}")
        
        # Print final answer
        if 'final_answer' in state and state['final_answer']:
            print(f"  ANSWER: {state['final_answer']}")
        
        print(f"  Iteration: {state.get('iteration_count', 0)}")
        
        if i >= 10:  # Safety limit
            print("\nSTOPPED: Too many iterations!")
            break
            
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Done!")
