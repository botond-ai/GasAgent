# Quickstart - MeetingAI

1. Create a Python 3.11 virtual environment and install dependencies:

```bash
python -m venv .venv
# Linux / macOS
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Run the backend (development):

```bash
uvicorn backend.main:app --reload --port 8000
```

3. Example requests (Linux/macOS):

- Summarize:

```bash
curl -X POST http://127.0.0.1:8000/summarize \
  -H "Content-Type: application/json" \
  -d "{ \"transcript\": \"$(cat data/example_transcript.txt)\", \"title\": \"Q4 Sprint Planning\" }"
```

- Extract tasks:

```bash
curl -X POST http://127.0.0.1:8000/extract_tasks \
  -H "Content-Type: application/json" \
  -d "{ \"transcript\": \"$(cat data/example_transcript.txt)\", \"meeting_reference\": \"MTG-2025-12-09-001\" }"
```

Windows PowerShell users can replace `$(cat ...)` with `Get-Content -Raw data\example_transcript.txt` or paste the transcript into the JSON body.

Notes:
- If `OPENAI_API_KEY` is set and the `openai` package is installed, the backend will attempt a simple OpenAI call; otherwise the service returns mock data for local testing.
