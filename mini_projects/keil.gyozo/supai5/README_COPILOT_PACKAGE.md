# 🤖 ChatGPT-Style Ticket Interface - Developer Package

Ez a csomag mindent tartalmaz amit a frontend ticket rendszer ChatGPT-szerű interfésszé alakításához szükséges.

---

## 📦 Mit tartalmaz?

### 1. Developer Prompts (Copilot számára)
- **COPILOT_DEVELOPER_PROMPT.md** - Részletes, teljes útmutató (4000+ szó)
- **COPILOT_QUICK_REFERENCE.md** - Gyors referencia (kódolás közben)

### 2. TypeScript Type Definitions
- **chat.ts** - Összes TypeScript interface és type (copy-paste ready)

### 3. Working Examples (Használatra kész kód)
- **useChat.example.ts** - Teljes useChat hook implementáció
- **ChatContainer.example.tsx** - Főkomponens példa
- **ChatContainer.example.css** - ChatGPT-stílusú CSS

---

## 🚀 Hogyan használd?

### Opció 1: Teljes Copilot-vezérelt fejlesztés

1. **Nyisd meg a projektet VS Code-ban**
2. **Olvasd el:** `COPILOT_DEVELOPER_PROMPT.md`
3. **Másold be a prompt-ot** Copilot Chat-be (Ctrl+Shift+I)
4. **Kezdd el írni a kódot** - Copilot segít minden lépésben
5. **Használd a Quick Reference-t** ha elakadsz

**Prompt használata Copilot-tal:**
```
Copilot Chat-ben:
"@workspace Create a ChatGPT-style chat interface based on the 
COPILOT_DEVELOPER_PROMPT.md file. Start with the basic chat 
components (ChatContainer, MessageBubble, InputBar)."
```

### Opció 2: Használd a példakódokat

1. **Másold a type definitions-t:**
   ```bash
   cp chat.ts src/types/chat.ts
   ```

2. **Másold a useChat hook-ot:**
   ```bash
   cp useChat.example.ts src/hooks/useChat.ts
   ```

3. **Másold a ChatContainer-t:**
   ```bash
   cp ChatContainer.example.tsx src/components/chat/ChatContainer.tsx
   cp ChatContainer.example.css src/components/chat/ChatContainer.css
   ```

4. **Használd az App.tsx-ben:**
   ```tsx
   import { ChatContainer } from './components/chat/ChatContainer';
   
   function App() {
     return <ChatContainer showDebug={true} />;
   }
   ```

### Opció 3: Hibrid megközelítés

1. Kezdj az example fájlokkal (gyors start)
2. Testre szabd Copilot segítségével
3. Használd a prompts-okat új funkciókhoz

---

## 📋 Fájlok részletesen

### COPILOT_DEVELOPER_PROMPT.md
**Méret:** ~4000 szó  
**Tartalom:**
- Teljes projekt kontextus
- Tech stack leírás
- UI/UX követelmények
- Komponens struktúra
- API integráció
- Debug panel tervek
- Styling guidelines
- Best practices
- Implementation checklist

**Mikor használd:**
- Projekt indításkor
- Új fejlesztő onboarding
- Komplexebb funkciók implementálásakor
- Copilot Chat-tel való munkánál

### COPILOT_QUICK_REFERENCE.md
**Méret:** ~1500 szó  
**Tartalom:**
- Tömör összefoglaló
- Gyors UI layout
- Komponens lista
- Core types
- API calls
- Quick start steps

**Mikor használd:**
- Kódolás közben
- Gyors lookup-ra
- Ha csak a lényeg kell

### chat.ts
**Típusok:**
- Message, Conversation
- API request/response types
- Component props
- Hook return types
- Utility types
- Type guards

**Használat:**
```typescript
import type { Message, UseChatReturn } from './types/chat';
```

### useChat.example.ts
**Teljes useChat hook implementáció:**
- Message state management
- API calls (create ticket, process)
- Error handling
- Loading states
- Helper functions

**Használat:**
Másold `src/hooks/useChat.ts`-be és testre szabd.

### ChatContainer.example.tsx
**Főkomponens:**
- Chat layout
- MessageBubble komponens
- TypingIndicator
- Debug panel
- Auto-scroll
- Timestamp formatting

**Használat:**
Másold `src/components/chat/ChatContainer.tsx`-be.

### ChatContainer.example.css
**ChatGPT-stílusú design:**
- Message bubbles
- Input bar
- Typing indicator animáció
- Debug panel layout
- Responsive design
- Dark mode (optional)

**Használat:**
Másold `src/components/chat/ChatContainer.css`-be.

---

## 🎯 Implementációs Út

### Fázis 1: Setup (10 perc)
```bash
# 1. Types
mkdir -p src/types
cp chat.ts src/types/

# 2. Hooks
mkdir -p src/hooks
cp useChat.example.ts src/hooks/useChat.ts

# 3. Components
mkdir -p src/components/chat
cp ChatContainer.example.tsx src/components/chat/ChatContainer.tsx
cp ChatContainer.example.css src/components/chat/ChatContainer.css
```

### Fázis 2: Integráció (20 perc)
```tsx
// src/App.tsx
import { ChatContainer } from './components/chat/ChatContainer';

function App() {
  return (
    <div className="app">
      <ChatContainer showDebug={true} />
    </div>
  );
}
```

### Fázis 3: Tesztelés (10 perc)
1. Indítsd el a frontend-et: `npm run dev`
2. Nyisd meg: http://localhost:5173
3. Írj egy üzenetet
4. Ellenőrizd az AI választ

### Fázis 4: Testreszabás (változó)
- Színek módosítása
- További funkciók (Copilot-tal)
- Debug panel kibővítése

---

## 💡 Copilot Tippek

### Inline Suggestions

Használj leíró kommenteket:
```typescript
// Create a message bubble that displays on the right for user messages
// and on the left for AI messages, with rounded corners and shadow
```

### Copilot Chat Parancsok

```
# Új komponens létrehozása
@workspace Create a TypingIndicator component that shows three 
animated dots when the AI is processing

# Refactoring
@workspace Refactor the MessageBubble component to support 
markdown rendering

# Styling
@workspace Add animations to message bubbles (fade in from bottom)

# Bug fix
@workspace Fix the auto-scroll behavior when new messages arrive
```

### Code Completion

Copilot automatikusan felismeri a mintákat:
- Típusokat használ a chat.ts-ből
- API hívásokat az example-ből
- Styling pattern-eket a CSS-ből

---

## 🔧 Testreszabási Példák

### Saját színséma

```css
/* ChatContainer.css */
:root {
  --user-message-bg: #YOUR_COLOR;
  --ai-message-bg: #YOUR_COLOR;
  --accent-color: #YOUR_COLOR;
}
```

### Markdown támogatás

```bash
npm install react-markdown
```

```tsx
import ReactMarkdown from 'react-markdown';

<ReactMarkdown>{message.content}</ReactMarkdown>
```

### Avatar hozzáadása

```tsx
<div className="message-wrapper">
  <img src={avatarUrl} alt="" className="avatar" />
  <div className="message-bubble">...</div>
</div>
```

---

## 📊 Összehasonlítás: Régi vs. Új

| Feature | Régi (Form) | Új (Chat) |
|---------|-------------|-----------|
| UX | Statikus form | Interaktív beszélgetés |
| Feedback | Csak sikeres submit után | Azonnali, üzenetenként |
| Metadata | Rejtett | Látható (category, priority) |
| Multi-turn | ❌ | ✅ (future) |
| Debug info | ❌ | ✅ (optional panel) |
| Mobile UX | OK | Kiváló |

---

## ✅ Checklist - Mielőtt Production-be megy

- [ ] TypeScript strict mode: nincs error
- [ ] Minden komponens type-safe
- [ ] API calls error handling
- [ ] Loading states mindenhol
- [ ] Auto-scroll működik
- [ ] Keyboard navigation (Enter, Esc)
- [ ] Mobile-responsive
- [ ] Accessibility (ARIA labels)
- [ ] Error messages user-friendly
- [ ] Debug panel toggle működik

---

## 🆘 Segítség

### Ha elakadnál:

1. **Nézd meg az example kódokat** - működő implementációk
2. **Olvasd el a Quick Reference-t** - gyors válaszok
3. **Kérdezd meg Copilot-ot** - használd a prompt-okat
4. **Check the API docs** - http://localhost:8000/docs

### Gyakori problémák:

**"Cannot find module './types/chat'"**
→ Másold a chat.ts-t `src/types/`-ba

**"Fetch failed"**
→ Ellenőrizd: backend fut-e (http://localhost:8000)

**"Auto-scroll nem működik"**
→ Ellenőrizd a messagesEndRef és useEffect implementációt

---

## 🎉 Kész!

**Most már mindened megvan:**
- ✅ Részletes prompts Copilot-hoz
- ✅ TypeScript type definitions
- ✅ Working example kódok
- ✅ ChatGPT-stílusú CSS
- ✅ Implementation guide

**Kezdj neki! Copilot segít minden lépésben.** 🚀

---

**Készítette:** Claude  
**Verzió:** 1.0  
**Dátum:** 2026-01-23  
**Projekt:** SupportAI ChatGPT-style Interface
