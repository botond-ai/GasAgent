import os
import uuid
from typing import Any, Dict

try:
    import openai
except Exception:
    openai = None


def analyze_transcript(transcript: str) -> Dict[str, Any]:
    """Analyze transcript and return a dict with keys: summary, key_decisions, next_steps, tasks.

    If `OPENAI_API_KEY` is set and `openai` is importable, a simple OpenAI completion is attempted.
    Otherwise a mock response is returned.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key and openai:
        openai.api_key = api_key
        prompt = (
            "Extract an executive summary, key decisions, next steps, and action items as JSON with keys"
            ": summary, key_decisions, next_steps, tasks. Return valid JSON only. Transcript:\n\n"
            + transcript
        )
        try:
            resp = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=700)
            text = resp.choices[0].text.strip()
            import json

            return json.loads(text)
        except Exception:
            # fall through to mock
            pass

    # Mock fallback
    task_id = f"TASK-{uuid.uuid4().hex[:6]}"
    return {
        "summary": "Mock summary generated from transcript.",
        "key_decisions": ["Decision A"],
        "next_steps": ["Follow up with team."],
        "tasks": [
            {
                "task_id": task_id,
                "title": "Mock task extracted from transcript",
                "assignee": None,
                "due_date": None,
                "priority": None,
                "status": "to-do",
                "meeting_reference": None,
            }
        ],
    }
