# AI Weather Agent

Intelligens időjárás-lekérdező asszisztens LangGraph és Groq API használatával. CLI, REST API és modern web interfész támogatással.

## Funkciók

- 🌦️ **Természetes nyelvi időjárás-lekérdezés** - kérdezz magyarul, ahogy szeretnél
- 📍 **Automatikus helyszín felismerés** - Regex + LLM + IP fallback (ipapi.co)
- ⏰ **Időpont felismerés** - "holnap", "tegnap", pontos időpontok
- 📊 **Aktuális időjárás** - OpenWeather API v2.5 (legacy, működő)
- 🇭🇺 **Csak magyar válaszok** - tömör, 2-3 mondatos válaszok
- 🛡️ **Robusztus hibakezelés** - rate limit, API hibák kezelése
- 🔄 **Többcsatornás elérés** - CLI, REST API, web frontend
- 🏗️ **Weather subgraph** - dedikált időjárás workflow 3 node-dal (time parsing, geocoding, weather fetch)

## Architektúra

### Main Graph (LangGraph StateGraph)
```
1. read_user_prompt → 2. decision_node ⟷ 3. tool_node → 4. answer_node
```

**Node 1: read_user_prompt** - Felhasználói kérdés beolvasása
**Node 2: decision_node** - LLM dönt: tool hívás vagy végső válasz
**Node 3: tool_node** - ToolNode wrapper két eszközzel:
  - `get_time` - aktuális szerver idő
  - `get_weather` - weather subgraph meghívása
**Node 4: answer_node** - Végső magyar válasz generálása LLM-mel

Max iteráció: 3 (végtelen ciklus elkerülése)

### Weather Subgraph
```
1. time_parser → 2. geo_location → 3. weather_fetch
```

**Node 1: time_parser** - Időpont felismerés (LLM + heurisztikák)
**Node 2: geo_location** - Város geocoding (Regex + LLM + Open-Meteo API + IP fallback)
**Node 3: weather_fetch** - OpenWeather API v2.5 hívás (legacy endpoint)

**Helyszín felismerés:**
- **Regex alapú**: Magyar ragozások kezelése (Budapesten → Budapest, Roglán → Roglán)
- **LLM fallback**: Ha regex nem talál semmit
- **IP geolocation**: Ha nincs város megadva (ipapi.co, 1000 req/day)

## Követelmények

- Python 3.10+
- Groq API kulcs (ingyenes: https://console.groq.com/)
- OpenWeather API kulcs (ingyenes: https://openweathermap.org/)

## Telepítés

### 1. Repository klónozása
```bash
git clone <repository-url>
cd hw3
```

### 2. Python függőségek telepítése

**Pip használatával:**
```bash
pip install -r requirements.txt
```

**Vagy Poetry használatával:**
```bash
poetry install
poetry shell
```

### 3. Környezeti változók beállítása

Hozz létre egy `.env` fájlt a projekt gyökérkönyvtárában:

```bash
# .env fájl tartalma
GROQ_API_KEY=your_groq_api_key_here
OPENWEATHER_API_KEY=your_openweather_api_key_here
```

**API kulcsok beszerzése:**

- **Groq API**: 
  - Regisztráció: https://console.groq.com/
  - Ingyenes tier: 100,000 token/nap
  - Modell: llama-3.3-70b-versatile

- **OpenWeather API**: 
  - Regisztráció: https://openweathermap.org/api
  - Ingyenes tier: 1000 hívás/nap
  - Használt endpoint: `/weather` (v2.5, legacy API)

## Használat

### 1. CLI mód

**Parancssorban megadott kérdés:**
```bash
python3 src/main.py "Milyen az időjárás Budapesten?"
```

**Interaktív mód:**
```bash
python3 src/main.py
# Ezután írd be a kérdést a promptnál
```

**Példa futtatások:**

```bash
# Időlekérdezés
$ python3 src/main.py "Hány óra van?"
Jelenleg 17 óra 59 perc van.

# Aktuális időjárás
$ python3 src/main.py "Milyen az időjárás Budapesten?"
Jelenleg 1,25 °C van Budapesten, erős felhőzet és 93% relatív páratartalom mellett.
Az időjárás szélsebessége 5,14 km/h.

# Időjárás időpont felismeréssel
$ python3 src/main.py "Milyen idő lesz holnap Szegeden?"
[időjárási válasz holnapra]

# Külföldi város (automatikus geocoding)
$ python3 src/main.py "milyen lesz az időjárás holnap Roglán?"
[Röglan, Svédország időjárása]

# IP alapú fallback (ha nincs város megadva)
$ python3 src/main.py "Milyen az időjárás most?"
[Aktuális helyszín IP alapján]
```

### 2. REST API mód

**API szerver indítása:**
```bash
python3 src/api.py
```

Az API a `http://localhost:5000` címen érhető el.

**Endpoint-ok:**

**POST /api/ask** - Kérdés küldése
```bash
curl -X POST http://localhost:5000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Milyen idő van Budapesten?"}'

# Válasz:
{
  "success": true,
  "answer": "Budapesten jelenleg 2 °C van, borús égbolt."
}
```

**GET /api/health** - Health check
```bash
curl http://localhost:5000/api/health

# Válasz:
{
  "status": "ok",
  "message": "AI Weather Agent API is running"
}
```

### 3. Web frontend

**Indítás:**

1. Indítsd el az API szervert (lásd fent):
```bash
python3 src/api.py
```

2. Másik terminálban indítsd el a frontend szervert:
```bash
cd front
python3 -m http.server 8080
```

3. Nyisd meg böngészőben: **http://localhost:8080**

**Használat:**
- Írd be a kérdést a chat input mezőbe
- Kattints "Küldés" gombra vagy nyomj Enter-t
- A válasz 2-5 másodperc alatt megjelenik
- Chat-szerű interfész üzenet buborékokkal

## Projekt struktúra

```
hw3/
├── pyproject.toml          # Poetry konfiguráció
├── requirements.txt        # Pip függőségek
├── pytest.ini             # Pytest konfiguráció
├── .env                   # Környezeti változók (nem verziókezelt)
├── README.md              # Ez a fájl
├── src/
│   ├── main.py            # CLI belépési pont
│   ├── api.py             # Flask REST API szerver
│   └── agent/
│       ├── __init__.py
│       ├── graph.py       # LangGraph StateGraph definíció (4 node)
│       ├── weather_graph.py  # Weather subgraph (3 node)
│       ├── state.py       # State modellek (Pydantic)
│       ├── llm.py         # GroqClient wrapper
│       ├── prompts.py     # Rendszer promptok (magyar)
│       └── tools/
│           ├── __init__.py
│           ├── time_tool.py    # Időlekérdezés (get_time)
│           ├── timeparse.py    # Időpont felismerő
│           ├── geocode.py      # Geocoding (Open-Meteo)
│           ├── weather.py      # Időjárás (OpenWeather v2.5)
│           └── ip_location.py  # IP geolocation (ipapi.co)
├── front/
│   ├── index.html         # Web interfész
│   ├── app.js             # Frontend logika (AJAX)
│   └── styles.css         # Stílusok (gradiens + üveg-effekt)
└── tests/
    ├── __init__.py
    ├── test_agent.py      # Agent node tesztek (13)
    ├── test_api.py        # API endpoint tesztek (12)
    ├── test_geocode.py    # Geocoding tesztek (7)
    └── test_weather.py    # Weather tool tesztek (9)
```

## Működés

Az agent egy LangGraph StateGraph-ot használ 4 node-dal:

### Main Graph
```
1. read_user_prompt → 2. decision_node ⟷ 3. tool_execution_wrapper → 4. answer_node
```

1. **read_user_prompt**: Felhasználói kérdés beolvasása
2. **decision_node**: Groq LLM eldönti melyik eszközt kell hívni
   - `get_time` - időlekérdezés
   - `get_weather` - időjárás (meghívja a weather subgraph-ot)
3. **tool_execution_wrapper**: Eszköz végrehajtás + ToolResult készítés
4. **answer_node**: Végső magyar válasz generálása Groq LLM-mel

**Iteráció védelem:** MAX_ITERATIONS = 3 (végtelen ciklus ellen)

### Weather Subgraph

A `get_weather` tool egy dedikált 3-node subgraph-ot hív meg:

```
time_parser → geo_location → weather_fetch
```

1. **time_parser**: 
   - LLM + heurisztikák időpont felismerésre
   - "holnap" → days_from_now=1
   - "tegnap" → days_from_now=-1
   - Default: "now"

2. **geo_location**: 
   - **Regex**: Magyar ragozások kezelése (Budapesten → Budapest, Roglán → Roglán)
   - **LLM**: Regex fallback, ha nem talál városnevet
   - **IP geolocation**: Ha nincs város, ipapi.co (1000 req/day)
   - **Geocoding**: Open-Meteo API (város → koordináták)

3. **weather_fetch**: 
   - OpenWeather API v2.5 `/weather` endpoint
   - Legacy API (ingyenes, működő)
   - Hőmérséklet, leírás, szél, páratartalom

### Példa végrehajtás

**Input:** "Milyen az időjárás Budapesten?"

1. `decision_node` → action="call_tool", tool_name="get_weather"
2. `tool_execution_wrapper` → Weather subgraph indítás:
   - `time_parser`: "Budapesten" → resolved_time="now"
   - `geo_location`: Regex → "Budapest" → geocoding → lat=47.4979, lon=19.0402
   - `weather_fetch`: OpenWeather API → temp=1.25°C, desc="erős felhőzet"
3. `answer_node` → "Jelenleg 1,25 °C van Budapesten, erős felhőzet és 93% relatív páratartalom mellett."

## Tesztelés

A projekt **41 átfogó teszttel** rendelkezik (100% sikeres).

### Tesztek futtatása

**Összes teszt:**
```bash
pytest -v
```

**Specifikus teszt fájl:**
```bash
pytest tests/test_agent.py -v
pytest tests/test_weather.py -v
```

**Lefedettség (coverage):**
```bash
pytest --cov=src --cov-report=html
# Majd nyisd meg: htmlcov/index.html
```

### Teszt kategóriák

**Agent tesztek (13 teszt) - `tests/test_agent.py`:**
- ✅ Node működés: read_user_prompt, decision_node, tool_execution_wrapper, answer_node
- ✅ Routing logika: should_continue, max iterations (3)
- ✅ Graph összeállítás és edge-ek
- ✅ Tool hívások (get_time, get_weather)
- ✅ Error handling, fallback mechanizmusok

**API tesztek (12 teszt) - `tests/test_api.py`:**
- ✅ POST /api/ask endpoint működés
- ✅ GET /api/health endpoint
- ✅ Hibakezelés: hiányzó paraméterek, invalid JSON
- ✅ CORS headers validáció
- ✅ HTTP method ellenőrzés (405 Not Allowed)

**Geocoding tesztek (7 teszt) - `tests/test_geocode.py`:**
- ✅ Sikeres geocoding (Budapest, Pécs, külföldi városok)
- ✅ Város nem található
- ✅ API hibák, timeout kezelés
- ✅ Pydantic input/output validáció

**Weather tesztek (9 teszt) - `tests/test_weather.py`:**
- ✅ Sikeres időjárás lekérdezés
- ✅ API kulcs hibák (401, 404)
- ✅ Timeout, hálózati hibák
- ✅ Pydantic WeatherResult validáció

### Példa teszt kimenet

```bash
$ pytest -v
================================ test session starts =================================
platform linux -- Python 3.10.12, pytest-8.3.4, pluggy-1.5.0
collected 41 items

tests/test_agent.py::test_read_user_prompt_node PASSED                        [  2%]
tests/test_agent.py::test_decision_node_call_tool PASSED                      [  4%]
tests/test_agent.py::test_decision_node_final_answer PASSED                   [  7%]
tests/test_agent.py::test_tool_execution_wrapper_get_time PASSED              [  9%]
tests/test_agent.py::test_tool_execution_wrapper_get_weather PASSED           [ 12%]
tests/test_agent.py::test_answer_node PASSED                                  [ 14%]
tests/test_agent.py::test_should_continue_call_tool PASSED                    [ 17%]
tests/test_agent.py::test_should_continue_final_answer PASSED                 [ 19%]
tests/test_agent.py::test_should_continue_max_iterations PASSED               [ 21%]
tests/test_agent.py::test_create_graph PASSED                                 [ 24%]
tests/test_agent.py::test_run_agent_time_query PASSED                         [ 26%]
tests/test_agent.py::test_run_agent_weather_query PASSED                      [ 29%]
tests/test_agent.py::test_run_agent_invalid_query PASSED                      [ 31%]

tests/test_api.py::test_health_endpoint PASSED                                [ 34%]
tests/test_api.py::test_ask_endpoint_success PASSED                           [ 36%]
tests/test_api.py::test_ask_endpoint_missing_question PASSED                  [ 39%]
tests/test_api.py::test_ask_endpoint_empty_question PASSED                    [ 41%]
tests/test_api.py::test_ask_endpoint_invalid_json PASSED                      [ 43%]
tests/test_api.py::test_ask_endpoint_method_not_allowed PASSED                [ 46%]
tests/test_api.py::test_cors_headers PASSED                                   [ 48%]
tests/test_api.py::test_health_endpoint_cors PASSED                           [ 51%]
tests/test_api.py::test_ask_endpoint_agent_error PASSED                       [ 53%]
tests/test_api.py::test_ask_endpoint_weather_error PASSED                     [ 56%]
tests/test_api.py::test_health_endpoint_structure PASSED                      [ 58%]
tests/test_api.py::test_ask_endpoint_response_structure PASSED                [ 60%]

tests/test_geocode.py::test_geocode_city_success PASSED                       [ 63%]
tests/test_geocode.py::test_geocode_city_not_found PASSED                     [ 65%]
tests/test_geocode.py::test_geocode_city_api_error PASSED                     [ 68%]
tests/test_geocode.py::test_geocode_city_timeout PASSED                       [ 70%]
tests/test_geocode.py::test_geocode_city_pydantic_validation PASSED           [ 73%]
tests/test_geocode.py::test_geocode_city_hungarian_accents PASSED             [ 75%]
tests/test_geocode.py::test_geocode_city_language_parameter PASSED            [ 78%]

tests/test_weather.py::test_get_weather_success PASSED                        [ 80%]
tests/test_weather.py::test_get_weather_api_key_missing PASSED                [ 82%]
tests/test_weather.py::test_get_weather_api_error_401 PASSED                  [ 85%]
tests/test_weather.py::test_get_weather_api_error_404 PASSED                  [ 87%]
tests/test_weather.py::test_get_weather_timeout PASSED                        [ 90%]
tests/test_weather.py::test_get_weather_pydantic_validation PASSED            [ 92%]
tests/test_weather.py::test_get_weather_network_error PASSED                  [ 95%]
tests/test_weather.py::test_get_weather_result_structure PASSED               [ 97%]
tests/test_weather.py::test_get_weather_temperature_format PASSED             [100%]

================================= 41 passed in 0.43s =================================
```

### Debug módok

**CLI debug:**
```bash
DEBUG=1 python3 src/main.py "Hány óra van?"
```

**API debug:**
```bash
# Flask debug mode automatikusan aktív
python3 src/api.py
# Részletes request/response logok a terminálban
```

## Hibaelhárítás

### "Az időjárás szolgáltatás nem elérhető"
- ✅ Ellenőrizd a `.env` fájlban az `OPENWEATHER_API_KEY` értékét
- ✅ Várj 5-10 percet új API kulcs aktiválódására
- ✅ Teszteld a kulcsot: `curl "https://api.openweathermap.org/data/2.5/weather?q=Budapest&appid=YOUR_API_KEY"`

### "Jelenleg túl sok kérés érkezett"
- ⚠️ Groq API rate limit: 100,000 token/nap (ingyenes tier)
- ⏰ Várj 5-10 percet, majd próbáld újra
- 📊 Ellenőrizd a használatot: https://console.groq.com/

### "Connection error" / API timeout
- 🌐 Ellenőrizd az internet kapcsolatot
- 🔥 Firewall: engedélyezd az api.openweathermap.org, api.groq.com és api.open-meteo.com címeket
- ⏱️ Próbáld újra 30 másodperc múlva

### Import hibák
```bash
# Ha "ModuleNotFoundError: No module named 'agent'" hibát kapsz:
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 src/main.py "teszt"
```

### Tesztek nem futnak
```bash
# Telepítsd a pytest-et:
pip install pytest pytest-cov

# Futtasd a projekt gyökérkönyvtárából:
cd /path/to/hw3
pytest -v
```

## Technológiai stack

- **LangGraph 0.2.x**: StateGraph, ToolNode, conditional edges
- **Groq API**: llama-3.3-70b-versatile (temp=0.1, max_tokens=500)
- **Pydantic 2.x**: Strict typing, Literal validáció
- **Flask 3.x + Flask-CORS**: REST API backend
- **OpenWeather API v2.5**: `/weather` endpoint (legacy, ingyenes)
- **Open-Meteo Geocoding**: Város → koordináták (ingyenes, korlátlan)
- **ipapi.co**: IP geolocation (1000 req/day, ingyenes)
- **Python 3.10+**: Type hints, async support

## Korlátok és ismert problémák

1. **Groq rate limit**: 100,000 token/nap (ingyenes tier)
   - Megoldás: Várj 6-12 órát a reset-re
   - Alternatíva: Upgrade Dev Tier-re

2. **OpenWeather One Call 3.0**: Nem elérhető (előfizetés szükséges)
   - Aktuális megoldás: Legacy v2.5 API (csak current weather)
   - Előrejelzés: Nem implementált

3. **IP geolocation**: ipapi.co 1000 req/day limit
   - Fallback: Ha nincs város, hiba üzenet

4. **Város felismerés**: Regex + LLM alapú
   - Ritka helynevek: Néha nem működik tökéletesen
   - Megoldás: Javítottuk regex-szel (magyar ragozások)

## Licenc

MIT
