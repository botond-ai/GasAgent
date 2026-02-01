# Multi-Conversation Chat Refactor – Coding Agent Prompt

## Objective

Refactor the existing chat agent application so that **chat conversations are fully separated into threads**.

Add a **right-hand conversation list** UI and a **“New Conversation”** button that starts a **completely fresh chat with zero prior context**.

Each conversation must be isolated at both **UI level** and **agent/context level**.

---

## UX Requirements (Mandatory)

### 1. Right-Side Conversation List
- Display conversations in a right-hand panel
- Newest conversations appear first
- Each list item shows:
  - Auto-generated title
  - Last updated timestamp
  - Optional message preview
- The active conversation is visually highlighted

### 2. New Conversation Button
- Creates a new conversation/thread
- Clears the chat window immediately
- The next agent call must receive **no prior user or assistant messages**
- Only the global system prompt may remain

### 3. Conversation Switching
- Clicking a conversation loads its messages into the chat window
- Switching conversations must **not leak context** between threads

### 4. Conversation Deletion (Optional but Preferred)
- Remove conversation from the list
- Use soft delete (`deleted_at`) if possible

### 5. Persistence
- Conversations must persist across page reloads
- Use existing backend DB if available
- Otherwise use local persistence:
  - IndexedDB preferred
  - localStorage acceptable for MVP

---

## Functional / Agent Requirements

### 1. Conversation / Thread ID
- Every message and every agent invocation must be associated with a `conversation_id`
- Use UUID v4 for IDs

### 2. Strict Context Isolation
- When calling the agent, include **only**:
  - Global system prompt
  - Messages belonging to the active `conversation_id`
- No global memory, cache, or shared history across conversations

### 3. Hard Context Reset
- Starting a new conversation must:
  - Create a new `conversation_id`
  - Discard any in-memory context related to previous conversations
- If the backend or agent uses memory, it must be explicitly cleared per conversation

### 4. Streaming Compatibility
- If agent responses are streamed:
  - Partial chunks must be appended only to the correct conversation

### 5. System Prompt Handling
- System prompt is global and static
- User, assistant, and tool messages are scoped strictly to a conversation

---

## Data Model (Must Be Implemented)

### Conversation / Thread
```
id: string (uuid v4)
title: string
created_at: datetime
updated_at: datetime
deleted_at?: datetime | null
```

### Message
```
id: string (uuid v4)
conversation_id: string
role: "system" | "user" | "assistant" | "tool"
content: string
created_at: datetime
metadata?: {
  tokens?,
  model?,
  tool_calls?,
  attachments?
}
```

---

## Deliverables & Constraints

- No global or shared chat history
- New conversation = hard context reset
- Prefer the simplest, most maintainable implementation
