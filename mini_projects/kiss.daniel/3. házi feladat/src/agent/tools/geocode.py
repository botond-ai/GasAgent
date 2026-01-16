"""Geocoding tool using Open-Meteo API."""
import requests
from pydantic import BaseModel, Field
from typing import Optional


class GeocodeInput(BaseModel):
    """Input for geocode_city tool."""
    city: str = Field(description="City name to geocode")
    country: Optional[str] = Field(default=None, description="Country code (e.g., 'HU')")
    count: int = Field(default=1, description="Number of results")
    language: str = Field(default="en", description="Language for results")


class GeocodeOutput(BaseModel):
    """Output from geocode_city tool."""
    success: bool
    name: Optional[str] = None
    country: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    admin1: Optional[str] = None
    timezone: Optional[str] = None
    error_message: Optional[str] = None
    raw: Optional[dict] = None


def geocode_city(city: str, country: Optional[str] = None, count: int = 1, language: str = "en") -> GeocodeOutput:
    """Geocode a city name to coordinates.
    
    Args:
        city: City name to search for
        country: Optional country code to filter results
        count: Number of results to return
        language: Language for results
        
    Returns:
        GeocodeOutput with coordinates or error
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    
    # Remove Hungarian accents for better API compatibility
    import unicodedata
    city_normalized = unicodedata.normalize('NFD', city)
    city_ascii = ''.join(c for c in city_normalized if unicodedata.category(c) != 'Mn')
    
    params = {
        "name": city_ascii,
        "count": count,
        "language": language,
        "format": "json"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            return GeocodeOutput(
                success=False,
                error_message=f"API hiba: {response.status_code}"
            )
        
        data = response.json()
        
        if "results" not in data or not data["results"]:
            return GeocodeOutput(
                success=False,
                error_message=f"Nem található város: {city}"
            )
        
        # Get the best match (first result)
        result = data["results"][0]
        
        # If country filter is specified, try to match
        if country:
            for item in data["results"]:
                if item.get("country_code", "").upper() == country.upper():
                    result = item
                    break
        
        return GeocodeOutput(
            success=True,
            name=result.get("name"),
            country=result.get("country"),
            latitude=result.get("latitude"),
            longitude=result.get("longitude"),
            admin1=result.get("admin1"),
            timezone=result.get("timezone"),
            raw=result
        )
        
    except requests.exceptions.Timeout:
        return GeocodeOutput(
            success=False,
            error_message="Időtúllépés a geocoding szolgáltatásnál"
        )
    except requests.exceptions.RequestException as e:
        return GeocodeOutput(
            success=False,
            error_message=f"Hálózati hiba: {str(e)}"
        )
    except (KeyError, ValueError, TypeError) as e:
        return GeocodeOutput(
            success=False,
            error_message=f"Adatfeldolgozási hiba: {str(e)}"
        )
