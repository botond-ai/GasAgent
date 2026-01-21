"""Main CLI entry point for the AI weather agent."""
import sys
import os
from dotenv import load_dotenv

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.graph import run_agent


def main():
    """Main entry point for the CLI application."""
    # Load environment variables
    load_dotenv()
    
    # Check if user prompt is provided as command line argument
    if len(sys.argv) > 1:
        # Use command line arguments
        user_prompt = " ".join(sys.argv[1:])
    else:
        # Read from stdin
        print("Add meg a kérdésed (vagy Ctrl+D / Ctrl+C a kilépéshez):")
        try:
            user_prompt = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nViszlát!")
            sys.exit(0)
    
    if not user_prompt:
        print("Hiba: Nem adtál meg kérdést.")
        sys.exit(1)
    
    # Run the agent
    try:
        answer = run_agent(user_prompt)
        print(answer)
    except Exception as e:
        print(f"Hiba történt: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
