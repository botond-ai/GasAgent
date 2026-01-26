# LangGraph Workflow Implementation

## Overview

The LangGraph workflow is a multi-step agent orchestration system that processes user requests through a structured plan, executes appropriate tools, and generates comprehensive summaries. It's implemented in `app/langgraph_workflow.py` and provides autonomous decision-making and tool routing capabilities.

## Architecture

### Workflow Nodes

The workflow consists of 7 key nodes that execute in sequence:

#### 1. **plan_node** - Execution Plan Generation
- Analyzes the user input from CLI
- Retrieves relevant context from the RAG database (vector store)
- Uses LLM to generate a structured execution plan
- Determines which steps are needed to fulfill the user's request
- Output: A list of `ExecutionStep` objects with actions and required tools

**Process:**
```
User Input → RAG Search (retrieve context) → LLM Plan Generation → Execution Plan
```

#### 2. **executor_loop** - Step Orchestration
- Manages the iteration through planned steps
- Maintains the current step index
- Decides whether to continue or finish execution
- Acts as the control flow coordinator

**Decision Logic:**
- If `current_step_index < total_steps`: continue to tool_router
- Else: move to summary_node

#### 3. **tool_router** - Tool Selection
- Routes each step to the appropriate tool
- Analyzes the step's action description
- Determines which tool is needed:
  - **google_calendar**: For calendar-related queries
  - **ip_geolocation**: For IP address lookups
  - **rag_search**: For document retrieval
  - **none**: For information gathering only

**Routing Logic:**
```
Step Action → Keyword Analysis → Tool Selection
  ├─ "calendar" → GOOGLE_CALENDAR
  ├─ "location" or "ip" → IP_GEOLOCATION
  ├─ "search" or "retrieve" → RAG_SEARCH
  └─ other → NONE
```

#### 4. **action_node** - Tool Execution
- Executes the tool selected by tool_router
- Calls the appropriate service:
  - Google Calendar API
  - IP Geolocation API
  - RAG search on vector store
- Captures results or errors
- Updates step status (completed/failed)

**Supported Actions:**
- Google Calendar: list upcoming events, get today's events
- IP Geolocation: lookup IP address, retrieve location data
- RAG Search: semantic search on embedded documents

#### 5. **observation_node** - State Update
- Checks and validates action results
- Updates the execution state based on action outcome
- Adds observations to the workflow state
- Moves to the next step index
- Handles both successful and failed actions

**State Updates:**
- Append current step to `executed_steps`
- Increment `current_step_index`
- Record observations about results
- Log any errors

#### 6. **summary_node** - Meeting Summary Generation
- Combines execution results with RAG context
- Uses LLM to generate a comprehensive meeting summary
- Includes:
  - Key decisions and discussions
  - Action items
  - Next steps
  - Relevant context from documents

**Summary Inputs:**
- Executed steps and their results
- Tool outputs
- Original user request
- Retrieved documents from RAG
- Workflow observations

#### 7. **final_answer_node** - Final Report Generation
- Creates comprehensive final report
- Lists all executed steps with status
- Shows meeting summary
- Includes warnings and errors (if any)
- Formatted for display to user

**Report Contains:**
- User request summary
- Step-by-step execution log with ✓/✗ status
- Meeting summary
- Warnings/errors encountered

## State Management

### WorkflowState Dataclass

```python
@dataclass
class WorkflowState:
    user_input: str                              # Original user request
    execution_plan: List[ExecutionStep]          # Planned steps
    current_step_index: int                      # Current execution position
    executed_steps: List[ExecutionStep]          # Completed steps
    tool_outputs: Dict[str, Any]                 # Results from each tool
    observations: List[str]                      # Running log of observations
    meeting_summary: Optional[str]               # Generated summary
    final_answer: Optional[str]                  # Final formatted report
    error_messages: List[str]                    # Collected errors
```

### ExecutionStep Structure

```python
@dataclass
class ExecutionStep:
    step_id: int                    # Sequential step number
    action: str                     # Description of action
    tool: ToolType                  # Tool to use
    parameters: Dict[str, Any]      # Tool parameters
    result: Optional[Any] = None    # Tool execution result
    status: str = "pending"         # pending|in_progress|completed|failed
```

## Workflow Graph

```
Start
  ↓
[plan_node] ← Generate execution plan from RAG context
  ↓
[executor_loop] ← Check if more steps to execute
  ├─→ "continue" → [tool_router] → [action_node] → [observation_node] → loop
  └─→ "done" → [summary_node] → [final_answer_node] → End
```

## Usage

### CLI Integration

The workflow is integrated into the interactive CLI:

```bash
/workflow your request here
```

**Examples:**

```bash
# Schedule and retrieve location
/workflow Schedule a meeting for tomorrow and check the IP location of our server

# Calendar events and document search
/workflow Show my calendar and find relevant documents about project X

# Complex multi-step request
/workflow Look up the weather, check my calendar, and find related meeting minutes
```

### Programmatic Usage

```python
from app.langgraph_workflow import MeetingAssistantWorkflow

# Initialize workflow
workflow = MeetingAssistantWorkflow(
    api_key="your-openai-key",
    vector_store=vector_store,
    rag_agent=rag_agent,
    google_calendar_service=calendar_service,
    geolocation_client=geo_client,
)

# Run workflow
result = workflow.run("Your user request")

# Access results
print(result['final_answer'])
print(result['meeting_summary'])
print(result['executed_steps'])
```

## Tool Integration

### Google Calendar Tool

**When Used:**
- User requests mention "calendar", "schedule", "meeting", etc.

**Capabilities:**
- List upcoming events (next 5)
- Get today's events
- Query date ranges

**Example:**
```json
{
  "step_id": 1,
  "action": "Retrieve upcoming calendar events",
  "tool": "google_calendar",
  "parameters": {"action_type": "list_events"}
}
```

### IP Geolocation Tool

**When Used:**
- User requests mention "IP", "location", "geolocation", etc.

**Capabilities:**
- Lookup IP addresses
- Return country, city, region, coordinates
- Return ISP and organization info
- Return timezone information

**Example:**
```json
{
  "step_id": 2,
  "action": "Check geolocation of server IP",
  "tool": "ip_geolocation",
  "parameters": {"ip": "8.8.8.8"}
}
```

### RAG Search Tool

**When Used:**
- User requests mention "search", "retrieve", "find", "documents", etc.

**Capabilities:**
- Semantic search on embedded documents
- Retrieve top-K similar documents
- Return relevance scores

**Example:**
```json
{
  "step_id": 1,
  "action": "Search for meeting minutes about project X",
  "tool": "rag_search",
  "parameters": {"query": "project X meeting minutes"}
}
```

## LLM Integration

The workflow uses OpenAI LLM for:

1. **Plan Generation** (`plan_node`)
   - Input: User request + RAG context
   - Output: JSON execution plan

2. **Summary Generation** (`summary_node`)
   - Input: Execution results + documents
   - Output: Natural language summary

**Configuration** (via `.env`):
```bash
OPENAI_LLM_MODEL=gpt-4o-mini
OPENAI_LLM_TEMPERATURE=0.7
OPENAI_LLM_MAX_TOKENS=1024
```

## Error Handling

Each node includes error handling:

- **action_node**: Catches tool execution failures, marks step as failed
- **observation_node**: Logs errors to `error_messages`
- **final_answer_node**: Includes errors in final report with ⚠ indicator

Example error handling:
```python
try:
    result = execute_action()
    step.status = "completed"
except Exception as e:
    step.status = "failed"
    state.error_messages.append(f"Step {step_id} failed: {str(e)}")
```

## Performance Considerations

1. **Plan Caching**: Plans are generated once per workflow run
2. **RAG Retrieval**: Limited to k=3 most relevant documents
3. **Tool Parallelization**: Currently sequential; can be optimized for parallel execution
4. **State Size**: State is kept in memory; suitable for typical workflows

## Extensibility

### Adding New Tools

1. Create tool handler in `_execute_*_action()` method
2. Add tool type to `ToolType` enum
3. Update `tool_router` routing logic
4. Update LLM prompt examples in `_create_plan_prompt()`

### Customizing Plan Generation

Modify `_create_plan_prompt()` to:
- Add domain-specific instructions
- Include additional context sources
- Specify custom plan structure

### Extending Summary Generation

Modify `_create_summary_prompt()` to:
- Include custom summary fields
- Add domain-specific analysis
- Customize output format

## Testing

Example test case:
```python
def test_workflow_execution():
    workflow = MeetingAssistantWorkflow(...)
    result = workflow.run("Show calendar and find relevant documents")
    
    assert result['executed_steps'] >= 1
    assert result['final_answer'] is not None
    assert len(result['errors']) == 0
```

## Future Enhancements

1. **Parallel Tool Execution**: Execute independent steps in parallel
2. **Conditional Routing**: Add decision points based on tool results
3. **Tool Chaining**: Allow tools to pass data to subsequent steps
4. **Context Persistence**: Save and restore workflow state
5. **Analytics**: Track workflow metrics and performance
6. **User Feedback Loop**: Refine plans based on execution results
7. **Multi-turn Conversations**: Support interactive workflow refinement
