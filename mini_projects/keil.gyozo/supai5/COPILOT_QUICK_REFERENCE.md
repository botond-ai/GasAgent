# Quick Reference: ChatGPT-Style Ticket Interface

## 🎯 Goal
Transform the current ticket form into a ChatGPT-like conversational interface for customer support.

---

## 📦 Tech Stack
- React 18 + TypeScript
- Vite
- CSS Modules or Tailwind
- Native fetch API

---

## 🎨 UI Layout

```
┌──────────────────────────────────┐
│  SupportAI Chat                  │
├──────────────────────────────────┤
│                                  │
│  [Scrollable Chat Messages]     │
│                                  │
│  👤 User: My order issue...     │
│  🤖 AI: I can help with that... │
│     Category: Billing | P1      │
│                                  │
├──────────────────────────────────┤
│  [Type message...] [Send 📤]    │
└──────────────────────────────────┘
```

---

## 📁 Component Structure

```
components/chat/
├── ChatContainer.tsx      # Main wrapper
├── MessageList.tsx        # Scrollable list
├── MessageBubble.tsx      # Individual message
├── InputBar.tsx           # Input + send button
└── TypingIndicator.tsx    # "AI is typing..."

hooks/
├── useChat.ts            # Chat state & API
└── useTicketAPI.ts       # Backend calls

types/
└── chat.ts               # TypeScript interfaces
```

---

## 🔧 Core Types

```typescript
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  metadata?: {
    category?: string;
    priority?: 'P1' | 'P2' | 'P3';
    sentiment?: string;
  };
}
```

---

## 🔌 API Calls

```typescript
// 1. Create ticket (first message)
POST /api/tickets/
{
  customer_name: string;
  customer_email: string;
  subject: string;  // First message truncated
  message: string;   // Full first message
}

// 2. Get AI response
POST /api/tickets/{ticketId}/process
→ Returns: { triage: {...}, answer_draft: {...} }
```

---

## 💡 Key Features

### Must Have:
✅ Messages scroll to bottom automatically  
✅ User messages on right (blue bubble)  
✅ AI messages on left (gray bubble)  
✅ Input bar fixed at bottom  
✅ "AI is typing..." indicator  
✅ Show category/priority metadata  

### Nice to Have:
⭐ Debug panel (collapsible sidebar)  
⭐ Markdown support in messages  
⭐ Copy message button  
⭐ Dark mode  

---

## 🎨 Styling Reference

**ChatGPT Colors:**
```css
--user-bg: #DCF8C6;      /* Light green */
--ai-bg: #F5F5F5;        /* Light gray */
--background: #FFFFFF;    /* White */
--input-bg: #FAFAFA;     /* Very light gray */
```

**Message Bubble:**
```css
.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  margin-bottom: 16px;
  animation: fadeIn 0.3s ease-in;
}
```

---

## 🪝 useChat Hook (Core Logic)

```typescript
export function useChat(ticketId?: string) {
  const [messages, setMessages] = useState<Message[]>([
    { 
      role: 'assistant', 
      content: 'Hi! How can I help?',
      ...
    }
  ]);
  const [isLoading, setIsLoading] = useState(false);

  const createTicket = async (content: string) => {
    // 1. Add user message to UI
    setMessages(prev => [...prev, userMessage]);
    
    // 2. Create ticket via API
    const ticket = await fetch('/api/tickets/', {...});
    
    // 3. Process ticket (get AI response)
    const result = await fetch(`/api/tickets/${ticket.id}/process`, {...});
    
    // 4. Add AI response to UI
    setMessages(prev => [...prev, aiMessage]);
  };

  return { messages, isLoading, createTicket };
}
```

---

## 🐛 Debug Panel (Optional)

**Three Tabs:**
1. **Tools** - API calls made (intent detection, RAG search, etc.)
2. **Memory** - Workflow state, preferences
3. **Logs** - Minimal INFO logs

**Toggle Button:**
```tsx
<button onClick={() => setShowDebug(!showDebug)}>
  🐛 Debug
</button>
```

---

## ✅ Implementation Steps

1. **Phase 1 - Basic Chat (1-2 hours)**
   - [ ] Create components (ChatContainer, MessageBubble, InputBar)
   - [ ] Implement useChat hook
   - [ ] Connect to backend API
   - [ ] Basic styling

2. **Phase 2 - UX Polish (1 hour)**
   - [ ] Auto-scroll to bottom
   - [ ] Typing indicator
   - [ ] Metadata display
   - [ ] Error handling

3. **Phase 3 - Debug Panel (optional)**
   - [ ] Create DebugPanel component
   - [ ] Add tabs for tools/memory/logs
   - [ ] Toggle functionality

---

## 🚀 Quick Start

```bash
# 1. Create new files
touch src/components/chat/ChatContainer.tsx
touch src/hooks/useChat.ts
touch src/types/chat.ts

# 2. Start with ChatContainer skeleton
# 3. Add MessageList and MessageBubble
# 4. Implement useChat hook
# 5. Connect to API
# 6. Style with CSS
```

---

## 📖 Reference Links

- **Existing API:** http://localhost:8000/docs
- **Current Tickets.tsx:** See existing implementation for API patterns
- **ChatGPT UI:** Use as visual reference

---

## 🎓 Tips for Copilot

When writing code, use these comments to guide Copilot:

```typescript
// Create a ChatGPT-style message bubble component
// User messages should be on the right with blue background
// AI messages on the left with gray background

// Implement auto-scroll to bottom when new message arrives
// Use useEffect with dependency on messages array

// Format AI response: combine greeting, body, and closing
// Add metadata badges for category and priority
```

---

**Start coding! Copilot will help you build this step by step.** 🤖
