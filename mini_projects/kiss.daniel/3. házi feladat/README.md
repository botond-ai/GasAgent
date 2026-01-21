# AI Weather Agent

Intelligens időjárás-lekérdező asszisztens LangGraph és Ollama használatával. CLI, REST API és modern web interfész támogatással.

## Funkciók

- 🌦️ **Természetes nyelvi időjárás-lekérdezés** - kérdezz magyarul, ahogy szeretnél
- 📍 **Automatikus geocoding** - felismeri a városneveket (magyar ékezetekkel is: Pécs, Szeged)
- ⏰ **Időpont felismerés** - "holnap", "nyáron", "3 nap múlva" kifejezések értelmezése
- 📊 **Aktuális és előrejelzett időjárás** - aktuális állapot és 5 napos előrejelzés támogatása
- 🇭🇺 **Csak magyar válaszok** - tömör, 2-3 mondatos válaszok
- 🛡️ **Intelligens validáció** - nem időjárási kérdéseket automatikusan elutasítja
- 🔄 **Többcsatornás elérés** - CLI, REST API, web frontend

## Követelmények

- Python 3.11+
- Ollama futó qwen2.5:14b-instruct modellel
- OpenWeather API kulcs (ingyenes regisztrációval)

## Telepítés

1. **Ollama telepítése és modell letöltése:**
```bash
# Ollama telepítés (ha még nincs): https://ollama.ai
ollama pull qwen2.5:14b-instruct
```

2. **Python függőségek telepítése:**
```bash
pip install -r requirements.txt
```

Vagy Poetry használatával:
```bash
poetry install
```

3. **Környezeti változók beállítása:**
```bash
cp .env.example .env
# Szerkeszd a .env fájlt és add meg az OpenWeather API kulcsod
```

OpenWeather API kulcs beszerzése:
- Regisztrálj: https://openweathermap.org/api
- Ingyenes API kulcs: https://home.openweathermap.org/api_keys

## Használat

### Parancssorban megadott kérdés:
```bash
python src/main.py "Milyen az időjárás Budapesten?"
```

### Interaktív mód (stdin):
```bash
python src/main.py
# Ezután írd be a kérdést a promptnál
```

### Példák:

```bash
# Aktuális időjárás
python src/main.py "Milyen az időjárás Budapesten?"

# Előrejelzés időpont felismeréssel
python src/main.py "Milyen idő lesz holnap Szegeden?"
python src/main.py "Hideg lesz 3 nap múlva Pécsett?"

# Külföldi város
python src/main.py "Mennyi a hőmérséklet Londonban?"

# Nem időjárási kérdés (elutasítva)
python src/main.py "Ki volt Magyarország első királya?"
# Válasz: "Sajnos nem tudok válaszolni erre a kérdésre."
```

## REST API

A backend Flask alapú REST API-t biztosít.

### API indítása:
```bash
cd /opt/hw3
source venv/bin/activate
python src/api.py
```

Az API a `http://localhost:5000` címen érhető el.

### API Endpointok:

#### POST /api/ask
Időjárási kérdés küldése az agentnek.

**Request:**
```json
{
  "question": "Milyen idő van Budapesten?"
}
```

**Response:**
```json
{
  "success": true,
  "answer": "Budapesten jelenleg 2 °C, gyenge köd van."
}
```

#### GET /api/health
API állapot ellenőrzése.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-16T10:30:00"
}
```

### CORS támogatás:
Az API engedélyezi a kereszt-origin kéréseket, így bármilyen frontendről hívható.

## Web Frontend

A projekt tartalmaz egy modern web interfészt is a `front/` mappában.

### Frontend futtatása:

1. **Indítsd el az API szervert** (lásd fent)

2. **Nyisd meg a frontendot böngészőben:**
```bash
# Egyszerű HTTP szerver (másik terminálban)
cd /opt/hw3/front
python3 -m http.server 8000

# Majd menj a böngészőben: http://localhost:8000
```

### Frontend funkciók:
- 🎨 Modern, reszponzív design (gradiens háttér, üveg-effekt)
- 💬 Chat-szerű interfész üzenet buborékokkal
- ⚡ Valós idejű válaszok (várható válaszidő: 30-60 mp)
- 🛡️ Hibakezelés és XSS védelem
- 🔍 Debug konzol támogatás

## Projekt struktúra

```
.
├── pyproject.toml          # Poetry konfiguráció
├── requirements.txt        # Pip függőségek
├── pytest.ini             # Pytest konfiguráció
├── .env.example           # Példa környezeti változók
├── README.md              # Ez a fájl
├── src/
│   ├── main.py            # CLI belépési pont
│   ├── api.py             # Flask REST API
│   └── agent/
│       ├── __init__.py
│       ├── graph.py       # LangGraph StateGraph definíció (4 node)
│       ├── state.py       # State modellek (Pydantic)
│       ├── llm.py         # Ollama LLM wrapper
│       ├── prompts.py     # Rendszer promptok (DECISION, ANSWER)
│       └── tools/
│           ├── __init__.py
│           ├── timeparse.py  # Időpont felismerő
│           ├── geocode.py    # Geocoding (Open-Meteo)
│           └── weather.py    # Időjárás (OpenWeather)
├── front/
│   ├── index.html         # Web interfész
│   ├── app.js             # Frontend logika
│   └── style.css          # Stílusok
└── tests/
    ├── test_agent.py      # Agent node tesztek (13)
    ├── test_api.py        # API endpoint tesztek (12)
    ├── test_geocode.py    # Geocoding tesztek (7)
    └── test_weather.py    # Weather tool tesztek (9)
```

## Működés

Az agent egy LangGraph StateGraph-ot használ 4 csomóponttal és szigorú végrehajtási sorrenddel:

1. **read_user_prompt**: Felhasználói input beolvasása
2. **decision_node**: LLM eldönti, hogy melyik eszközt kell hívni (Boolean logika)
3. **tool_node**: Eszköz végrehajtása a megadott sorrendben
4. **answer_node**: Végső válasz generálása (csak ha weather tool sikeres volt)

### Tool végrehajtási sorrend:

```
parse_time → geocode_city → get_weather → final_answer
```

- **parse_time**: Időpont felismerés a kérdésből ("holnap", "3 nap múlva", stb.)
  - Output: `days_from_now` (0-5)
  - Default: 0 (mai nap)

- **geocode_city**: Város neve → koordináták
  - Támogatja a magyar ékezeteket (Pécs, Szeged)
  - Open-Meteo Geocoding API

- **get_weather**: Időjárás lekérdezés
  - Current weather (days_from_now=0): OpenWeather `/weather` endpoint
  - Forecast (days_from_now=1-5): OpenWeather `/forecast` endpoint

- **final_answer**: LLM generál magyar nyelvű választ
  - Csak akkor fut le, ha `get_weather` sikeres volt
  - Egyébként: "Sajnos nem tudok válaszolni erre a kérdésre."

### Példa végrehajtás:

**Input:** "Milyen idő lesz holnap Budapesten?"

1. `parse_time("Milyen idő lesz holnap Budapesten?")` → days_from_now=1
2. `geocode_city("Budapest")` → lat=47.4979, lon=19.0402
3. `get_weather(lat=47.4979, lon=19.0402, days_from_now=1)` → temp=3°C, desc="clear sky"
4. `final_answer` → "Holnap Budapesten várhatóan 3°C lesz, tiszta égbolt."

### LLM döntési logika:

A `decision_node` Boolean státuszt használ:

```json
{
  "action": "call_tool",
  "tool_name": "parse_time",
  "reason": "parse_time=False"
}
```

Ha minden tool lefutott (`parse_time=True, geocode_city=True, get_weather=True`), akkor `final_answer`.

## Hibaelhárítás

**"Az időjárás szolgáltatás nem elérhető":**
- Ellenőrizd, hogy az OpenWeather API kulcs helyes a `.env` fájlban
- Várj néhány percet az API kulcs aktiválódására (új regisztráció után)

**"Connection error" / Ollama hiba:**
- Ellenőrizd, hogy az Ollama fut: `ollama list`
- Indítsd el az Ollama szolgáltatást: `ollama serve`
- Győződj meg róla, hogy a modell letöltve van: `ollama pull qwen2.5:14b-instruct`

**Import hibák:**
- Győződj meg róla, hogy a `src` könyvtárból futtatod a scriptet
- Vagy add hozzá a PYTHONPATH-hoz: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`

## Tesztek

A projekt 41 átfogó teszttel rendelkezik (100% sikeres).

### Tesztek futtatása:
```bash
cd /opt/hw3
source venv/bin/activate
pytest -v
```

### Teszt kategóriák:

- **Agent tesztek** (13 teszt):
  - Node működés: read_user_prompt, decision_node, tool_node, answer_node
  - Routing logika: should_continue, max iterations
  - Graph összeállítás

- **API tesztek** (12 teszt):
  - Endpoint működés: /api/ask, /api/health
  - Hibakezelés: hiányzó paraméterek, invalid JSON
  - CORS headers, HTTP methods

- **Geocoding tesztek** (7 teszt):
  - Sikeres geocoding (Budapest, Pécs)
  - Város nem található
  - API hibák, timeout
  - Pydantic input/output validáció

- **Weather tesztek** (9 teszt):
  - Sikeres lekérdezés (current + forecast)
  - API kulcs hibák
  - Timeout, API error kezelés
  - Pydantic validáció

### Példa teszt kimenet:
```bash
$ pytest -v
========== test session starts ==========
collected 41 items

tests/test_agent.py::test_read_user_prompt_node PASSED
tests/test_agent.py::test_decision_node_call_tool PASSED
...
========== 41 passed in 0.33s ==========
```

### Teszt lefedettség:
```bash
pip install pytest-cov
pytest --cov=src --cov-report=html
```

## Licenc

MIT
