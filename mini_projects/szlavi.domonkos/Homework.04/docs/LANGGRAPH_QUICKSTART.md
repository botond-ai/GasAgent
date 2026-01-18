# LangGraph Workflow - Quick Start Guide

## Installation

1. Update dependencies:
```bash
pip install -r requirements.txt
```

The `requirements.txt` now includes:
- `langgraph>=0.0.20`
- `langchain>=0.1.0`

2. Set up environment variables in `.env`:
```bash
OPENAI_API_KEY=your-openai-api-key
OPENAI_LLM_MODEL=gpt-4o-mini
OPENAI_LLM_TEMPERATURE=0.7
OPENAI_LLM_MAX_TOKENS=1024

# Optional: Google Calendar
GOOGLE_CALENDAR_CREDENTIALS_FILE=./client_credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=./token.pickle

# Optional: IP Geolocation (free tier available)
IP_GEOLOCATION_API_KEY=your-api-key-if-using-pro
```

## Running the Workflow

### Via CLI (Interactive Mode)

Start the application:
```bash
python -m app.main
```

Use the workflow command:
```bash
Enter a prompt (or 'exit' to quit): /workflow show my calendar and find related meeting minutes
```

### Programmatic Usage

```python
from app.config import load_config
from app.embeddings import OpenAIEmbeddingService
from app.vector_store import ChromaVectorStore
from app.rag_agent import RAGAgent
from app.google_calendar import GoogleCalendarService
from app.tool_clients import IPAPIGeolocationClient
from app.langgraph_workflow import MeetingAssistantWorkflow

# Load configuration
cfg = load_config()

# Initialize services
emb_service = OpenAIEmbeddingService(api_key=cfg.openai_api_key, model=cfg.embedding_model)
vector_store = ChromaVectorStore(persist_dir=cfg.chroma_persist_dir)
rag_agent = RAGAgent(api_key=cfg.openai_api_key, llm_model=cfg.llm_model)
calendar_service = GoogleCalendarService(
    credentials_file=cfg.google_calendar_credentials_file,
    token_file=cfg.google_calendar_token_file,
)
geolocation_client = IPAPIGeolocationClient(use_pro=False)

# Create workflow
workflow = MeetingAssistantWorkflow(
    api_key=cfg.openai_api_key,
    vector_store=vector_store,
    rag_agent=rag_agent,
    google_calendar_service=calendar_service,
    geolocation_client=geolocation_client,
)

# Run workflow
result = workflow.run("Your complex request here")

# Process results
print("Execution Plan:")
for step in result['execution_plan']:
    status = "✓" if step['status'] == "completed" else "✗"
    print(f"  {status} Step {step['step_id']}: {step['action']} ({step['tool']})")

print("\nMeeting Summary:")
print(result['meeting_summary'])

print("\nFinal Answer:")
print(result['final_answer'])
```

## Example Workflows

### Example 1: Check Calendar and Search Related Docs

**Command:**
```bash
/workflow Check my calendar for tomorrow and find relevant meeting minutes about quarterly planning
```

**Execution Flow:**
1. **plan_node**: Generates plan with 2 steps
   - Step 1: Retrieve tomorrow's calendar events
   - Step 2: Search documents for "quarterly planning"

2. **executor_loop**: Iterates through steps

3. **tool_router**: 
   - Step 1 → GOOGLE_CALENDAR
   - Step 2 → RAG_SEARCH

4. **action_node**: Executes tools
   - Gets 3 events for tomorrow
   - Finds 3 relevant documents

5. **observation_node**: Records results

6. **summary_node**: Generates summary combining calendar and document insights

7. **final_answer_node**: Creates formatted report

**Expected Output:**
```
Execution Plan (2 steps):
  ✓ Step 1: Retrieve tomorrow's calendar events (google_calendar)
  ✓ Step 2: Search for quarterly planning documents (rag_search)

Meeting Summary:
Tomorrow's calendar shows 2 meetings:
- Planning Review (10:00-11:00)
- Team Standup (15:00-15:30)

Related documents about quarterly planning include:
- Q1 2026 Planning Document (relevance: 0.95)
- Budget Allocation Guidelines (relevance: 0.87)
- Hiring Plan Overview (relevance: 0.82)

Key insights:
- Planning review is scheduled during typical planning time
- Found 3 relevant planning documents in knowledge base
```

### Example 2: Multi-Tool Research Request

**Command:**
```bash
/workflow Where are our servers located? Check the geolocation for 8.8.8.8 and search our infrastructure docs
```

**Execution Flow:**
1. **plan_node**: Creates plan with 2 steps
   - Step 1: Lookup geolocation for IP 8.8.8.8
   - Step 2: Search infrastructure documentation

2. **tool_router**:
   - Step 1 → IP_GEOLOCATION
   - Step 2 → RAG_SEARCH

3. **action_node**: Executes both tools
   - Geolocation: Returns location data for IP
   - Search: Finds relevant infrastructure docs

4. **summary_node**: Correlates geolocation with infrastructure docs

**Expected Output:**
```
Execution Plan (2 steps):
  ✓ Step 1: Lookup geolocation for server IP (ip_geolocation)
  ✓ Step 2: Search infrastructure documentation (rag_search)

IP Geolocation Information:
- IP: 8.8.8.8
- Country: United States
- City: Mountain View
- Timezone: America/Los_Angeles
- ISP: Google LLC

Related Infrastructure Documents:
- Data Center Locations (relevance: 0.94)
- Server Configuration Guide (relevance: 0.88)
- Network Architecture Diagram (relevance: 0.85)

Analysis:
Server IP is located in Mountain View, California. Our infrastructure documents
confirm we have primary data center in this region with redundancy setup.
```

### Example 3: Meeting Preparation Workflow

**Command:**
```bash
/workflow Prepare for tomorrow's meetings: show calendar, find relevant project docs, and summarize key points
```

**Execution Flow:**
1. **plan_node**: Creates 2-step plan
   - Step 1: Get tomorrow's calendar events
   - Step 2: Search for project documentation

2. **tool_router**:
   - Step 1 → GOOGLE_CALENDAR
   - Step 2 → RAG_SEARCH

3. **action_node**: Executes tools
   - Gets 5 tomorrow's events
   - Finds 3 project documents

4. **summary_node**: Creates meeting prep summary

**Expected Output:**
```
=== MEETING PREPARATION SUMMARY ===

Tomorrow's Schedule:
1. Project Kickoff (09:00-09:30) - Conference Room A
2. Requirements Review (10:00-11:00) - Virtual
3. Budget Approval (14:00-14:30) - Executive Suite
4. Team Sync (15:30-16:00) - Engineering Lab

Key Preparation Materials Found:
- Project Charter & Scope (relevance: 0.96)
- Technical Requirements Document (relevance: 0.93)
- Budget Allocation Guidelines (relevance: 0.89)

Recommended Pre-Read:
✓ Review Project Charter before 09:00 kickoff
✓ Check Technical Requirements 30min before 10:00 review
✓ Verify Budget document before 14:00 approval meeting

Ready for 4 meetings tomorrow with all supporting documentation prepared.
```

## Advanced Configuration

### Custom LLM Models

Edit `.env` to use different LLM models:

```bash
# Use GPT-4 for more complex reasoning
OPENAI_LLM_MODEL=gpt-4

# Or use GPT-4 Turbo
OPENAI_LLM_MODEL=gpt-4-turbo-preview

# Adjust temperature for more/less creative planning
OPENAI_LLM_TEMPERATURE=0.3  # More deterministic
# or
OPENAI_LLM_TEMPERATURE=0.9  # More creative
```

### Extending with Custom Tools

To add a new tool to the workflow:

1. **Create tool handler** in `langgraph_workflow.py`:
```python
def _execute_custom_tool_action(self, step: ExecutionStep) -> Dict[str, Any]:
    """Execute custom tool action."""
    try:
        # Your tool logic here
        result = your_tool.execute(step.parameters)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}
```

2. **Add tool type** to `ToolType` enum:
```python
class ToolType(str, Enum):
    CUSTOM_TOOL = "custom_tool"
    # ... existing tools
```

3. **Update tool router** to recognize your tool:
```python
def tool_router(self, state: WorkflowState) -> WorkflowState:
    # ... existing code
    elif "custom" in current_step.action.lower():
        current_step.tool = ToolType.CUSTOM_TOOL
    # ... rest of routing
```

4. **Update action node** to call your tool:
```python
def action_node(self, state: WorkflowState) -> WorkflowState:
    # ... existing code
    elif current_step.tool == ToolType.CUSTOM_TOOL:
        result = self._execute_custom_tool_action(current_step)
    # ... rest of execution
```

## Troubleshooting

### Issue: "LangGraph workflow not available"

**Solution**: Ensure RAG agent is properly initialized:
```bash
# Check OPENAI_API_KEY is set
echo $OPENAI_API_KEY

# Verify dependencies installed
pip install -r requirements.txt
```

### Issue: Workflow executes but returns no results

**Solution**: Check that vector store has data:
```bash
# Add sample documents to data/ folder
python -m app.main  # Run in batch mode to populate vector store
```

### Issue: Tool not being selected correctly

**Solution**: Review tool routing logic:
- Check if action keywords match routing conditions
- Update `tool_router` to handle your specific action descriptions
- Enable debug logging to trace routing decisions

### Issue: LLM rate limiting

**Solution**: Adjust workflow configuration:
```bash
# Reduce max tokens per request
OPENAI_LLM_MAX_TOKENS=512

# Or add retry logic in _call_llm method
```

## Performance Monitoring

Monitor workflow execution:

```python
import time
import json

# Time the workflow
start = time.time()
result = workflow.run("Your request")
elapsed = time.time() - start

# Log metrics
print(f"Workflow executed in {elapsed:.2f}s")
print(f"Steps executed: {result['executed_steps']}")
print(f"Errors: {len(result['errors'])}")

# Save results for analysis
with open("workflow_result.json", "w") as f:
    json.dump(result, f, indent=2)
```

## Best Practices

1. **Structure Requests Clearly**: More specific requests lead to better plans
   - ❌ "Show me things"
   - ✓ "Show my calendar for tomorrow and find relevant Q1 planning documents"

2. **Use Descriptive Keywords**: Help the router identify needed tools
   - For calendar: use "calendar", "schedule", "meeting", "events"
   - For geolocation: use "location", "IP", "geolocation", "where"
   - For search: use "find", "search", "relevant", "documents"

3. **Chain Related Tasks**: Workflow works best when tasks are logically connected
   - ✓ "Check calendar and find related meeting minutes"
   - ✓ "Lookup server IP location and find infrastructure docs"

4. **Prepare Your Data**: Populate the vector store with relevant documents
   - Place documents in `data/` folder
   - Run batch processing: `python -m app.main`
   - This builds the knowledge base for RAG searches

5. **Monitor Errors**: Check the errors list in results
   - Use for debugging and improving future requests
   - Some failures are expected (missing tools, etc.)
