"""IP geolocation fallback for weather tool."""
import requests
from typing import Optional


def get_city_from_ip() -> Optional[str]:
    """Get city name from user's IP address using ipapi.co (free tier).
    
    Returns:
        City name or None if lookup fails
    """
    try:
        # Using ipapi.co free tier (no API key needed, 1000 requests/day)
        response = requests.get("https://ipapi.co/json/", timeout=5)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        city = data.get("city")
        
        return city if city else None
        
    except Exception:
        # Silently fail - return None so caller can handle it
        return None
