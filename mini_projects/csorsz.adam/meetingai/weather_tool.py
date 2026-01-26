import os
import requests
from langchain_core.tools import tool

@tool
def get_weather_json(city: str):
    """Lekéri az aktuális időjárást egy városhoz JSON formátumban."""
    # Az API kulcsot az apikulcs.env-ből fogja venni, amit már használsz
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        return {"error": "Hiányzó API kulcs!"}
    
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=hu"
    
    response = requests.get(url)
    # Ez a feladat kritikus része: a JSON válasz lekérése
    data = response.json() 
    
    # Csak a fontos részeket adjuk vissza, hogy ne fogyjon a token
    return {
        "varos": data.get("name"),
        "homerseklet": data.get("main", {}).get("temp"),
        "leiras": data.get("weather", [{}])[0].get("description"),
        "nyers_json": data 
    }