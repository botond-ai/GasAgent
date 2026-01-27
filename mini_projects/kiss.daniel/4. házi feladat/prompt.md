# Copilot prompt (HU) – LangGraph AI agent tervezése és generáltatása

## Kontextus / szerep

Te egy senior Python engineer és AI agent-architekt vagy. Generálj egy **production-ready** (de minimalista) Python projektet, amely egy LangGraph-alapú AI agentet valósít meg.

A megoldás következetesen használja:

* **LangGraph**
* **ToolNode**
* **Pydantic**

## LLM futtatás (Ollama)

Az agent LLM-je **Ollama**-n fusson.

* A projekt tartalmazzon egy vékony LLM-klienst, amely HTTP-n hívja az Ollama API-t.
* **Konfiguráció:** LLM beállítások `.env`-ből jönnek (python-dotenv):

  * `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
  * `OLLAMA_TIMEOUT_S` (default: 60)
  * `OLLAMA_TEMPERATURE` (default: 0.2)

### Elérhető modellek (a környezetben)

* `gpt-oss:20b`
* `qwen2.5:14b-instruct`
* `llama3.1:8b`
* `phi3.5:latest`
* `llama3.2:3b`
* `llama3.2-vision:latest`

### Modellválasztás és ajánlott hozzárendelés node-onként

Implementálj **modell-routing** stratégiát: külön modell lehessen a különböző feladatokra (Planner vs extraction vs final), `.env`-ből állíthatóan, ésszerű fallback-ekkel.

**Ajánlott alapértelmezések ehhez a projekthez (meeting notes → summary + extraction + calendar event):**

* **Planner (Step List tervezés, döntési pontok):** `gpt-oss:20b` *(QUALITY)*, különben `qwen2.5:14b-instruct` *(BALANCED)*

  * Indok: összetett, agent-szerű tervezési feladatoknál erős következetesség; Qwen jó alternatíva, ha a 20B túl nehéz.

* **ExtractNextMeetingDetails (adatkinyerés, normalizált mezők):** `gpt-oss:20b` *(QUALITY)*, különben `qwen2.5:14b-instruct` *(BALANCED)*

  * Indok: pontosság és kontextus-összefűzés kritikus (dátum/idő/agenda/attendees); Qwen stabil structured extraction-re.

* **SummarizeNotes (üzleti összefoglaló):** `llama3.1:8b` *(BALANCED)*, quality módban `gpt-oss:20b`

  * Indok: gyorsabb futás, jó összefoglalóminőség; ha a jegyzetek nagyon kuszák, a 20B segít.

* **ComposeFinalAnswer (formatált végső válasz, JSON + emberi blokk):** `llama3.1:8b`

  * Indok: stabil, konzisztens szövegformálás; a kritikus extraction már megtörtént.

#### Fontos: gpt-oss „response format”

* A `gpt-oss:20b` modellek tipikusan egy kötöttebb, fejlesztőbarát válaszformátummal működnek jól.
* Implementálj a kódban egy **formatter/wrapper** réteget az Ollama kliensben:

  * ahol szükséges, kényszerítsd a választ **szigorúan JSON**-ra (Pydantic séma),
  * és ha a modell nem tartja a formátumot, aktiváld a **Fallback model** mintát.

**Kis erőforrás / gyors mód (fallback):**

* Ha a gépen kevés a RAM/VRAM vagy gyors futás kell:

  * Planner/Extractor: `phi3.5:latest`
  * Summarizer/Final: `llama3.2:3b` vagy `phi3.5:latest`

**Profilok (ajánlott, `.env`-ből választható):**

* `AGENT_PROFILE=QUALITY`:

  * Planner/Extractor: `gpt-oss:20b`
  * Summarizer: `gpt-oss:20b`
  * Final: `llama3.1:8b`
* `AGENT_PROFILE=BALANCED` (default):

  * Planner/Extractor: `qwen2.5:14b-instruct`
  * Summarizer/Final: `llama3.1:8b`
* `AGENT_PROFILE=FAST`:

  * Planner/Extractor: `phi3.5:latest`
  * Summarizer/Final: `llama3.2:3b`

**Vision modell használata:**

* `llama3.2-vision:latest` **csak akkor** legyen használva, ha a bemenet képi (pl. screenshot, fotózott jegyzet, diagram) vagy multimodális forrásból jön. Ebben a feladatban (szöveges jegyzet) defaultból ne használd.

**Embedding modell (opcionális, de ajánlott):**

* `mxbai-embed-large:latest` használható:

  * deduplikációra (ugyanazon meeting notes ismétlődő feldolgozásának felismerése),
  * „similarity” alapú template-választásra,
  * későbbi bővítésként jegyzet-archívumhoz (RAG) és gyors visszakereséshez.

### `.env` kulcsok a modell-routinghoz

A következő változókat kezeld (defaultokkal):

* `AGENT_PROFILE` (default: `BALANCED`, opciók: `FAST|BALANCED|QUALITY`)
* `OLLAMA_MODEL_PLANNER` (default: profiltól függ)
* `OLLAMA_MODEL_EXTRACTOR` (default: profiltól függ)
* `OLLAMA_MODEL_SUMMARIZER` (default: profiltól függ)
* `OLLAMA_MODEL_FINAL` (default: profiltól függ)
* `OLLAMA_EMBED_MODEL` (default: `mxbai-embed-large:latest`)
* `OLLAMA_MODEL_FALLBACKS` (pl. CSV: `gpt-oss:20b,qwen2.5:14b-instruct,llama3.1:8b,phi3.5:latest,llama3.2:3b`)

### Validáció az indításkor

* Induláskor kérdezd le az elérhető modelleket (`/api/tags`) és ellenőrizd, hogy a megadott modellek elérhetők-e.
* Ha nem elérhető:

  * dobj érthető hibát,
  * sorold fel az elérhető modelleket,
  * és javasolj automatikus fallback-et a `OLLAMA_MODEL_FALLBACKS` alapján.

## Célfeladat

Bemenetként kapunk **egy megbeszélés jegyzeteit** (szabad szöveg). Az agent:

1. készít belőle **tömör, üzleti jellegű összefoglalót** (döntések, nyitott kérdések, feladatok, felelősök, határidők)
2. **kigyűjti** a következő időpontra (következő meeting / follow-up) vonatkozó adatokat (dátum, idő, időzóna, időtartam, hely/meeting link, résztvevők, téma/cím, agenda)
3. a kinyert adatok alapján **Google Naptár eseményt hoz létre**
4. a végén visszaad egy **Final Answer** választ: összefoglaló + kinyert adatok + létrehozott esemény meta (event id, link)

## Kötelező agent-folyamat (graph)

A LangGraph folyamat pontosan ezt az alap felépítést kövesse:

User → Planner → Step List → Executor Loop

↓

Router → Tool

↓

Observation

↓

Update State

↓

Next Step?

↓ No

Final Answer

### Kötelező csomópontok (node) és felelősségek

* **Planner**: Step List felépítése, állapot inicializálás.
* **Executor Loop**: step-by-step végrehajtás, hibatűrés, megszakítás.
* **Router**: kizárólag tool-hívások döntése (melyik tool, milyen inputtal).
* **ToolNode**: tool futtatás.
* **Observation**: tool kimenet rögzítése.
* **Update State**: AgentState frissítése (összefoglaló, event_details, naptár eredmény, warnings, errors).
* **Next Step?**: kilépési feltétel (összes step done vagy fatal error vagy visszakérdezés szükséges).
* **Final Answer**: determinisztikus formátumú végső válasz.

## 0) Rétegzett architektúra (kötelező)

A generált agent 4 rétegű felépítést kövessen. A kódban és a README-ben is jelenjen meg a rétegek szétválasztása.

1. **Reasoning layer (LLM döntések)**

   * Prompting, triage, routing, strukturált kimenetek (Pydantic-séma szerinti JSON)
   * A „chain-of-thought” jellegű belső gondolatmenetet **ne** logold vagy ne add vissza; helyette rövid, auditálható **rationale** mezőket használj (1–3 mondat), ha szükséges.
   * Node-onként külön prompt, külön modell (modell-routing) támogatása.

2. **Operational layer (workflow)**

   * LangGraph: node-ok, edge-ek, State (Pydantic)
   * Determinisztikus step-executor loop, hibatűrés, megszakítási feltételek

3. **Tool execution layer (külső API-k)**

   * ToolNode + explicit tool interfészek (Google Calendar create_event, opcionális conflict check)
   * Tool hívások izolált modulban, könnyen mockolható

4. **Memory / RAG / context handling**

   * Stateful működés: AgentState és per-run artefaktok
   * **Retrieval-before-tools**: mielőtt külső toolt hívsz (pl. naptárírás), előbb futtass retrieval / kontextus-ellenőrzést:

     * deduplikáció (ugyanazon meeting notes vagy azonos event candidate),
     * releváns múltbeli események/meeting pattern visszakeresése (opcionális bővítés).
   * Az embedding modell (`mxbai-embed-large`) használata opcionális, de a struktúrát építsd be: `memory/` modul + in-memory vagy egyszerű file-alapú store.

### Retrieval-before-tools minimál implementáció (kötelező)

* Implementálj egy `MemoryStore` absztrakciót (interface):

  * `upsert_run(run_id, notes_hash, summary, event_details, created_event_id)`
  * `find_similar_notes(notes_text) -> list[Match]` (embeddinggel vagy hash alapú fallback)
  * `find_similar_event_candidate(event_details) -> list[Match]`
* **Döntési szabály:** ha magas egyezés van, akkor:

  * vagy `dry-run`-ként áll meg és jelzi a duplikáció kockázatát,
  * vagy kér „megerősítést” (interaktív módban),
  * nem ír automatikusan a naptárba.

## Tervezési elvárások

### 1) Pydantic modellek (erősen típusos state)

Hozz létre Pydantic modelleket legalább az alábbiakhoz:

* **MeetingNotesInput**: `notes_text`, opcionális `user_timezone` (default: `Europe/Budapest`), opcionális `calendar_id` (default: `primary`)
* **EventDetails**: `title`, `start_datetime`, `end_datetime`, `timezone`, `location`, `attendees` (email lista), `description`, `conference_link` (opcionális), `source_confidence` (0–1), `extraction_warnings` (lista)
* **Step**: `id`, `name`, `tool_name` (opcionális), `inputs` (dict), `status` (planned/running/done/failed), `result` (opcionális)
* **AgentState**: `input`, `summary`, `decisions`, `actions`, `risks_open_questions`, `event_details`, `steps`, `current_step_index`, `tool_observations`, `calendar_event_result`, `errors`

### 2) Planner és Step List

* A **Planner** node feladata: meghatározni a cél eléréséhez szükséges lépéseket és létrehozni egy Step List-et.
* A Step List minimum lépései (de bővíthető):

  1. `SummarizeNotes`
  2. `ExtractNextMeetingDetails`
  3. `ValidateAndNormalizeEventDetails` (időtartam default, időzóna default, hiányzó mezők kezelése)
  4. `CreateGoogleCalendarEvent` (Tool használattal)
  5. `ComposeFinalAnswer`

### 3) Executor Loop

* Iterál a Step List-en.
* Minden iterációban:

  * Router dönt: kell-e tool, és melyik tool
  * ToolNode meghívás (ha szükséges)
  * Observation rögzítése
  * State frissítése
  * Next Step döntés

### 4) Router + ToolNode

* Router csak a tool-hívások routolását végzi (pl. `create_calendar_event`).
* Kötelező legalább 1 eszköz:

  * **GoogleCalendarTool.create_event(event: EventDetails, calendar_id: str) -> CalendarEventResult**
* Opcionális (ha érdemi, de ne legyen túlzás):

  * `GoogleCalendarTool.find_conflicts(...)` vagy `resolve_timezone(...)`

### 5) Google Calendar integráció

* Implementáld a Google Calendar esemény létrehozását a projektben.
* **Konfiguráció:** a szükséges kulcsokat és beállításokat **a `.env` fájlból** töltsd be (python-dotenv).

  * A kód ne hardcode-oljon titkokat; minden autentikációs és API paraméter a környezeti változókból jöjjön.
  * A README-ben dokumentáld, mely `.env` kulcsokat vár a program (azokkal a nevekkel, ahogy a `.env.example`-be bekerülnek).
* **Auth megközelítés:** implementálj egy működőképes alapértelmezettet, amely `.env` alapján választ:

  * Ha van service account kulcs (pl. JSON path / JSON string): használd azt.
  * Egyébként OAuth kliens (client_id/client_secret + token cache) mód.
* Minimális mezők: `summary/title`, `start`, `end`, `description`, `location`, `attendees`.
* Ha van meeting link, tedd bele a `description`-be és/vagy `location`-be.
* Eredmény: `event_id`, `htmlLink`/URL, `status`.

### Ajánlott `.env` kulcsok (a projektben **ezeket** kezeld; ha a felhasználó `.env`-je más neveket használ, igazítsd ehhez)

* `GOOGLE_CALENDAR_ID` (default: `primary`, CLI felülírhatja)
* **Service account mód** (ha elérhető):

  * `GOOGLE_SERVICE_ACCOUNT_FILE` (útvonal) **vagy** `GOOGLE_SERVICE_ACCOUNT_JSON` (JSON string)
  * `GOOGLE_IMPERSONATE_USER` (opcionális, domain-wide delegation esetén)
* **OAuth mód** (ha service account nincs):

  * `GOOGLE_OAUTH_CLIENT_ID`
  * `GOOGLE_OAUTH_CLIENT_SECRET`
  * `GOOGLE_OAUTH_REDIRECT_URI` (opcionális)
  * `GOOGLE_OAUTH_TOKEN_PATH` (token cache helye)
* Általános:

  * `APP_TIMEZONE` (default: `Europe/Budapest`)
  * `LOG_LEVEL` (default: `INFO`)

### 6) Hiányzó vagy bizonytalan adatok kezelése

* Ha **nem egyértelmű** a következő időpont (nincs dátum/idő, vagy több jelölt van):

  * állíts be `extraction_warnings`-t és `source_confidence`-t,
  * **ne hozz létre eseményt automatikusan**, hanem a Final Answer-ben adj vissza célzott kérdéseket (max 3), és javasolj egy alapértelmezett időtartamot (pl. 30 perc).
* Ha csak az időtartam hiányzik: default **30 perc**.
* Időzóna default: **Europe/Budapest**.

### 7) Megbízhatóság, idempotencia, logolás

* Adj hozzá alap logolást (pl. strukturált logok).
* Idempotencia javaslat: eseményhez generálj `dedupe_key`-t (pl. title+start hash) és opcionálisan ellenőrizd, hogy már létezik-e (ha nem implementálod a keresést, legalább dokumentáld).

### Kötelező hibakezelési minták (implementáld a graph-ban)

Az agent tartalmazza az alábbi mintákat **külön node-okkal / átlátható edge-ekkel**:

1. **Retry node**

* Cél: időszakos (transient) API hibák kezelése (Ollama timeout, Google API 429/5xx).
* Megvalósítás:

  * exponenciális backoff + jitter (max N próbálkozás)
  * csak bizonyos hibakódokra (429, 500–503) és hálózati timeoutokra
  * retries kimenetét rögzítsd az `errors`/`tool_observations` mezőkben

2. **Fallback model**

* Cél: modell-eszkaláció vagy degradáció.
* Megvalósítás:

  * ha egy node (pl. extraction) nem tud Pydantic-ot validálható JSON-t adni, vagy alacsony confidence-et ad, akkor:

    * futtasd újra erősebb modellen (`qwen2.5:14b-instruct`),
    * ha a strong modell sem elérhető, menj a `OLLAMA_MODEL_FALLBACKS` listán.
  * `source_confidence` és `extraction_warnings` alapján döntési szabály.

3. **Fail-safe response**

* Cél: auditált, biztonságos hibaüzenet és kimenet.
* Megvalósítás:

  * A Final Answer mindig adjon:

    * futás-azonosítót (run_id),
    * rövid hiba-összegzést (nem szenzitív),
    * javasolt következő lépéseket,
    * és **tiltsa** a részleges/inkonzisztens naptárírást.
  * Ne logolj titkokat; `.env` értékeket maszkolj.

4. **Planner fallback (replan)**

* Cél: sikertelen tool vagy validation után újratervezés.
* Megvalósítás:

  * Ha a ToolNode sikertelen (nem transient), vagy a Guardrail blokkol:

    * térj vissza a Planner node-ba egy „replan” flaggel,
    * generálj új Step List-et (pl. hiányzó adatok bekérése, dry-run mód, alternatív tool-lépések).

5. **Guardrail node (szabályellenőrzés / compliance)**

* Cél: szabályellenőrzés még a tool-hívás előtt.
* Megvalósítás:

  * külön node: `GuardrailCheck` a `CreateGoogleCalendarEvent` előtt
  * ellenőrizd:

    * van-e elég adat a naptáríráshoz (min. cím + start + end/timezone)
    * nincs-e tiltott/szenzitív tartalom beemelve a description-be (pl. titkok, jelszavak)
    * a felhasználói szándék teljesül-e (ha bizonytalan időpont → ne írjon automatikusan)
  * Eredmény:

    * `allow: bool`, `reasons: list[str]`, `required_questions: list[str]`
  * Ha `allow == false`: Planner fallback vagy fail-safe.

## 8) Projekt struktúra és deliverable-ek

Generálj teljes repo struktúrát, például:

* `app/agent/graph.py` (LangGraph felépítés)
* `app/agent/state.py` (Pydantic modellek)
* `app/agent/nodes.py` (Planner, Router, Executor loop, State updater, Final composer)
* `app/llm/ollama_client.py` (Ollama kliens: chat/generate + /api/tags)
* `app/tools/google_calendar.py` (Tool implementáció)
* `app/config.py` (Pydantic Settings / dotenv betöltés, központi config)
* `app/main.py` (CLI belépési pont)
* `tests/` (unit tesztek; Google Calendar tool és Ollama kliens mockolva)
* `.env.example` (összes szükséges kulcs felsorolva)
* `README.md` (setup, auth, futtatás, példa input/output)

## 9) Futtatási mód

* Legyen egy **CLI** belépési pont:

  * `python -m app.main --notes "..."`
  * opcionálisan: `--calendar-id primary`
  * opcionálisan: `--timezone Europe/Budapest`
  * opcionálisan: `--dry-run` (ne hozzon létre naptár eseményt; csak extraction + normalizálás)
* A kimenet legyen gépileg is feldolgozható (pl. JSON) + emberi olvasásra is alkalmas (összefoglaló blokk).

## LLM viselkedés a jegyzetek feldolgozásához

A kivonatolásnál kérlek ezeket a mezőket állítsd elő:

* **Summary**: 5–10 sor
* **Decisions**: bullet lista
* **Action items**: bullet lista (Owner, Due)
* **Open questions / Risks**: bullet lista
* **Next meeting proposal**: a legvalószínűbb időpont + confidence

## Minta bemenet (teszthez)

Adj a tesztekhez legalább 2 mintajegyzetet:

1. Egyértelmű következő meeting (dátum, idő, résztvevők)
2. Nem egyértelmű következő meeting (csak annyi, hogy „jövő héten valamikor”)

## Kimeneti forma (Final Answer)

A Final Answer tartalmazza:

* Összefoglaló
* Kinyert event mezők (normalizált)
* Ha létrejött: `calendar_event_result` (event id + link)
* Ha nem jött létre: célzott kérdések + mi hiányzik

## Minőségi elvárások

* Ne legyen túlkomplikált; preferáld a tiszta, olvasható, jól tagolt kódot.
* Írj rövid docstringeket a node-okhoz és a tool-hoz.
* Tesztelhetőség: a tool réteg legyen könnyen mockolható.

## Feladat a Copilot számára

A fenti specifikáció alapján generáld a projekt **összes fájlját** a megadott struktúrában. A README legyen futtatható lépésekkel, és legyen benne legalább 1 teljes példa bemenet és a várható kimenet mintája.
