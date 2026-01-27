# LangGraph Architecture & Photo Upload Tool Documentation

## Table of Contents
1. [Overview](#1-overview)
2. [LangGraph State Machine Architecture](#2-langgraph-state-machine-architecture)
3. [Agent State Definition](#3-agent-state-definition)
4. [Graph Nodes and Routing](#4-graph-nodes-and-routing)
5. [Photo Upload Tool Deep Dive](#5-photo-upload-tool-deep-dive)
6. [pCloud API Integration](#6-pcloud-api-integration)
7. [End-to-End Request Flow](#7-end-to-end-request-flow)
8. [Error Handling and Edge Cases](#8-error-handling-and-edge-cases)

---

## 1. Overview

This application implements an AI-powered chat agent using **LangGraph**, a framework for building stateful, multi-step AI workflows. The agent orchestrates multiple tools including weather, geocoding, currency exchange, radio stations, book queries, translation, and **photo uploads to pCloud**.

The photo upload tool (`photo_upload`) is the newest addition, enabling users to:
- Upload photos to pCloud cloud storage
- Automatically organize photos into folders following the naming convention: `YYYY.MM.DD - event_name - location`
- View the complete folder structure of their Photo_Memories collection

**Key Technologies:**
- **LangGraph** – State machine for agent orchestration
- **LangChain** – LLM integration (OpenAI GPT-4 Turbo)
- **pCloud API** – Cloud storage backend via the `pcloud` Python library
- **FastAPI** – REST API backend
- **React/TypeScript** – Frontend application

---

## 2. LangGraph State Machine Architecture

The agent is implemented as a **cyclic state graph** that allows the LLM to reason, call tools, observe results, and iterate until a final answer is produced.

### Graph Structure Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        ENTRY POINT                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  agent_decide   │◄──────────────────────────┐
                    │  (LLM reasoning)│                           │
                    └────────┬────────┘                           │
                             │                                    │
              ┌──────────────┼──────────────┐                     │
              │              │              │                     │
              ▼              ▼              ▼                     │
       ┌────────────┐ ┌────────────┐ ┌────────────┐              │
       │tool_weather│ │tool_photo_ │ │ tool_...   │              │
       │            │ │  upload    │ │ (others)   │              │
       └─────┬──────┘ └─────┬──────┘ └─────┬──────┘              │
             │              │              │                      │
             └──────────────┴──────────────┘                      │
                            │                                     │
                            └─────────────────────────────────────┘
                                        (loop back)
                              │
                              │ (final_answer)
                              ▼
                    ┌─────────────────┐
                    │ agent_finalize  │
                    │ (response gen)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │      END        │
                    └─────────────────┘
```

### Key Design Principles

1. **Cyclic Execution** – After each tool execution, control returns to `agent_decide`, allowing the agent to call additional tools or finalize.
2. **Iteration Limit** – A maximum of 10 iterations prevents infinite loops.
3. **Conditional Routing** – The `_route_decision` function inspects the agent's JSON response to determine the next node.

---

## 3. Agent State Definition

The agent maintains state across the graph using a `TypedDict`:

```python
class AgentState(TypedDict, total=False):
    messages: Sequence[BaseMessage]      # Conversation history (Human, AI, System messages)
    memory: Memory                        # User profile, preferences, workflow state
    tools_called: List[ToolCall]          # Record of all tool invocations
    current_user_id: str                  # User identifier for personalization
    next_action: str                      # Routing decision (tool name or "final_answer")
    tool_decision: Dict[str, Any]         # Tool name and arguments from LLM
    iteration_count: int                  # Loop counter for safety
```

**Source:** `Application/backend/services/agent.py` lines 31-39

---

## 4. Graph Nodes and Routing

### 4.1 Node: `agent_decide`

**Purpose:** Analyzes the user's request and decides the next action.

**Process:**
1. Builds a system prompt with user memory and preferences
2. Constructs a decision prompt listing all available tools
3. Includes information about attached files (critical for photo uploads)
4. Requests the LLM to return a JSON object specifying the action

**Decision Prompt Structure:**
```
Available tools:
- weather: Get weather forecast...
- photo_upload: Upload photos to pCloud Photo_Memories folder...
  (USE THIS WHEN FILES ARE ATTACHED)

User's original request: {user_message}

CRITICAL RULES:
1. If files are attached, you MUST use photo_upload
2. Return ONLY valid JSON
3. Do not call the same tool with identical arguments twice
```

**Output Format:**
```json
{
  "action": "call_tool",
  "tool_name": "photo_upload",
  "arguments": {
    "action": "upload",
    "date": "2024-06-15",
    "event_name": "summer vacation",
    "location": "Barcelona"
  },
  "reasoning": "User attached photos and mentioned summer vacation in Barcelona"
}
```

**Source:** `Application/backend/services/agent.py` lines 142-257

### 4.2 Node: `tool_*` (Dynamic Tool Nodes)

Each registered tool has a corresponding node created dynamically:

```python
for tool_name in self.tools.keys():
    workflow.add_node(f"tool_{tool_name}", self._create_tool_node(tool_name))
```

**Tool Node Execution:**
1. Retrieves tool instance and arguments from state
2. For `photo_upload`, injects pending file data (paths, names, bytes)
3. Executes the tool's `execute()` method
4. Records the result in a `ToolCall` object
5. Appends a `SystemMessage` with the tool output to conversation history

**Source:** `Application/backend/services/agent.py` lines 275-335

### 4.3 Node: `agent_finalize`

**Purpose:** Generates the final natural language response to the user.

**Process:**
1. Detects the user's question language (supports EN, HU, DE, FR, ES, IT, PT, RU)
2. Builds conversation history including full tool outputs
3. Applies critical formatting instructions:
   - Use 📂 icons before folder names
   - Use 📷 icons before file names
   - List attached files on separate lines
4. Invokes the LLM to generate the response
5. Validates response language matches input language

**Source:** `Application/backend/services/agent.py` lines 400-510

### 4.4 Routing Function: `_route_decision`

Determines the next node based on the agent's decision:

```python
def _route_decision(self, state: AgentState) -> str:
    if state.get("iteration_count", 0) >= MAX_ITERATIONS:
        return "final_answer"
    
    action = state.get("next_action", "final_answer")
    
    if action == "call_tool" and "tool_decision" in state:
        tool_name = state["tool_decision"].get("tool_name")
        if tool_name in self.tools:
            return f"tool_{tool_name}"
    
    return "final_answer"
```

**Source:** `Application/backend/services/agent.py` lines 259-273

---

## 5. Photo Upload Tool Deep Dive

### 5.1 Tool Registration

The `PhotoUploadTool` is instantiated in `main.py` and passed to the agent:

```python
pcloud_client = PCloudClient(
    username=os.getenv("PCLOUD_USERNAME"),
    password=os.getenv("PCLOUD_PASSWORD"),
    endpoint="eapi"  # European endpoint
)

photo_upload_tool = PhotoUploadTool(
    cloud_client=pcloud_client,
    photo_memories_folder_id=int(os.getenv("PCLOUD_PHOTO_MEMORIES_FOLDER_ID", 0)) or None
)
```

### 5.2 Tool Description (LLM-Facing)

```
Upload photos to pCloud Photo_Memories folder.
This tool is used when the user has attached files/photos to upload.

The tool will:
1. Ask about the date (when were the photos taken) - converts to YYYY.MM.DD format
2. Ask about the event name (what event/occasion)
3. Ask about the location (where the photos were taken)
4. Create a folder: YYYY.MM.DD - [EVENT NAME] - [LOCATION]
5. Upload all attached photos to that folder
6. Show the Photo_Memories folder structure with the new folder's contents

Parameters:
- action: 'upload' to upload files, 'list' to list Photo_Memories structure
- date: Date in any format (will be converted to YYYY.MM.DD)
- event_name: Name of the event
- location: Where the event took place
- file_paths: List of file paths to upload (provided by the system)
- file_names: List of original file names
```

**Source:** `Application/backend/services/tools.py` lines 889-905

### 5.3 Execution Flow

#### Step 1: Action Dispatch

```python
async def execute(self, action: str = "upload", date: str = None, 
                  event_name: str = None, location: str = None,
                  file_paths: list = None, file_names: list = None,
                  file_data: list = None) -> Dict[str, Any]:
```

Two actions are supported:
- `"list"` – Returns the Photo_Memories folder structure
- `"upload"` – Uploads files to a new or existing event folder

#### Step 2: Input Validation (Upload Action)

```python
if not date or not event_name or not location:
    missing = []
    if not date: missing.append("date (when were the photos taken?)")
    if not event_name: missing.append("event_name (what event/occasion?)")
    if not location: missing.append("location (where were the photos taken?)")
    
    return {
        "success": False,
        "error": f"Missing required information: {', '.join(missing)}",
        "needs_info": missing
    }
```

**Source:** `Application/backend/services/tools.py` lines 1061-1084

#### Step 3: Date Parsing

The tool accepts dates in multiple formats and normalizes to `YYYY.MM.DD`:

```python
formats = [
    "%Y-%m-%d",      # 2024-01-15
    "%Y.%m.%d",      # 2024.01.15
    "%d-%m-%Y",      # 15-01-2024
    "%B %d, %Y",     # January 15, 2024
    "%d %B %Y",      # 15 January 2024
    # ... and more
]
```

**Source:** `Application/backend/services/tools.py` lines 907-957

#### Step 4: Folder Resolution

```python
# Ensure Photo_Memories root folder exists
photo_memories_id = await self._ensure_photo_memories_folder()

# Build folder name: "2024.06.15 - summer vacation - Barcelona"
folder_name = f"{formatted_date} - {sanitized_event} - {sanitized_location}"

# Check if folder already exists
existing = await self.drive_client.find_folder(folder_name, photo_memories_id)
if existing.get("found"):
    event_folder_id = existing["folder_id"]
else:
    # Create new folder
    folder_result = await self.drive_client.create_folder(folder_name, photo_memories_id)
    event_folder_id = folder_result["folder_id"]
```

**Source:** `Application/backend/services/tools.py` lines 1086-1114

#### Step 5: File Upload Loop

```python
for i in range(num_files):
    file_name = file_names[i]
    mime_type = self._get_mime_type(file_name)
    
    if file_paths and i < len(file_paths):
        # Upload from temporary file path
        result = await self.drive_client.upload_file(
            file_paths[i], file_name, event_folder_id, mime_type
        )
    elif file_data and i < len(file_data):
        # Upload from bytes (in-memory)
        result = await self.drive_client.upload_file_from_bytes(
            file_data[i], file_name, event_folder_id, mime_type
        )
    
    if result.get("success"):
        uploaded_files.append({"name": file_name, "id": result.get("file_id")})
    else:
        failed_files.append({"name": file_name, "error": result.get("error")})
```

**Source:** `Application/backend/services/tools.py` lines 1116-1166

#### Step 6: Response Generation

```python
summary = f"📸 **Photo Upload Complete!**\n\n"
summary += f"📂 **Folder Created/Used:** {folder_name}\n"
summary += f"✅ **Successfully Uploaded:** {len(uploaded_files)} file(s)\n"

# List files in the uploaded folder
summary += f"\n**📁 Files in '{folder_name}':**\n"
for item in folder_files:
    size_kb = item.get('size', 0) / 1024
    summary += f"  📷 {item['name']} ({size_kb:.1f} KB)\n"

# List all Photo_Memories folders
summary += f"\n**📂 All Photo_Memories Folders:**\n"
for folder in all_folders:
    if folder["name"] == folder_name:
        summary += f"📂 **{folder['name']}** ← _just uploaded here_\n"
    else:
        summary += f"📂 {folder['name']}\n"
```

**Source:** `Application/backend/services/tools.py` lines 1175-1203

---

## 6. pCloud API Integration

### 6.1 PCloudClient Overview

The `PCloudClient` class wraps the official `pcloud` Python library, providing async-compatible methods for the photo upload tool.

**Authentication Methods:**
1. **Username/Password** – Uses `PCLOUD_USERNAME` and `PCLOUD_PASSWORD` environment variables
2. **OAuth Token** – Uses `PCLOUD_ACCESS_TOKEN` for token-based auth

**Endpoints:**
- `api.pcloud.com` – US datacenter
- `eapi.pcloud.com` – European datacenter (default)

**Source:** `Application/backend/infrastructure/tool_clients.py` lines 1218-1275

### 6.2 API Methods Summary

| Method | pCloud API Call | HTTP Type | Purpose |
|--------|-----------------|-----------|---------|
| `find_folder()` | `listfolder` | GET | Search for a folder by name within a parent folder |
| `create_folder()` | `createfolderifnotexists` | POST | Create a folder (idempotent) |
| `upload_file()` | `uploadfile` | POST | Upload file from disk path |
| `upload_file_from_bytes()` | `uploadfile` | POST | Upload file from memory bytes |
| `list_folder_contents()` | `listfolder` | GET | List all items in a folder |
| `get_folder_structure()` | `listfolder` | GET | List only subfolders (one level) |

### 6.3 Detailed Method Descriptions

#### `find_folder(folder_name, parent_folder_id)`

Lists the parent folder's contents and searches for a matching folder name.

```python
result = self._client.listfolder(folderid=parent_id)
for item in contents:
    if item.get('isfolder') and item.get('name') == folder_name:
        return {"found": True, "folder_id": item.get('folderid')}
return {"found": False}
```

**Source:** `Application/backend/infrastructure/tool_clients.py` lines 1407-1441

#### `create_folder(folder_name, parent_folder_id)`

Creates a folder using the idempotent `createfolderifnotexists` API.

```python
result = self._client.createfolderifnotexists(name=folder_name, folderid=parent_id)
return {
    "success": True,
    "folder_id": result['metadata']['folderid'],
    "created": result.get('created', False)
}
```

**Source:** `Application/backend/infrastructure/tool_clients.py` lines 1296-1330

#### `upload_file(file_path, file_name, folder_id, mime_type)`

Uploads a file from a local path.

```python
result = self._client.uploadfile(files=[file_path], folderid=folder_id)
return {
    "success": True,
    "file_id": result['metadata'][0]['fileid'],
    "size": result['metadata'][0]['size']
}
```

**Source:** `Application/backend/infrastructure/tool_clients.py` lines 1332-1367

#### `list_folder_contents(folder_id)`

Returns all items (files and folders) within a folder.

```python
result = self._client.listfolder(folderid=folder_id)
contents = []
for item in result['metadata']['contents']:
    contents.append({
        "id": item.get('folderid') if item.get('isfolder') else item.get('fileid'),
        "name": item.get('name'),
        "type": "folder" if item.get('isfolder') else "file",
        "size": item.get('size')
    })
return {"success": True, "contents": contents}
```

**Source:** `Application/backend/infrastructure/tool_clients.py` lines 1443-1481

---

## 7. End-to-End Request Flow

### 7.1 Frontend Upload Request

1. User attaches photos via the file input in `ChatInput.tsx`
2. User enters a message describing the photos (e.g., "Here are my summer vacation photos from Barcelona, June 2024")
3. Frontend calls `api.sendMessageWithFiles()` which POSTs to `/api/chat/upload`

```typescript
const formData = new FormData();
formData.append('user_id', userId);
formData.append('message', message);
files.forEach((file) => formData.append('files', file));

await apiClient.post('/chat/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
});
```

**Source:** `Application/frontend/src/api.ts` lines 22-44

### 7.2 Backend Processing

1. **File Reception** – FastAPI endpoint receives files, saves to temp directory
2. **Chat Service** – Calls `process_message_with_files()` with file paths and names
3. **Agent Execution** – `agent.run_with_files()` stores file info in `_pending_files`
4. **Graph Execution** – LangGraph runs the state machine

```python
# In chat_service.py
agent_result = await self.agent.run_with_files(
    user_message=message,
    memory=memory,
    user_id=user_id,
    file_paths=file_paths,
    file_names=file_names
)
```

**Source:** `Application/backend/services/chat_service.py` lines 307-354

### 7.3 Agent Decision with Files

The `agent_decide` node detects attached files and instructs the LLM to use `photo_upload`:

```python
files_attached = hasattr(self, '_pending_files') and self._pending_files
if files_attached:
    file_names = self._pending_files.get('file_names', [])
    file_info = f"**IMPORTANT: {len(file_names)} FILE(S) ATTACHED: {', '.join(file_names)}**"
    file_info += "\nYou MUST use the photo_upload tool to handle these files."
```

**Source:** `Application/backend/services/agent.py` lines 168-173

### 7.4 Tool Execution

The `tool_photo_upload` node injects file data and executes:

```python
if tool_name == "photo_upload" and hasattr(self, '_pending_files'):
    arguments["file_paths"] = self._pending_files.get("file_paths", [])
    arguments["file_names"] = self._pending_files.get("file_names", [])

result = await tool.execute(**arguments)
```

**Source:** `Application/backend/services/agent.py` lines 288-296

### 7.5 Response Generation

The `agent_finalize` node generates the user-facing response with formatting instructions:

```
CRITICAL INSTRUCTIONS:
- Use proper icons: 📂 folder icon before folder names, 📷 camera icon before file names
- DO NOT use hyphens (-) before folders or files - use the icons instead
- When files are attached to the question, list them on a NEW LINE
```

**Source:** `Application/backend/services/agent.py` lines 476-486

### 7.6 Frontend Display

The response is displayed in `MessageBubble.tsx`:
- **Tools Used Section** – Shows `✓ photo_upload - Uploaded 3 photos to '2024.06.15 - summer vacation - Barcelona'`
- **Message Content** – Contains the LLM's natural language response with folder/file listings

**Source:** `Application/frontend/src/components/MessageBubble.tsx` lines 21-36

---

## 8. Error Handling and Edge Cases

### 8.1 Missing Information

If the user doesn't provide date, event name, or location, the tool returns a structured error:

```python
return {
    "success": False,
    "error": "Missing required information: date, event_name",
    "needs_info": ["date (when were the photos taken?)", "event_name (what event/occasion?)"]
}
```

The agent can then ask the user for the missing details.

### 8.2 Upload Failures

Individual file failures are tracked separately from successes:

```python
if result.get("success"):
    uploaded_files.append({"name": file_name, "id": result.get("file_id")})
else:
    failed_files.append({"name": file_name, "error": result.get("error")})
```

The final summary reports both:
```
✅ Successfully Uploaded: 2 file(s)
❌ Failed: 1 file(s)
```

### 8.3 Iteration Limit

The graph enforces a maximum of 10 iterations to prevent infinite loops:

```python
MAX_ITERATIONS = 10

if state.get("iteration_count", 0) >= MAX_ITERATIONS:
    logger.warning(f"Max iterations ({MAX_ITERATIONS}) reached, forcing finalize")
    return "final_answer"
```

**Source:** `Application/backend/services/agent.py` lines 27-28, 262-264

### 8.4 pCloud API Errors

All pCloud operations are wrapped in try/except blocks with detailed logging:

```python
except Exception as e:
    logger.error(f"Failed to upload file: {e}", exc_info=True)
    return {"error": str(e)}
```

---

## Summary

The photo upload tool demonstrates a sophisticated integration of:

1. **LangGraph** – For stateful, multi-step agent orchestration
2. **LLM Reasoning** – GPT-4 Turbo for understanding user intent and extracting metadata
3. **Cloud Storage** – pCloud API for persistent file storage
4. **Structured Output** – JSON-based tool communication and rich markdown responses

The cyclic graph architecture allows the agent to gather missing information, execute uploads, and provide detailed feedback—all within a single conversation turn.
