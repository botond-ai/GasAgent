# AI Meeting Assistant – LangGraph házi feladat

## Rövid összefoglaló
Ez a projekt egy **LangGraph-alapú AI agent**, amely egy meeting leirat (transcript) feldolgozásával:
- **összefoglalót** készít,
- **döntéseket** és **akciópontokat** azonosít,
- a feldolgozást megelőzően egy **nyilvános REST API-t** hív meg,
- majd **validált, strukturált JSON kimenetet** generál.

A megoldás több lépéses workflow-t használ, ahol az egyes lépések elkülönített node-okként működnek.

---

## Célok
- Többlépcsős agent workflow megvalósítása LangGraph-pal
- Külső (nyilvános) API integráció demonstrálása
- Strukturált kimenet (JSON) előállítása validációval
- Reprodukálható futtatás CLI módon

---

## Funkcionalitás

### Bemenet (Input)
- Szöveges meeting leirat (`.txt` vagy `.md`)
- A leirat tartalmazhat informális beszédet, több résztvevőt, és implicit döntéseket.

### Kimenet (Output)
- Strukturált JSON a meeting metaadataival, összefoglalóval, döntésekkel, akciópontokkal
- A JSON tartalmazza a külső API-ból származó naptári kontextust is (pl. ünnepnap-e a meeting dátuma).

---

## Kötelező külső API integráció
A workflow a meeting dátuma alapján meghív egy **nyilvános REST API-t**, amely ünnepnap-információt ad vissza.

Javasolt nyilvános API:
- **Nager.Date – Public Holidays API**
- Nem igényel autentikációt
- JSON formátumú választ ad

Példa hívás:
```
GET https://date.nager.at/api/v3/PublicHolidays/{YEAR}/{COUNTRY}
```

A válasz alapján meghatározásra kerül:
- `is_holiday` (boolean)
- opcionálisan `holiday_name`

---

## Architektúra

### Állapotmodell (State)
A workflow központi állapota például az alábbi mezőket kezeli:
- `raw_text`
- `meeting_date`
- `calendar_context`
- `summary`
- `decisions`
- `action_items`
- `output`

---

## LangGraph workflow (node-ok)

1. **Extract Metadata Node**
   - meeting dátum (és opcionálisan cím) kinyerése

2. **Calendar API Node**
   - nyilvános API hívás
   - naptári kontextus meghatározása

3. **Summarize Node**
   - executive summary generálása

4. **Extract Decisions Node**
   - döntések kinyerése

5. **Extract Action Items Node**
   - feladatok, felelősök, határidők azonosítása

6. **Build Output Node**
   - strukturált JSON összeállítása
   - validáció

Logikai folyamat:
```
Raw transcript
   ↓
Extract metadata
   ↓
Public Calendar API
   ↓
Summarize
   ↓
Extract decisions
   ↓
Extract action items
   ↓
Build validated JSON output
```

---

## Példa bemenet

```
Weekly planning meeting – December 9

Participant A:
Let’s review what we discussed last week. The main focus should be stabilizing the current system.

Participant B:
Agreed. We also said that the documentation needs to be updated before Friday.

Participant C:
I can take care of that. I’ll prepare the document by December 12.

Participant B:
Since next Monday is a public holiday, we should avoid setting deadlines for that day.
```

---

## Példa kimenet (részlet)

```json
{
  "meeting": {
    "date": "2025-12-09",
    "is_holiday": false,
    "summary": "..."
  },
  "decisions": ["..."],
  "action_items": [
    {
      "task": "...",
      "owner": "Participant C",
      "due_date": "2025-12-12",
      "priority": "medium"
    }
  ]
}
```

---

## Technikai stack
- Python 3.11+
- LangChain + LangGraph
- HTTP kliens (`requests` vagy `httpx`)
- Pydantic (output validáció)
- Opcionálisan FastAPI

---

## Futtatás

```bash
python main.py --input samples/sample_transcript.txt --country HU
```

Engine választás (ha van `langgraph` telepítve, használhatod):
```bash
python main.py --input samples/sample_transcript.txt --country HU --engine langgraph
```

Lokális LLM (Ollama) használat:
- Indítsd el az Ollama-t: `ollama serve`
- Töltsd le a modellt: `ollama pull llama3.1:8b`
- Futtatás: `python main.py --input samples/sample_transcript.txt --country HU --use-llm`
- Opcionális környezeti változók: `OLLAMA_URL` (alap: `http://localhost:11434`), `OLLAMA_MODEL` (alap: `llama3.1:8b`)

Tesztek (stdlib `unittest`):
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Webes UI (statikus):
- Nyisd meg a `web/index.html` fájlt böngészőben.
- A feldolgozás kliensoldali; az ünnepnap ellenőrzés opcionálisan hívja a Nager.Date API-t.

Elvárt eredmény:
- JSON output mentése fájlba
- Konzolos státusz üzenetek

---

## Értékelési megfelelés
- Többlépcsős agent workflow
- Nyilvános API meghívás
- Strukturált JSON output
- Validáció
- Dokumentált, reprodukálható futtatás

---

## Opcionális bővítések
- Markdown riport generálás
- Batch feldolgozás
- FastAPI endpoint
- Logolás és metrikák

---

## Fejlesztési megjegyzések (publikus)

- Tartsd meg a node-ok tiszta szeparációját és a kötelező nyilvános API hívást.
- Kerüld a cég-specifikus elnevezéseket és belső endpointokat a publikus rétegben.
- Javasolt minimál fájlstruktúra: `main.py` (CLI), `graph.py` (LangGraph), `schemas.py` (Pydantic), `calendar_api.py` (Nager.Date), `prompts.py` (LLM promptok), `outputs/` (generált kimenet).

---

# AI Meeting Assistant – LangGraph Homework (ENG)

## Short Summary
This project is a **LangGraph-based AI agent** that processes a meeting transcript to:
- produce a **summary**,
- identify **decisions** and **action items**,
- call a **public REST API** before processing,
- output a **validated, structured JSON** result.

The solution uses a multi-step workflow where each step is implemented as a separate node.

---

## Goals
- Implement a multi-step agent workflow with LangGraph
- Demonstrate integration with an external (public) API
- Produce structured (JSON) output with validation
- Provide reproducible CLI execution

---

## Functionality

### Input
- Text meeting transcript (`.txt` or `.md`)
- The transcript may be informal, multi-speaker, and include implicit decisions.

### Output
- Structured JSON with meeting metadata, summary, decisions, and action items
- The JSON also includes calendar context from the external API (e.g., whether the meeting date is a public holiday).

---

## Required External API Integration
Based on the meeting date, the workflow calls a **public REST API** that returns holiday information.

Suggested public API:
- **Nager.Date – Public Holidays API**
- No authentication required
- JSON responses

Example request:
```
GET https://date.nager.at/api/v3/PublicHolidays/{YEAR}/{COUNTRY}
```

From the response, determine:
- `is_holiday` (boolean)
- optionally `holiday_name`

---

## Architecture

### State Model
The workflow’s shared state may include fields such as:
- `raw_text`
- `meeting_date`
- `calendar_context`
- `summary`
- `decisions`
- `action_items`
- `output`

---

## LangGraph Workflow (Nodes)

1. **Extract Metadata Node**
   - extract meeting date (and optionally title)

2. **Calendar API Node**
   - call the public API
   - compute calendar context

3. **Summarize Node**
   - generate an executive summary

4. **Extract Decisions Node**
   - extract decisions

5. **Extract Action Items Node**
   - identify tasks, owners, and due dates

6. **Build Output Node**
   - assemble structured JSON
   - validate output

Logical flow:
```
Raw transcript
   ↓
Extract metadata
   ↓
Public Calendar API
   ↓
Summarize
   ↓
Extract decisions
   ↓
Extract action items
   ↓
Build validated JSON output
```

---

## Example Input

```
Weekly planning meeting – December 9

Participant A:
Let’s review what we discussed last week. The main focus should be stabilizing the current system.

Participant B:
Agreed. We also said that the documentation needs to be updated before Friday.

Participant C:
I can take care of that. I’ll prepare the document by December 12.

Participant B:
Since next Monday is a public holiday, we should avoid setting deadlines for that day.
```

---

## Example Output (excerpt)

```json
{
  "meeting": {
    "date": "2025-12-09",
    "is_holiday": false,
    "summary": "..."
  },
  "decisions": ["..."],
  "action_items": [
    {
      "task": "...",
      "owner": "Participant C",
      "due_date": "2025-12-12",
      "priority": "medium"
    }
  ]
}
```

---

## Tech Stack
- Python 3.11+
- LangChain + LangGraph
- HTTP client (`requests` or `httpx`)
- Pydantic (output validation)
- Optional: FastAPI

---

## Running

```bash
python main.py --input samples/sample_transcript.txt --country HU
```

Engine selection (if `langgraph` is installed):
```bash
python main.py --input samples/sample_transcript.txt --country HU --engine langgraph
```

Local LLM (Ollama):
- Start Ollama: `ollama serve`
- Pull model: `ollama pull llama3.1:8b`
- Run: `python main.py --input samples/sample_transcript.txt --country HU --use-llm`
- Optional env vars: `OLLAMA_URL` (default: `http://localhost:11434`), `OLLAMA_MODEL` (default: `llama3.1:8b`)

Tests (stdlib `unittest`):
```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

Web UI (static):
- Open `web/index.html` in a browser.
- Processing is client-side; holiday check optionally calls the Nager.Date API.

Expected result:
- JSON output saved to a file
- Console status messages

---

## Evaluation Criteria Match
- Multi-step agent workflow
- Public API call
- Structured JSON output
- Validation
- Documented, reproducible execution

---

## Optional Extensions
- Generate a Markdown report
- Batch processing
- FastAPI endpoint
- Logging and metrics

---

## Development Notes (Public)

- Keep clean node separation and the mandatory public API call.
- Avoid company-specific naming and internal endpoints in the public layer.
- Suggested minimal file layout: `main.py` (CLI), `graph.py` (LangGraph), `schemas.py` (Pydantic), `calendar_api.py` (Nager.Date), `prompts.py` (LLM prompts), `outputs/` (generated output).
