"""Weather subgraph - dedicated workflow for weather queries."""
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from datetime import datetime, timedelta
import re
import os
import requests
from pydantic import BaseModel


class WeatherSubState(TypedDict):
    """State for the weather subgraph."""
    user_prompt: str
    resolved_time: Optional[str]  # "now", "tomorrow", "2026-01-20", etc.
    days_from_now: Optional[int]
    time_type: Optional[str]  # "current", "forecast", "specific_date"
    city: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    weather_data: Optional[dict]
    error_message: Optional[str]


class WeatherResult(BaseModel):
    """Final output from weather subgraph."""
    success: bool
    temperature_c: Optional[float] = None
    description: Optional[str] = None
    wind_speed: Optional[float] = None
    humidity: Optional[int] = None
    location_name: Optional[str] = None
    date: Optional[str] = None
    is_forecast: bool = False
    error_message: Optional[str] = None


def time_parser_node(state: WeatherSubState) -> WeatherSubState:
    """Weather Node 1: Parse time reference from user prompt.
    
    Uses LLM to infer what time the question refers to.
    Defaults to 'now' if unclear.
    """
    from .llm import GroqClient
    
    user_prompt = state["user_prompt"]
    
    # Try to parse time using simple heuristics first
    text_lower = user_prompt.lower()
    today = datetime.now()
    
    # Current/now
    if any(word in text_lower for word in ["most", "jelenleg", "ma ", "current", "aktuális"]):
        return {
            **state,
            "resolved_time": "now",
            "days_from_now": 0,
            "time_type": "current"
        }
    
    # Tomorrow
    if "holnap" in text_lower or "tomorrow" in text_lower:
        tomorrow = today + timedelta(days=1)
        return {
            **state,
            "resolved_time": tomorrow.strftime("%Y-%m-%d"),
            "days_from_now": 1,
            "time_type": "forecast"
        }
    
    # Day after tomorrow
    if "holnapután" in text_lower:
        day_after = today + timedelta(days=2)
        return {
            **state,
            "resolved_time": day_after.strftime("%Y-%m-%d"),
            "days_from_now": 2,
            "time_type": "forecast"
        }
    
    # Yesterday
    if "tegnap" in text_lower or "yesterday" in text_lower:
        yesterday = today - timedelta(days=1)
        return {
            **state,
            "resolved_time": yesterday.strftime("%Y-%m-%d"),
            "days_from_now": -1,
            "time_type": "specific_date"
        }
    
    # Specific number of days
    days_match = re.search(r'(\d+)\s*(nap|day)', text_lower)
    if days_match:
        num_days = int(days_match.group(1))
        future_date = today + timedelta(days=num_days)
        return {
            **state,
            "resolved_time": future_date.strftime("%Y-%m-%d"),
            "days_from_now": num_days,
            "time_type": "forecast" if num_days <= 7 else "specific_date"
        }
    
    # Use LLM as fallback for complex time expressions
    try:
        llm = GroqClient()
        prompt = f"""Extract the time reference from this weather question and respond with JSON only.

Question: {user_prompt}

Respond with JSON in this exact format:
{{
  "resolved_time": "now" or "YYYY-MM-DD",
  "days_from_now": integer (negative for past, 0 for now, positive for future),
  "time_type": "current" or "forecast" or "specific_date"
}}

Examples:
- "holnap" -> {{"resolved_time": "{(today + timedelta(days=1)).strftime('%Y-%m-%d')}", "days_from_now": 1, "time_type": "forecast"}}
- "most" -> {{"resolved_time": "now", "days_from_now": 0, "time_type": "current"}}
- "jövő héten" -> {{"resolved_time": "{(today + timedelta(days=7)).strftime('%Y-%m-%d')}", "days_from_now": 7, "time_type": "forecast"}}

If unclear, default to now."""

        response = llm.invoke_json(
            "You are a time parser. Respond with JSON only.",
            prompt
        )
        
        return {
            **state,
            "resolved_time": response.get("resolved_time", "now"),
            "days_from_now": response.get("days_from_now", 0),
            "time_type": response.get("time_type", "current")
        }
        
    except Exception:
        # Default to "now" on any error
        return {
            **state,
            "resolved_time": "now",
            "days_from_now": 0,
            "time_type": "current"
        }


def geo_location_node(state: WeatherSubState) -> WeatherSubState:
    """Weather Node 2: Resolve city name to coordinates.
    
    If city cannot be inferred from prompt, use IP-based geolocation.
    """
    import re
    from .llm import GroqClient
    from .tools.geocode import geocode_city
    from .tools.ip_location import get_city_from_ip
    
    user_prompt = state["user_prompt"]
    
    # First try: Simple regex for capitalized words that might be city names
    # Look for patterns like "Budapesten", "Pécsett", "Roglán"
    city_pattern = r'\b([A-ZÁÉÍÓÖŐÚÜŰ][a-záéíóöőúüű]+(?:en|n|ett|ban|ben|on|ön|an|án)?)\b'
    matches = re.findall(city_pattern, user_prompt)
    
    # Filter out common Hungarian words that aren't cities
    common_words = {'Milyen', 'Lesz', 'Időjárás', 'Holnap', 'Ma', 'Tegnap', 'Hány', 'Óra', 'Van'}
    potential_cities = [m for m in matches if m not in common_words]
    
    city = None
    
    # Try each potential city name with geocoding
    for potential_city in potential_cities:
        # Remove Hungarian suffixes to get base city name
        base_city = re.sub(r'(en|ett|ban|ben|on|ön|an|án)$', '', potential_city)
        geocode_test = geocode_city(city=base_city, language="hu")
        if geocode_test.success:
            city = base_city
            break
    
    # If regex didn't find anything, try LLM
    if not city:
        try:
            llm = GroqClient()
            prompt = f"""Extract the city name from this weather question and respond with JSON only.

Question: {user_prompt}

Respond with JSON in this exact format:
{{
  "city": "city name" or null
}}

Examples:
- "Milyen idő lesz holnap Budapesten?" -> {{"city": "Budapest"}}
- "Holnap milyen idő lesz?" -> {{"city": null}}
- "Pécsett milyen az időjárás?" -> {{"city": "Pécs"}}
- "milyen lesz az időjárás holnap Roglán?" -> {{"city": "Roglán"}}

IMPORTANT: Extract ANY word that could be a place name, even if it's uncommon or spelled unusually.
Look for proper nouns (capitalized words) that follow location patterns (-n, -en, -ban, -ben endings).
Extract ONLY the city name, without country. If no city mentioned, return null."""

            response = llm.invoke_json(
                "You are a location extractor. Respond with JSON only.",
                prompt
            )
            
            city = response.get("city")
            
        except Exception:
            city = None
    
    # If no city found, try IP geolocation
    if not city:
        city = get_city_from_ip()
    
    # If still no city, return error
    if not city:
        return {
            **state,
            "error_message": "Nem tudom megmondani az időjárást, mert nem ismerem a helyszínt."
        }
    
    # Geocode the city
    geocode_result = geocode_city(city=city, language="hu")
    
    if not geocode_result.success:
        return {
            **state,
            "error_message": f"Nem tudom megmondani az időjárást, mert nem találom ezt a várost: {city}"
        }
    
    return {
        **state,
        "city": geocode_result.name,
        "latitude": geocode_result.latitude,
        "longitude": geocode_result.longitude
    }


def weather_fetch_node(state: WeatherSubState) -> WeatherSubState:
    """Weather Node 3: Fetch weather using the legacy OpenWeather API.
    
    Uses tools/weather.py for current weather data (legacy v2.5 API).
    """
    # Check if we have location
    if not state.get("latitude") or not state.get("longitude"):
        return {
            **state,
            "error_message": "Nem tudom megmondani az időjárást, mert nem ismerem a helyszínt."
        }
    
    # Check if we have time
    if not state.get("resolved_time"):
        return {
            **state,
            "error_message": "Nem tudom megmondani az időjárást, mert nem ismerem az időpontot."
        }
    
    latitude = state["latitude"]
    longitude = state["longitude"]
    city = state.get("city", "unknown")
    
    try:
        # Use the existing get_weather function from tools
        from .tools.weather import get_weather
        
        weather_result = get_weather(latitude=latitude, longitude=longitude)
        
        if not weather_result.success:
            return {
                **state,
                "error_message": "Az időjárás szolgáltatás nem elérhető, próbáld később."
            }
        
        # Return successful result
        weather_data = {
            "temperature_c": weather_result.temperature_c,
            "description": weather_result.description,
            "wind_speed": weather_result.wind_speed,
            "humidity": weather_result.humidity,
            "location_name": city,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "is_forecast": False
        }
        
        return {**state, "weather_data": weather_data}
    
    except Exception as e:
        return {
            **state,
            "error_message": "Az időjárás szolgáltatás nem elérhető, próbáld később."
        }



def create_weather_subgraph() -> StateGraph:
    """Create the weather subgraph workflow.
    
    Edges: 1 -> 2 -> 3
    """
    workflow = StateGraph(WeatherSubState)
    
    # Add nodes
    workflow.add_node("time_parser", time_parser_node)
    workflow.add_node("geo_location", geo_location_node)
    workflow.add_node("weather_fetch", weather_fetch_node)
    
    # Add edges
    workflow.add_edge("time_parser", "geo_location")
    workflow.add_edge("geo_location", "weather_fetch")
    workflow.add_edge("weather_fetch", END)
    
    # Set entry point
    workflow.set_entry_point("time_parser")
    
    return workflow.compile()


def get_weather_via_subgraph(user_prompt: str) -> WeatherResult:
    """Execute the weather subgraph and return results.
    
    Args:
        user_prompt: Original user question
        
    Returns:
        WeatherResult with weather data or error
    """
    subgraph = create_weather_subgraph()
    
    initial_state = {
        "user_prompt": user_prompt,
        "resolved_time": None,
        "days_from_now": None,
        "time_type": None,
        "city": None,
        "latitude": None,
        "longitude": None,
        "weather_data": None,
        "error_message": None
    }
    
    final_state = subgraph.invoke(initial_state)
    
    # Check for errors
    if final_state.get("error_message"):
        return WeatherResult(
            success=False,
            error_message=final_state["error_message"]
        )
    
    # Check if we have weather data
    weather_data = final_state.get("weather_data")
    if not weather_data:
        return WeatherResult(
            success=False,
            error_message="Nem tudom megmondani az időjárást, mert nem ismerem az időpontot vagy a helyszínt."
        )
    
    return WeatherResult(
        success=True,
        **weather_data
    )
