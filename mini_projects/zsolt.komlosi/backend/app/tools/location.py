"""
Location-related tools (IP geolocation).
"""

import requests
from langchain_core.tools import tool

from app.config import get_settings


@tool
def get_location_info(ip_address: str) -> dict:
    """
    Get location information for an IP address using ip-api.com.
    Returns country, city, timezone, and country code.

    Args:
        ip_address: The IP address to look up (e.g., "8.8.8.8")

    Returns:
        Dictionary with location info: country, city, timezone, country_code
    """
    settings = get_settings()

    try:
        url = f"{settings.ip_api_url}/{ip_address}?lang=hu"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "fail":
            return {
                "error": True,
                "message": f"Failed to query IP address: {data.get('message', 'Unknown error')}"
            }

        return {
            "error": False,
            "ip": ip_address,
            "country": data.get("country", "Unknown"),
            "country_code": data.get("countryCode", ""),
            "city": data.get("city", "Unknown"),
            "region": data.get("regionName", ""),
            "timezone": data.get("timezone", "UTC"),
            "isp": data.get("isp", ""),
        }
    except requests.RequestException as e:
        return {
            "error": True,
            "message": f"Network error: {str(e)}"
        }
