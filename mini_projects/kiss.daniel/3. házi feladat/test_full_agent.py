"""Full debug test for Roglán query."""
import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from src.agent.graph import run_agent

print("Full agent test: 'milyen lesz az időjárás holnap Roglán?'\n")

try:
    answer = run_agent("milyen lesz az időjárás holnap Roglán?")
    print(f"Answer: {answer}")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
