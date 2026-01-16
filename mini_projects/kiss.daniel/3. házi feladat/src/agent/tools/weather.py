"""Weather tool using OpenWeather API."""
import os
import requests
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class WeatherInput(BaseModel):
    """Input for get_weather tool."""
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    units: str = Field(default="metric", description="Units (metric/imperial)")
    lang: str = Field(default="hu", description="Language for weather description")
    days_from_now: int = Field(default=0, description="Days from now (0=current, 1-5=forecast)")


class WeatherOutput(BaseModel):
    """Output from get_weather tool."""
    success: bool
    temperature_c: Optional[float] = None
    description: Optional[str] = None
    wind_speed: Optional[float] = None
    humidity: Optional[int] = None
    location_name: Optional[str] = None
    date: Optional[str] = None
    is_forecast: bool = False
    error_message: Optional[str] = None
    raw: Optional[dict] = None


def get_weather(latitude: float, longitude: float, units: str = "metric", lang: str = "hu", days_from_now: int = 0) -> WeatherOutput:
    """Get current or forecast weather for coordinates.
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        units: Units system (metric or imperial)
        lang: Language for weather description
        days_from_now: Days from now (0=current, 1-5=forecast, >5=seasonal estimate)
        
    Returns:
        WeatherOutput with weather data or error
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    
    if not api_key or api_key == "your_api_key_here":
        return WeatherOutput(
            success=False,
            error_message="OpenWeather API kulcs hiányzik vagy érvénytelen (.env fájl)"
        )
    
    # For distant future (seasons), provide general info
    if days_from_now > 5:
        return WeatherOutput(
            success=True,
            temperature_c=None,
            description=f"Időjárás előrejelzés {days_from_now} nappal előre nem elérhető. Csak általános szezonális információk.",
            is_forecast=True,
            date=None,
            error_message="Csak 5 napos előrejelzés érhető el az ingyenes API-val"
        )
    
    # Current weather or forecast (1-5 days)
    if days_from_now == 0:
        # Current weather
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": api_key,
            "units": units,
            "lang": lang
        }
    else:
        # Forecast weather (1-5 days)
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": api_key,
            "units": units,
            "lang": lang
        }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 401:
            return WeatherOutput(
                success=False,
                error_message="Érvénytelen API kulcs"
            )
        
        if response.status_code != 200:
            return WeatherOutput(
                success=False,
                error_message=f"API hiba: {response.status_code}"
            )
        
        data = response.json()
        
        if days_from_now == 0:
            # Current weather response
            main = data.get("main", {})
            weather = data.get("weather", [{}])[0]
            wind = data.get("wind", {})
            
            return WeatherOutput(
                success=True,
                temperature_c=main.get("temp"),
                description=weather.get("description"),
                wind_speed=wind.get("speed"),
                humidity=main.get("humidity"),
                location_name=data.get("name"),
                date=datetime.now().strftime("%Y-%m-%d"),
                is_forecast=False,
                raw=data
            )
        else:
            # Forecast response - get the forecast for the specified day
            forecast_list = data.get("list", [])
            
            if not forecast_list:
                return WeatherOutput(
                    success=False,
                    error_message="Nincs előrejelzés adat"
                )
            
            # Find forecast closest to the target day (noon time)
            target_index = min(days_from_now * 8, len(forecast_list) - 1)  # 8 forecasts per day (3-hour intervals)
            forecast = forecast_list[target_index]
            
            main = forecast.get("main", {})
            weather = forecast.get("weather", [{}])[0]
            wind = forecast.get("wind", {})
            
            return WeatherOutput(
                success=True,
                temperature_c=main.get("temp"),
                description=weather.get("description"),
                wind_speed=wind.get("speed"),
                humidity=main.get("humidity"),
                location_name=data.get("city", {}).get("name"),
                date=forecast.get("dt_txt", "").split(" ")[0],
                is_forecast=True,
                raw=forecast
            )
        
    except requests.exceptions.Timeout:
        return WeatherOutput(
            success=False,
            error_message="Időtúllépés az időjárás szolgáltatásnál"
        )
    except requests.exceptions.RequestException as e:
        return WeatherOutput(
            success=False,
            error_message=f"Hálózati hiba: {str(e)}"
        )
    except (KeyError, ValueError, TypeError) as e:
        return WeatherOutput(
            success=False,
            error_message=f"Adatfeldolgozási hiba: {str(e)}"
        )
