import json
from pathlib import Path

# Load transcript
transcript = Path("data/example_transcript.txt").read_text()

# Import and test the llm module
from backend.services import llm
result = llm.analyze_transcript(transcript)

print("LLM Result:")
print(json.dumps(result, indent=2, ensure_ascii=False))

# Now test the Pydantic model
from backend.domain.models import MeetingSummary
summary = MeetingSummary(
    meeting_id="MTG-test",
    title="Q4 Sprint Planning",
    date="2025-12-09",
    participants=["János", "Péter", "Maria"],
    summary=result.get("summary"),
    key_decisions=result.get("key_decisions", []),
    next_steps=result.get("next_steps", []),
)

print("\nMeetingSummary Model:")
print(summary.model_dump_json(indent=2))
