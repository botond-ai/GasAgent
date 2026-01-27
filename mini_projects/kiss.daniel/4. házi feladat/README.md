# Meeting Notes Agent

A production-ready LangGraph AI agent that processes meeting notes, extracts key information, and creates Google Calendar events.

## Features

- 📝 **Meeting Summarization**: Extracts decisions, action items, and open questions
- 📅 **Event Extraction**: Identifies next meeting details from notes
- 🗓️ **Google Calendar Integration**: Automatically creates calendar events
- 🔒 **Safety Guardrails**: Validates data before creating events
- 🔄 **Deduplication**: Prevents duplicate event creation
- 🤖 **Multi-Model Support**: Different models for different tasks (Planner, Extractor, Summarizer)

## Architecture

The agent follows a 4-layer architecture:

1. **Reasoning Layer** - LLM decisions, prompting, routing
2. **Operational Layer** - LangGraph workflow, state management
3. **Tool Execution Layer** - External APIs (Google Calendar)
4. **Memory Layer** - Deduplication, context handling

### Workflow

```
User Input → Planner → Router ─┬→ Summarizer → Router
                  ↑            ├→ Extractor → Router
                  │            ├→ Validator → Router
                  │            ├→ Guardrail → Router
                  │            ├→ Tool → Router
                  │            └→ Final Answer → END
                  │
                  └── (replan) ──┘
```

## Installation

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) running locally
- Google Calendar API credentials (for calendar integration)

### Setup

1. **Clone the repository**
```bash
git clone <repo-url>
cd hw4
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings
```

5. **Pull Ollama models**
```bash
ollama pull qwen2.5:14b-instruct
ollama pull llama3.1:8b
ollama pull mxbai-embed-large:latest
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API URL |
| `OLLAMA_TIMEOUT_S` | `60` | Request timeout in seconds |
| `OLLAMA_TEMPERATURE` | `0.2` | LLM temperature |
| `AGENT_PROFILE` | `BALANCED` | Profile: FAST, BALANCED, QUALITY |
| `GOOGLE_CALENDAR_ID` | `primary` | Calendar to create events in |
| `APP_TIMEZONE` | `Europe/Budapest` | Default timezone |
| `LOG_LEVEL` | `INFO` | Logging level |

### Agent Profiles

| Profile | Planner/Extractor | Summarizer/Final | Use Case |
|---------|-------------------|------------------|----------|
| `QUALITY` | gpt-oss:20b | gpt-oss:20b / llama3.1:8b | Best quality, slower |
| `BALANCED` | qwen2.5:14b-instruct | llama3.1:8b | Good balance |
| `FAST` | phi3.5:latest | llama3.2:3b | Quick results |

### Google Calendar Setup

#### Option 1: Service Account (Recommended for servers)

1. Create a service account in Google Cloud Console
2. Download the JSON key file
3. Set in `.env`:
```env
GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
```

#### Option 2: OAuth (For personal accounts)

1. Create OAuth credentials in Google Cloud Console
2. Set in `.env`:
```env
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

## Usage

### Command Line

```bash
# Process notes from command line
python -m app.main --notes "Meeting notes here..."

# Process notes from file
python -m app.main --notes-file meeting.txt

# Dry run (don't create calendar event)
python -m app.main --notes "..." --dry-run

# Output as JSON
python -m app.main --notes "..." --json

# With custom timezone
python -m app.main --notes "..." --timezone "America/New_York"

# Verbose logging
python -m app.main --notes "..." --verbose
```

### CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--notes` | `-n` | Meeting notes text |
| `--notes-file` | `-f` | Path to notes file |
| `--calendar-id` | `-c` | Google Calendar ID |
| `--timezone` | `-t` | Timezone (default: Europe/Budapest) |
| `--dry-run` | `-d` | Don't create calendar event |
| `--json` | `-j` | Output as JSON |
| `--mock-calendar` | | Use mock calendar |
| `--skip-validation` | | Skip Ollama model validation |
| `--verbose` | `-v` | Enable verbose logging |

## Example

### Input

```
Product Review Meeting - January 15, 2026

Participants: Alice (PM), Bob (Dev Lead), Carol (Design)

DECISIONS:
- We will release v2.1 on January 28th
- The new pricing page will be postponed to v2.2

ACTION ITEMS:
- Alice: Prepare release notes by Jan 24
- Bob: Finalize API documentation by Jan 22

NEXT MEETING:
The next sprint planning will be on Tuesday, January 20, 2026 at 10:00 AM.
Location: Conference Room B
Duration: 1 hour
Attendees: alice@company.com, bob@company.com, carol@company.com
```

### Output

```
============================================================
🤖 MEETING NOTES AGENT - FINAL ANSWER
============================================================
Run ID: abc12345-6789-...
Status: ✅ Success

📝 SUMMARY
----------------------------------------
Product review meeting covering Sprint 23 deliverables and v2.1 release 
planning. Key decisions made about release timing and feature scope.

📌 DECISIONS
----------------------------------------
  • Release v2.1 on January 28th
  • Postpone pricing page to v2.2

✅ ACTION ITEMS
----------------------------------------
  • Prepare release notes
    Owner: Alice | Due: Jan 24
  • Finalize API documentation
    Owner: Bob | Due: Jan 22

📅 EXTRACTED EVENT DETAILS
----------------------------------------
  Title: Sprint Planning
  Start: 2026-01-20 10:00:00
  End: 2026-01-20 11:00:00
  Timezone: Europe/Budapest
  Location: Conference Room B
  Attendees: alice@company.com, bob@company.com, carol@company.com
  Confidence: 95%

📆 CALENDAR EVENT
----------------------------------------
  ✅ Event created successfully!
  Event ID: abc123xyz
  Link: https://calendar.google.com/event?eid=abc123xyz

============================================================
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_agent.py

# Run with verbose output
pytest -v
```

## Project Structure

```
app/
├── __init__.py
├── config.py           # Settings and configuration
├── main.py             # CLI entry point
├── agent/
│   ├── __init__.py
│   ├── graph.py        # LangGraph workflow
│   ├── nodes.py        # Node implementations
│   ├── prompts.py      # LLM prompts
│   └── state.py        # Pydantic state models
├── llm/
│   ├── __init__.py
│   └── ollama_client.py # Ollama HTTP client
├── memory/
│   ├── __init__.py
│   └── store.py        # Deduplication store
└── tools/
    ├── __init__.py
    └── google_calendar.py # Calendar integration

tests/
├── __init__.py
├── fixtures.py         # Sample meeting notes
├── test_agent.py       # Agent integration tests
├── test_google_calendar.py
├── test_memory_store.py
├── test_ollama_client.py
└── test_state.py
```

## Error Handling

The agent implements several reliability patterns:

1. **Retry with Backoff**: Transient API errors (429, 5xx) are retried with exponential backoff
2. **Model Fallback**: If a model fails, falls back to alternative models
3. **Guardrail Checks**: Validates data before calendar creation
4. **Fail-Safe Response**: Always returns a structured response with error details

## Sample Meeting Notes for Testing

The project includes **3 realistic sample meeting notes** in the `sample_notes/` directory:

1. **`tech_design_meeting.txt`** - Clear next meeting (100% confidence)
   - Database migration planning meeting
   - Complete event details with attendees and video link
   - Expected: Calendar event created successfully

2. **`customer_call.txt`** - Tentative meeting (95% confidence)
   - Customer contract renewal discussion
   - Multiple time options with one preferred
   - Expected: Event created with confirmation warning

3. **`team_retrospective.txt`** - No specific meeting (30% confidence)
   - Sprint retrospective with many action items
   - Vague next meeting reference ("approximately February 11th")
   - Expected: No event created, missing date/time

See [sample_notes/README.md](sample_notes/README.md) for detailed information.

### Testing with Sample Notes

```bash
# Test with tech design meeting
python -m app.main --notes-file sample_notes/tech_design_meeting.txt --dry-run

# Test with customer call
python -m app.main --notes-file sample_notes/customer_call.txt --dry-run

# Run integration tests
pytest tests/test_integration_samples.py -v -s
```

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (`pytest`)
5. Submit a pull request
