You are a senior Python engineer. Create a **GitHub Copilot prompt** that instructs Copilot to generate a complete, production-ready Python project according to the following specification. The resulting Copilot prompt should request **only code output** (multiple files) with clear file headers, and **no commentary**.

---

# Project Goal

Build a CLI-based AI agent using:

* **LangGraph**
* **Pydantic**
* **ToolNode**
* LLM via **Groq API** (cloud-hosted, OpenAI-compatible) using `GROQ_API_KEY` from `.env`

The agent reads a user prompt from the command line, decides whether to call tools, calls tools as needed, and generates a final answer.

---

# Main Graph Design (LangGraph StateGraph)

Create a `StateGraph` with the following nodes:

## Node 1: `read_user_prompt`

* Read a **single user prompt** from the command line (choose **either** stdin **or** argv and implement consistently).
* Store it in state as `user_prompt`.

## Node 2: `decision_node`

* Call the LLM to interpret the current state and decide whether a tool must be called.
* The LLM must return a **structured decision object** validated by **Pydantic**, with fields:

  * `action`: one of `["call_tool", "final_answer"]`
  * `tool_name`: optional, one of `["get_weather", "get_time"]`
  * `tool_input`: optional dict containing validated tool parameters
  * `reason`: short string, internal only (must not be printed)
* If `action == "call_tool"`, route to Node 3.
* If `action == "final_answer"`, route to Node 4.
* Robustness requirement: if the LLM output cannot be parsed/validated, fall back to `final_answer` with a safe message.

## Node 3: `tool_node`

* Implement using **LangGraph ToolNode**.
* Provide two tools:

  1. **Get Time tool**: return the current server time.
  2. **Weather tool**: this is backed by a dedicated **Weather Graph** (see below).
* After tool execution, store results in state in a list, e.g. `tool_results`, with entries including:

  * `tool_name`
  * `success` (bool)
  * `data` (normalized)
  * `error_message` (optional)

## Node 4: `answer_node`

* Call the LLM to generate the final response using:

  * `user_prompt`
  * accumulated `tool_results` (including any errors)
* Print **ONLY** the final answer to stdout.

---

# Main Graph Edges (must match exactly)

* `1 -> 2`
* `2 -> 3`
* `3 -> 2`
* `2 -> 4`

Add a maximum tool-call iteration counter in state (e.g., `max_iterations = 3`). If exceeded, route to `answer_node` to avoid infinite loops.

---

# Weather Graph Design (Subgraph)

Implement a dedicated Weather workflow used by the main tool system.

## Weather Node 1: `time_parser`

* Use the LLM to infer what time the question refers to: today, tomorrow, yesterday, etc.
* If it cannot be inferred, default to **"now"**.
* Store the resolved time expression in the weather sub-state.

## Weather Node 2: `geo_location`

* Resolve **city name -> coordinates (lat/lon)** using:

  * `https://geocoding-api.open-meteo.com/v1/search`
* If the city cannot be inferred from the user prompt, use **IP-based geolocation** to infer a city, then geocode it.

  * Note: implement IP geolocation using a free service (choose one and document it in code/README), then map it to a city string.

## Weather Node 3: `weather_fetch`

* Fetch weather via **OpenWeather One Call API 3.0** using `OPENWEATHER_API_KEY` from `.env`.

* The weather workflow must support **past and future** requests by selecting the correct endpoint:

  **A) Current + short-range forecast**

  * Endpoint: `https://api.openweathermap.org/data/3.0/onecall`
  * Use when the question targets **now / today / next hours / next days** within the short forecast window.
  * The agent should select the appropriate item from `current`, `hourly`, or `daily` based on the resolved time.

  **B) Any specific timestamp (historical + up to a few days ah()t: `https://api.openweathermap.org/data/3.0/onecall/timemachine?dt=<unix>`

  * Use when the question targets a **specific past moment** (or a specific datetime clo()want time-specific conditions.
  * `dt` must be a Unix timestamp in UTC.

  **C) Daily aggregation (historical + long-range forecast)**

  * Endpoint: `https()ap.org/data/3.0/onecall/day_summary?date=YYYY-MM-DD`
  * Use when the question targets a **specific date beyond the short forecast window** and daily-level aggregation/forecast is acceptable.

* Routing logic based on parsed time:

  * If time resolves to **now / near future** and is covered by short forecast, call **(A)**.
  * If time resolves to a **specific datetime** and you need time-specific conditions, call **(B)**.
  * If time resolves to a **specific date** beyond the short forecast window, call **(C)**.

* Only call OpenWeather if **both** time and location are available.

* If either is missing, return a Hungarian error message:

  * "Nem tudom megmondani az időjárást, mert nem ismerem az időpontot vagy a helyszínt."

### Weather Graph Edges

* `1 -> 2`
* `2 -> 3`

---

# Tool Requirements

## Tool: `geocode_city`

* Input (Pydantic model):

  * `city: str`
  * `country: Optional[str] = None`
  * `count: int = 1`
  * `language: str = "hu"`
* Output (Pydantic model):

  * `success: bool`
  * `name, country, latitude, longitude`
  * `admin1: Optional[str]`
  * `timezone: Optional[str]`
  * `error_message: Optional[str]`
* If no results: `success=False` with a clear `error_message`.

## Tool: `get_weather`

* Input (Pydantic model):

  * `latitude: float`
  * `longitude: float`
  * `units: str = "metric"`
  * `lang: str = "hu"`
* Output normalized fields (Pydantic model):

  * `success: bool`
  * `temperature_c: float`
  * `description: str`
  * `wind_speed: float`
  * `humidity: int`
  * `location_name: Optional[str]`
  * `error_message: Optional[str]`
* If the API key is missing: return `success=False` with a missing-config error message.

## Tool: `get_time`

* Output current server time in ISO format.

---

# External Provider Resilience (mandatory)

For all HTTP calls:

* Use a timeout (e.g., 10 seconds).
* Catch network errors, non-200 responses, and invalid JSON.
* Tools must **never crash** the program.
* On provider failure/unavailability, ensure the agent can respond with a user-facing message, e.g.:

  * "The weather service is unavailable, so I cannot answer."

---

# Project Structure

Generate the following files:

* `pyproject.toml` (or `requirements.txt`) with dependencies pinned reasonably
* `.env.example` containing `OPENWEATHER_API_KEY=...`
* `src/main.py` (CLI entrypoint)
* `src/agent/graph.py` (main LangGraph graph)
* `src/agent/state.py` (Pydantic State model)
* `src/agent/llm.py` (Groq API client wrapper using `GROQ_API_KEY`)
* `src/agent/tools/geocode.py` and `src/agent/tools/weather.py` (tools + models)
* `src/agent/tools/time_tool.py` (get_time tool)
* `src/agent/prompts.py` (system prompts for decision and answer phases)
* `README.md` (concise run instructions)

---

# Implementation Details

* Use `python-dotenv` to load `.env`.
* Use `requests` (or the official Groq Python SDK if preferred) for HTTP calls to the **Groq API**.
* Read the API key from `GROQ_API_KEY`.
* Target a Groq-hosted model suitable for tool-using agents (e.g. Llama 3.x Instruct).
* Make LLM calls as deterministic as possible (low temperature).
* Python 3.11+ compatible.
* No external services besides:

  * Open-Meteo Geocoding API
  * OpenWeather API
  * One free IP geolocation API (for city fallback)

# Language

* **All system prompts and user-facing error messages should be in Hungarian.**
* Code comments can be English.

---

# Output Format

The Copilot prompt must instruct Copilot to output code for all files using:

```
# FILE: path/to/file
<file contents>
```

Do not include any extra commentary outside the code.

---

## Review Notes (my assessment)

* The architecture is sound: a decision loop (2↔3) with a bounded iteration counter prevents infinite cycles.
* You clarified the intent correctly: **the Copilot spec is in English**, but **the generated program’s system prompts and user-facing messages are in Hungarian**.
* Weather-by-time is now implementable: instead of “current weather only”, the weather tool/subgraph must support **past and future** by selecting the appropriate OpenWeather One Call 3.0 endpoint:

  * **Current + short-range forecast** (minute/hourly/daily): `https://api.openweathermap.org/data/3.0/onecall` (daily forecast up to ~8 days). ()
  * **Any timestamp** (historical archive and up to ~4 days ahead): `https://api.openweathermap.org/data/3.0/onecall/timemachine?dt=<unix>` (Unix UTC timestamp). ()
  * **Daily aggregation** (historical + long-range forecast up to ~1.5 years): `https://api.openweathermap.org/data/3.0/onecall/day_summary?date=YYYY-MM-DD`. ()
  * The agent should route based on the resolved date:

    * If the user asks for **today/next days** and needs a forecast: use `/onecall`.
    * If the user asks for a **specific timestamp** or **past day** and you want time-specific conditions: use `/onecall/timemachine`.
    * If the user asks for a **date far in the future** beyond the short forecast window: use `/onecall/day_summary` when applicable.
* Practical note: One Call 3.0 access may require enabling the One Call plan; ensure README notes this and explains expected errors (401/429) gracefully.
