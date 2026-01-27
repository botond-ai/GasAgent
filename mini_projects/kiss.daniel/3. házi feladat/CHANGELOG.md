# Projekt Átalakítás Összefoglaló

## 2026.01.17 - Teljes átdolgozás a részletes specifikáció alapján

### Fő Változások

#### 1. **Új architektúra: Weather Subgraph**
   - Létrehozva: `/src/agent/weather_graph.py`
   - 3 dedikált node:
     - `time_parser_node` - időpont felismerés (LLM + heurisztikák)
     - `geo_location_node` - város geocoding (LLM + Open-Meteo + IP fallback)
     - `weather_fetch_node` - OpenWeather One Call 3.0 API
   - Edges: 1 → 2 → 3
   - Teljes izolált workflow időjárás lekérdezéshez

#### 2. **Új tool: get_time**
   - Létrehozva: `/src/agent/tools/time_tool.py`
   - Aktuális szerver idő visszaadása ISO formátumban
   - Egyszerű Pydantic model (TimeOutput)

#### 3. **IP-alapú geolokáció fallback**
   - Létrehozva: `/src/agent/tools/ip_location.py`
   - ipapi.co API használata (ingyenes, 1000 req/nap)
   - Automatikus város detektálás, ha a prompt nem tartalmaz várost

#### 4. **Main Graph átírása - ToolNode használat**
   - `/src/agent/graph.py` teljes újraírás
   - LangGraph ToolNode koncepció implementálva
   - 2 tool regisztrálva @tool decorator-ral:
     - `get_time_tool` - idő lekérdezés
     - `get_weather_tool` - weather subgraph wrapper
   - Graph struktúra továbbra is: 1→2⟷3→4
   - MAX_ITERATIONS = 3 (végtelen ciklus védelem)

#### 5. **LLM Client átnevezés**
   - `/src/agent/llm.py`: `OllamaClient` → `GroqClient`
   - Dokumentáció frissítés: Groq API használatra
   - Model: `llama-3.3-70b-versatile` (tool-using agent)
   - Temperature: 0.1 (determinisztikus)
   - Max tokens: 500 (JSON válaszokhoz elegendő)

#### 6. **State modellek frissítése**
   - `/src/agent/state.py`
   - Decision.action: `Literal["call_tool", "final_answer"]`
   - Decision.tool_name: `Literal["get_weather", "get_time"]`
   - Strict typing a specifikáció szerint

#### 7. **Prompts teljes átírása magyar nyelvre**
   - `/src/agent/prompts.py`
   - DECISION_PROMPT: magyar nyelvű döntési logika
   - ANSWER_PROMPT: szigorú magyar válasz követelmények
   - Példák, szabályok, formátum specifikáció

#### 8. **OpenWeather One Call 3.0 integráció**
   - `/src/agent/weather_graph.py` weather_fetch_node
   - Endpoint routing:
     - Aktuális + 7 napos forecast: `/data/3.0/onecall`
     - Távoli dátumok: előfizetés szükséges (timemachine/day_summary)
   - Magyar hibaüzenetek minden failure esetére
   - Robusztus timeout és exception handling

#### 9. **README átírása**
   - Architektúra dokumentáció
   - Groq API követelmények
   - One Call 3.0 API aktiválási útmutató
   - Frissített példák (get_time, IP fallback)

#### 10. **Tools package frissítés**
   - `/src/agent/tools/__init__.py`
   - Új exportok: get_time, TimeOutput, get_city_from_ip

### Specifikációnak való megfelelés

✅ **Main Graph Design**
- Node 1: read_user_prompt ✓
- Node 2: decision_node (LLM + Pydantic Decision) ✓
- Node 3: tool_node (ToolNode wrapper) ✓
- Node 4: answer_node (magyar válasz generálás) ✓

✅ **Main Graph Edges**
- 1 → 2 ✓
- 2 → 3 ✓
- 3 → 2 ✓
- 2 → 4 ✓

✅ **Weather Subgraph**
- Node 1: time_parser ✓
- Node 2: geo_location (+ IP fallback) ✓
- Node 3: weather_fetch (One Call 3.0) ✓
- Edges: 1 → 2 → 3 ✓

✅ **Tools**
- get_time: ISO formátum ✓
- get_weather: subgraph wrapper ✓
- geocode_city: Open-Meteo API ✓
- IP geolocation fallback ✓

✅ **External Provider Resilience**
- Minden HTTP hívás timeout-tal (10s) ✓
- Catch network errors ✓
- Catch invalid JSON ✓
- Tools never crash ✓
- Magyar hibaüzenetek ✓

✅ **Language Requirements**
- Rendszer promptok magyarul ✓
- Hibaüzenetek magyarul ✓
- Code comments angolul ✓

✅ **LLM Configuration**
- Groq API (GROQ_API_KEY) ✓
- Low temperature (0.1) ✓
- Structured JSON output ✓
- Tool-using model (llama-3.3-70b) ✓

### Megjegyzések

1. **OpenWeather One Call 3.0 Access**
   - A specifikáció One Call 3.0-t ír elő
   - Ez előfizetést igényel (ingyenes tier aktiválással)
   - README tartalmaz figyelmeztetést és aktiválási útmutatót

2. **IP Geolocation Service**
   - Választott szolgáltatás: ipapi.co
   - Ingyenes: 1000 req/day
   - Nincs API key szükséges
   - README dokumentálja

3. **ToolNode használat**
   - A specifikáció LangGraph ToolNode-ot ír elő
   - Implementálva @tool decorator-okkal
   - Wrapper node (tool_execution_wrapper) konvertálja ToolResult-ra

4. **Magyar nyelv konzisztencia**
   - Minden user-facing string magyar
   - LLM promptok magyar nyelvűek
   - Fallback üzenetek magyar nyelvűek
   - Code/comments angolul maradtak

### Tesztelési javaslatok

```bash
# 1. Időjárás lekérdezés várossal
python src/main.py "Milyen az időjárás Budapesten?"

# 2. Időjárás előrejelzés
python src/main.py "Milyen idő lesz holnap Szegeden?"

# 3. IP alapú fallback (nincs város)
python src/main.py "Milyen az időjárás most?"

# 4. Idő lekérdezés
python src/main.py "Hány óra van?"

# 5. Nem releváns kérdés
python src/main.py "Ki volt Petőfi Sándor?"
```

### Backup fájlok

Eredeti graph.py elmentve: `/src/agent/graph.py.backup`
