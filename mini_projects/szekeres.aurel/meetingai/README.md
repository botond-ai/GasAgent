
## 1. AI Meeting Assistant

**Projekt név:** MeetingAI  
**Alcím:** Jegyző + Feladatkiosztó + Összegző Agent

### Koncepció

Egy AI agent, ami meeting jegyzetből vagy transcript-ből automatikusan:
- ✅ **Összefoglalót készít** (executive summary)
- ✅ **Akciópontokat gyűjt ki** (to-do lista tulajdonosokkal)
- ✅ **Elmenti** JSON formátumban vagy Jira API-n keresztül
- ✅ **Időpontot foglal** calendar-ban API-n keresztül
- ✅ **Email-t küld** a megfelelő személynek a szükséges kéréssel, információval

### Előnyök

| Szempont | Részletek |
|----------|-----------|
| **Egyszerű indulás** | Sima TXT vagy transcript feldolgozása, nincs szükség külső API-kra |
| **LangGraph példák** | Document input → LLM summarization → JSON output |
| **Bővíthetőség** | Memóriával (korábbi meetingek), feladatrögzítéssel, Slack/Teams integrációval |
| **Üzleti érték** | Időmegtakarítás, egységes dokumentáció, követhetőség |

### Végeredmény Output-ok

**1. Meeting Summary (Összefoglaló)**
```json
{
  "meeting_id": "MTG-2025-12-09-001",
  "title": "Q4 Sprint Planning",
  "date": "2025-12-09",
  "participants": ["János", "Péter", "Maria"],
  "summary": "A csapat megvitatta a Q4 sprintek prioritásait. Megállapodtak a login feature véglegesítésében és a teljesítmény-optimalizálásban.",
  "key_decisions": [
    "Login feature lesz a P1 prioritás",
    "Performance audit Q4 végéig"
  ],
  "next_steps": [
    "UI mockup review - János - Dec 12",
    "Backend API setup - Péter - Dec 15"
  ]
}
```

**2. Task List (Feladatlista)**
```json
{
  "tasks": [
    {
      "task_id": "TASK-001",
      "title": "UI mockup review készítése",
      "assignee": "János",
      "due_date": "2025-12-12",
      "priority": "P1",
      "status": "to-do",
      "meeting_reference": "MTG-2025-12-09-001"
    },
    {
      "task_id": "TASK-002",
      "title": "Backend API setup - login endpoint",
      "assignee": "Péter",
      "due_date": "2025-12-15",
      "priority": "P1",
      "status": "to-do",
      "meeting_reference": "MTG-2025-12-09-001"
    }
  ]
}
```

**3. Jira Integration (Opcionális)**
- Automatikus ticket létrehozás Jira API-n keresztül
- Assignee beállítása
- Priority és due date szinkronizálás

### LangGraph Workflow

```
┌─────────────────┐
│  Document Input │  (TXT/Transcript)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Parse & Split │  (Chunking)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Summarize Node │  (LLM - executive summary)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Extract Actions │  (LLM - to-do extraction)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Structure JSON │  (Validation + Schema)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Save Output   │  (JSON file / Jira API)
└─────────────────┘
```

### Technikai Stack

**Backend:**
- Python 3.11+
- LangChain + LangGraph
- OpenAI GPT-4 / Claude
- Jira Python SDK (opcionális)
- Pydantic (JSON schema validation)

**Input formátumok:**
- Plain TXT
- Markdown
- SRT (subtitle format)
- DOCX

**Output formátumok:**
- JSON
- Markdown report
- Jira tickets (API)
- Slack/Teams message (webhook)

### Bővítési Lehetőségek

1. **Memory Integration**
   - Korábbi meetingek context-je
   - Résztvevők profiljai
   - Projekt history

2. **Slack/Teams Bot**
   - Meeting után automatikus összefoglaló post
   - Task assignee-k értesítése
   - Follow-up reminder 24h előtt

3. **Voice Transcript Integration**
   - Google Meet / Zoom transcript import
   - Speaker diarization (ki mit mondott)
   - Sentiment analysis