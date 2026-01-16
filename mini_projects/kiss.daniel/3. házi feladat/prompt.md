You are GitHub Copilot. Generate a complete, production-ready Python project that implements an AI agent according to the specification below. Output ONLY code (multiple files separated with clear file headers), no explanations.

GOAL
Build a CLI-based AI agent using:
- LangGraph
- Pydantic
- ToolNode
- Local LLM via Ollama: `ollama run qwen2.5:14b-instruct`

GRAPH DESIGN
Create a LangGraph StateGraph with these nodes:
1) `read_user_prompt`:
   - Read a single user prompt from the command line (stdin or argv, choose one and implement consistently).
   - Store it in state as `user_prompt`.

2) `decision_node`:
   - Call the LLM to interpret the current state and decide whether a tool must be called.
   - The LLM must return a structured decision object (use Pydantic) with:
     - `action`: one of ["call_tool", "final_answer"]
     - `tool_name`: optional, one of ["geocode_city", "get_weather"]
     - `tool_input`: optional dict containing validated tool params
     - `reason`: short string (kept internal, not printed to user)
   - If the LLM says to call a tool, route to node 3.
   - If the LLM says final answer, route to node 4.

3) `tool_node`:
   - Implement via LangGraph ToolNode with two tools:
     a) Geo location: city name -> coordinates (lat, lon) using:
        - `https://geocoding-api.open-meteo.com/v1/search`
     b) Weather: lat/lon -> weather via OpenWeather using API key from `.env`:
        - `OPENWEATHER_API_KEY`
   - Tools MUST be implemented as pure Python callables with Pydantic input/output models.
   - Tools return normalized outputs for agent use (not raw full JSON), plus optionally include `raw` for debugging.
   - IMPORTANT: Robust error handling:
     - Timeout on all HTTP calls (e.g., 10 seconds).
     - Catch network errors, non-200 responses, invalid JSON.
     - On any tool failure or provider unavailable, tools must return a structured error result (Pydantic) such that:
       - state records the error
       - the LLM can produce a user-facing message like:
         "Az időjárás szolgáltatás nem elérhető, ezért nem tudok válaszolni."
       - Do NOT crash.
   - After tool execution, store results in state (e.g., `tool_results` list with entries including tool_name, success, data, error_message).

4) `answer_node`:
   - Call the LLM to generate the final response using:
     - user prompt
     - accumulated tool results (success/error)
   - Print ONLY the final answer to stdout.

EDGES (must match exactly)
1 -> 2
2 -> 3
3 -> 2
2 -> 4

TOOLS REQUIREMENTS
- geocode_city tool:
  - Input: city (str), optional country (str), count (int default 1), language ("hu" default)
  - Output: best match: name, country, latitude, longitude, admin1 (optional), timezone (optional)
  - If no results: return success=False with a clear error_message.

- get_weather tool:
  - Input: latitude (float), longitude (float), units ("metric" default), lang ("hu" default)
  - Use OpenWeather current weather endpoint (or another suitable OpenWeather endpoint that works with lat/lon).
  - Output normalized fields: temperature_c, description, wind_speed, humidity, location_name (if available)
  - If API key missing: success=False with error_message indicating missing config.

PROJECT STRUCTURE
Generate these files:
- `pyproject.toml` (or requirements.txt) with all dependencies pinned reasonably.
- `.env.example` containing OPENWEATHER_API_KEY placeholder.
- `src/main.py` entrypoint for CLI.
- `src/agent/graph.py` building the LangGraph graph.
- `src/agent/state.py` containing the Pydantic State model used in LangGraph.
- `src/agent/llm.py` for Ollama client wrapper (must call local Ollama model qwen2.5:14b-instruct).
- `src/agent/tools/geocode.py` and `src/agent/tools/weather.py` implementing tools + Pydantic models.
- `src/agent/prompts.py` storing system prompts for decision and answer phases.
- `README.md` with concise run instructions.

IMPLEMENTATION DETAILS
- Use python-dotenv to load .env.
- Use `requests` for HTTP calls.
- Ensure compatibility with Python 3.11+.
- No external services besides the two specified APIs.
- Make the LLM calls deterministic as possible (set temperature low).
- The decision_node MUST be robust: if LLM output is invalid, fall back to `final_answer` with a safe message.
- The graph must not loop infinitely: add a max tool-call iterations counter in state (e.g., 3). If exceeded, go to answer_node.

LANGUAGE
- System prompts and user-facing error messages should be Hungarian.
- Code comments can be English.

OUTPUT FORMAT
- Provide code for all files. Use the following format:

# FILE: path/to/file
<file contents>

Do not include any extra commentary outside the code.
