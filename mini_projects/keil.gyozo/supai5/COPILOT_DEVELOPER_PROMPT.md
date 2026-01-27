# Developer Prompt: ChatGPT-Style Ticket Interface

## Project Context

You are building a **customer support ticket interface** for SupportAI, an AI-powered support triage system. Transform the current ticket creation form into an interactive ChatGPT-style conversational interface.

---

## Tech Stack

- **Framework:** React 18+ with TypeScript
- **Build Tool:** Vite
- **Styling:** CSS Modules or Tailwind CSS (developer's choice)
- **State Management:** React Hooks (useState, useEffect, useReducer)
- **API Client:** Native fetch or axios

---

## Core Requirements

### 1. ChatGPT-Like Interface

**Layout:**
```
┌─────────────────────────────────────────┐
│  SupportAI - Support Chat               │
├─────────────────────────────────────────┤
│                                         │
│  [Chat Messages - Scrollable]          │
│                                         │
│  User: My order was charged twice      │
│  ───────────────────────────────────   │
│  AI: I understand you were charged...  │
│  Category: Billing | Priority: P1      │
│                                         │
│  [More messages...]                     │
│                                         │
├─────────────────────────────────────────┤
│  [Type your message...]      [Send]    │
└─────────────────────────────────────────┘
```

**Features:**
- ✅ Scrollable chat history (auto-scroll to bottom on new message)
- ✅ User messages on the right (light blue background)
- ✅ AI responses on the left (light gray background)
- ✅ Input field at the bottom (always visible)
- ✅ Send button or Enter key to submit
- ✅ Loading indicator while AI processes
- ✅ Timestamp on each message
- ✅ Support for markdown in AI responses (optional)

### 2. Conversation Flow

**Initial State:**
```typescript
// Welcome message from AI
{
  role: "assistant",
  content: "Hi! I'm your AI support assistant. How can I help you today?",
  timestamp: Date.now()
}
```

**User Interaction:**
1. User types message → Press Enter or Click Send
2. Message appears in chat (user bubble)
3. Show "AI is typing..." indicator
4. Call backend API: `POST /api/tickets/{ticketId}/process`
5. AI response appears (assistant bubble)
6. Show AI metadata: category, priority, sentiment

**Conversation Types:**
- **New conversation:** Create ticket with first message
- **Existing conversation:** Add messages to existing ticket (optional future feature)

### 3. Message Types

```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  metadata?: {
    category?: string;
    priority?: 'P1' | 'P2' | 'P3';
    sentiment?: 'frustrated' | 'neutral' | 'satisfied';
    suggestedTeam?: string;
  };
}

interface Conversation {
  ticketId: string;
  messages: Message[];
  status: 'active' | 'resolved' | 'waiting';
}
```

---

## Component Structure

### Recommended File Structure

```
src/
├── pages/
│   └── TicketChat.tsx                 # Main chat page
├── components/
│   ├── chat/
│   │   ├── ChatContainer.tsx          # Main chat wrapper
│   │   ├── MessageList.tsx            # Scrollable message list
│   │   ├── MessageBubble.tsx          # Individual message
│   │   ├── InputBar.tsx               # Message input + send
│   │   └── TypingIndicator.tsx        # "AI is typing..."
│   ├── debug/
│   │   ├── DebugPanel.tsx             # Debug sidebar (collapsible)
│   │   ├── ToolCallsLog.tsx           # Show API calls
│   │   └── MemorySnapshot.tsx         # Show state/memory
│   └── ui/
│       ├── Button.tsx                 # Reusable button
│       └── Spinner.tsx                # Loading spinner
├── hooks/
│   ├── useChat.ts                     # Chat state management
│   └── useTicketAPI.ts                # API calls
├── types/
│   └── chat.ts                        # TypeScript interfaces
└── styles/
    └── chat.module.css                # Chat-specific styles
```

### Component Details

#### 1. `ChatContainer.tsx` (Main Component)

```typescript
import React, { useState, useEffect, useRef } from 'react';
import { MessageList } from './MessageList';
import { InputBar } from './InputBar';
import { DebugPanel } from '../debug/DebugPanel';
import { useChat } from '../../hooks/useChat';

interface ChatContainerProps {
  ticketId?: string; // Optional: for existing tickets
  showDebug?: boolean; // Toggle debug panel
}

export function ChatContainer({ ticketId, showDebug = false }: ChatContainerProps) {
  const {
    messages,
    isLoading,
    error,
    sendMessage,
    createTicket,
  } = useChat(ticketId);

  const handleSendMessage = async (content: string) => {
    if (!ticketId) {
      // First message: create ticket
      await createTicket(content);
    } else {
      // Subsequent messages: add to conversation
      await sendMessage(content);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-main">
        <MessageList messages={messages} isLoading={isLoading} />
        <InputBar onSend={handleSendMessage} disabled={isLoading} />
      </div>
      {showDebug && <DebugPanel />}
    </div>
  );
}
```

#### 2. `MessageBubble.tsx`

```typescript
interface MessageBubbleProps {
  message: Message;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  
  return (
    <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-content">
        {message.content}
      </div>
      
      {message.metadata && (
        <div className="message-metadata">
          <span className="category">{message.metadata.category}</span>
          <span className={`priority priority-${message.metadata.priority}`}>
            {message.metadata.priority}
          </span>
          <span className="sentiment">{message.metadata.sentiment}</span>
        </div>
      )}
      
      <div className="message-timestamp">
        {formatTimestamp(message.timestamp)}
      </div>
    </div>
  );
}
```

#### 3. `useChat.ts` Hook

```typescript
import { useState, useCallback } from 'react';
import type { Message, Conversation } from '../types/chat';

const API_URL = 'http://localhost:8000';

export function useChat(initialTicketId?: string) {
  const [ticketId, setTicketId] = useState<string | undefined>(initialTicketId);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: 'Hi! I\'m your AI support assistant. How can I help you today?',
      timestamp: Date.now(),
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createTicket = useCallback(async (content: string) => {
    setIsLoading(true);
    setError(null);

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      // 1. Create ticket
      const createResponse = await fetch(`${API_URL}/api/tickets/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_name: 'Anonymous', // TODO: Get from user profile
          customer_email: 'user@example.com',
          subject: content.substring(0, 100),
          message: content,
        }),
      });

      if (!createResponse.ok) throw new Error('Failed to create ticket');
      
      const ticket = await createResponse.json();
      setTicketId(ticket.id);

      // 2. Process ticket (AI response)
      const processResponse = await fetch(`${API_URL}/api/tickets/${ticket.id}/process`, {
        method: 'POST',
      });

      if (!processResponse.ok) throw new Error('Failed to process ticket');
      
      const result = await processResponse.json();

      // 3. Add AI response
      const aiMessage: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        content: formatAIResponse(result.answer_draft),
        timestamp: Date.now(),
        metadata: {
          category: result.triage.category,
          priority: result.triage.priority,
          sentiment: result.triage.sentiment,
          suggestedTeam: result.triage.suggested_team,
        },
      };
      setMessages(prev => [...prev, aiMessage]);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message');
    } finally {
      setIsLoading(false);
    }
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!ticketId) return;
    
    // Similar to createTicket but for existing conversation
    // TODO: Implement if backend supports conversation history
  }, [ticketId]);

  return {
    ticketId,
    messages,
    isLoading,
    error,
    createTicket,
    sendMessage,
  };
}

function formatAIResponse(draft: { greeting: string; body: string; closing: string }) {
  return `${draft.greeting}\n\n${draft.body}\n\n${draft.closing}`;
}
```

---

## Debug Panel (Optional)

### Requirements

**Features:**
- ✅ Collapsible sidebar (toggle button)
- ✅ Three tabs: "Tools" | "Memory" | "Logs"
- ✅ Shows API calls made during conversation
- ✅ Shows workflow state (intent, triage, RAG results)
- ✅ Minimal logs (INFO level only)

### Component Structure

```typescript
interface DebugPanelProps {
  isOpen?: boolean;
}

export function DebugPanel({ isOpen = true }: DebugPanelProps) {
  const [activeTab, setActiveTab] = useState<'tools' | 'memory' | 'logs'>('tools');
  
  return (
    <div className={`debug-panel ${isOpen ? 'open' : 'closed'}`}>
      <div className="debug-tabs">
        <button onClick={() => setActiveTab('tools')}>Tools</button>
        <button onClick={() => setActiveTab('memory')}>Memory</button>
        <button onClick={() => setActiveTab('logs')}>Logs</button>
      </div>
      
      <div className="debug-content">
        {activeTab === 'tools' && <ToolCallsLog />}
        {activeTab === 'memory' && <MemorySnapshot />}
        {activeTab === 'logs' && <LogViewer />}
      </div>
    </div>
  );
}
```

**Data to Display:**

**Tools Tab:**
```json
[
  {
    "name": "intent_detection",
    "status": "success",
    "duration": "1.2s",
    "output": { "intent": "billing_inquiry" }
  },
  {
    "name": "qdrant_search",
    "status": "success",
    "duration": "0.8s",
    "output": { "results_found": 5 }
  }
]
```

**Memory Tab:**
```json
{
  "preferences": {
    "language": "en",
    "tone": "professional"
  },
  "workflow_state": {
    "intent": "billing_inquiry",
    "category": "Billing",
    "priority": "P1"
  }
}
```

**Logs Tab:**
```
[15:30:45] INFO - Processing ticket abc-123
[15:30:46] INFO - Intent detected: billing_inquiry
[15:30:47] INFO - RAG search completed (5 results)
[15:30:48] INFO - Answer generated successfully
```

---

## Styling Guidelines

### ChatGPT-Inspired Design

**Colors:**
- User message: `#DCF8C6` (light green) or `#E3F2FD` (light blue)
- AI message: `#F5F5F5` (light gray)
- Background: `#FFFFFF` (white)
- Input bar: `#FAFAFA` (very light gray)

**Typography:**
- Font: `system-ui, -apple-system, sans-serif`
- Message text: `16px` / `1.5` line-height
- Metadata: `12px` / `0.875rem`

**Layout:**
- Max width: `800px` (center aligned)
- Message padding: `12px 16px`
- Border radius: `12px`
- Spacing between messages: `16px`

**Animations:**
- Message fade-in: `opacity 0.3s ease-in`
- Typing indicator: pulsing dots
- Scroll: smooth scroll to bottom

---

## API Integration

### Expanded Core Requirements

### User Stories
- As a user, I want to create a support ticket through a chat interface so that I can easily communicate my issues.
- As a support agent, I want to view the conversation history to provide better assistance.

### Scenarios
- **Scenario 1**: User initiates a chat and creates a new ticket.
- **Scenario 2**: User continues an existing conversation and receives updates.

### Component Details

### 1. `InputBar.tsx`
```typescript
import React, { useState } from 'react';

interface InputBarProps {
  onSend: (content: string) => void;
  disabled: boolean;
}

export function InputBar({ onSend, disabled }: InputBarProps) {
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSend(input);
      setInput('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="input-bar">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        disabled={disabled}
        placeholder="Type your message..."
      />
      <button type="submit" disabled={disabled}>Send</button>
    </form>
  );
}
}
```

### 2. API Integration Examples

#### Create Ticket Example
```bash
curl -X POST http://localhost:8000/api/tickets/ \
-H "Content-Type: application/json" \
-d '{"customer_name": "John Doe", "customer_email": "john@example.com", "subject": "Issue with order", "message": "I received the wrong item."}'
```

#### Process Ticket Example
```bash
curl -X POST http://localhost:8000/api/tickets/{ticketId}/process
```

## Conclusion
This project aims to create an intuitive and efficient support ticket interface that leverages AI to enhance user experience and streamline support processes.

### Endpoints Used

```typescript
// 1. Create ticket
POST /api/tickets/
Body: {
  customer_name: string;
  customer_email: string;
  subject: string;
  message: string;
}
Response: {
  id: string;
  status: "new";
  created_at: string;
}

// 2. Process ticket (AI response)
POST /api/tickets/{ticketId}/process
Response: {
  triage: {
    category: string;
    priority: "P1" | "P2" | "P3";
    sentiment: string;
    suggested_team: string;
  };
  answer_draft: {
    greeting: string;
    body: string;
    closing: string;
  };
}

// 3. Get conversation history (future)
GET /api/tickets/{ticketId}/messages
Response: Message[]
```

---

## Best Practices

### Performance
- ✅ Use `React.memo` for message bubbles
- ✅ Virtualize long message lists (react-window)
- ✅ Debounce input if needed
- ✅ Lazy load debug panel

### Accessibility
- ✅ ARIA labels for buttons
- ✅ Keyboard navigation (Tab, Enter, Escape)
- ✅ Screen reader announcements for new messages
- ✅ Focus management (input auto-focus)

### Error Handling
- ✅ Show error messages in chat
- ✅ Retry mechanism for failed requests
- ✅ Offline indicator
- ✅ Graceful degradation

### Testing
- ✅ Unit tests for hooks
- ✅ Component tests for UI
- ✅ E2E test for full conversation flow
- ✅ Mock API responses

---

## Implementation Checklist

### Phase 1: Basic Chat (MVP)
- [ ] ChatContainer component
- [ ] MessageList component
- [ ] MessageBubble component
- [ ] InputBar component
- [ ] useChat hook
- [ ] API integration
- [ ] Basic styling

### Phase 2: Enhanced UX
- [ ] TypingIndicator component
- [ ] Auto-scroll to bottom
- [ ] Timestamp formatting
- [ ] Metadata display (category, priority)
- [ ] Error messages
- [ ] Loading states

### Phase 3: Debug Panel (Optional)
- [ ] DebugPanel component
- [ ] ToolCallsLog component
- [ ] MemorySnapshot component
- [ ] LogViewer component
- [ ] Toggle functionality
- [ ] Tab navigation

### Phase 4: Polish
- [ ] Animations
- [ ] Responsive design
- [ ] Dark mode (optional)
- [ ] Markdown support
- [ ] Code syntax highlighting
- [ ] Copy message button

---

## Example Usage

```tsx
// App.tsx
import { ChatContainer } from './components/chat/ChatContainer';

function App() {
  const [showDebug, setShowDebug] = useState(false);

  return (
    <div className="app">
      <header>
        <h1>SupportAI</h1>
        <button onClick={() => setShowDebug(!showDebug)}>
          {showDebug ? 'Hide' : 'Show'} Debug
        </button>
      </header>
      
      <main>
        <ChatContainer showDebug={showDebug} />
      </main>
    </div>
  );
}
```

---

## Success Criteria

✅ **Functional:**
- Users can send messages
- AI responds with helpful answers
- Conversation flows naturally
- All API calls work correctly

✅ **Visual:**
- Looks like ChatGPT interface
- Clean, modern design
- Smooth animations
- Responsive on mobile

✅ **Technical:**
- TypeScript strict mode enabled
- No console errors
- < 100ms interaction latency
- Accessible (WCAG 2.1 AA)

---

## Notes for Developer

- **Start with Phase 1 (MVP)** - Get basic chat working first
- **Use existing Tickets.tsx** as reference for API calls
- **Test with real backend** at http://localhost:8000
- **Copilot will help** with boilerplate and TypeScript types
- **Ask questions** if API response format is unclear

Good luck! 🚀
