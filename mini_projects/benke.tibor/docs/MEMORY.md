# Memory Strategies (v2.6)

This project implements lightweight conversation memory on top of the LangGraph pipeline:

- Rolling Window: keeps the last N messages (config: `MEMORY_MAX_MESSAGES`, default `8`).
- Conversation Summary: LLM-generated 3–4 sentence summary, updated when needed.
- Facts Store: extracts up to 5 atomic facts as short bullet points for future reference.

## How it works

A new `memory_update` node runs at the end of the pipeline:

```
intent → retrieval → generation → guardrail → feedback_metrics → execute_workflow → memory_update → END
```

- Messages are deduplicated with a SHA256-based reducer (role+normalized content).
- The rolling window trims the `messages` to the last N entries.
- The summary is refreshed when the window fills or no summary exists.
- Facts are extracted as one-line bullets and deduplicated.
- All operations are non-blocking: failures are logged and ignored.

## Configuration

Set via environment variables:

```bash
# OpenAI provider
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini

# Memory settings
MEMORY_MAX_MESSAGES=8
```

## Testing

Run the memory tests only:

```powershell
python -m pytest backend/tests/test_memory.py -v --tb=short --no-cov
```

Or the full integration suite:

```powershell
python -m pytest backend/tests/test_integration_v2_5.py -v --tb=short --no-cov
```
