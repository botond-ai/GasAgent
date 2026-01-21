"""
Holiday-related tools.
"""

from datetime import datetime
from typing import Optional

import requests
from langchain_core.tools import tool

from app.config import get_settings


@tool
def get_holidays(country_code: str, year: Optional[int] = None) -> dict:
    """
    Get public holidays for a country using Nager.Date API.

    Args:
        country_code: Two-letter country code (e.g., "HU", "DE", "US")
        year: Year to get holidays for (defaults to current year)

    Returns:
        Dictionary with list of holidays for the country
    """
    settings = get_settings()

    if year is None:
        year = datetime.now().year

    try:
        url = f"{settings.holidays_api_url}/{year}/{country_code}"
        response = requests.get(url, timeout=10)

        if response.status_code == 404:
            return {
                "error": False,
                "country_code": country_code,
                "year": year,
                "holidays": [],
                "message": "No data available for this country"
            }

        response.raise_for_status()
        data = response.json()

        holidays = []
        for h in data:
            holidays.append({
                "date": h.get("date"),
                "name": h.get("name"),
                "local_name": h.get("localName", h.get("name")),
            })

        return {
            "error": False,
            "country_code": country_code,
            "year": year,
            "holidays": holidays,
        }
    except requests.RequestException as e:
        return {
            "error": True,
            "message": f"Network error: {str(e)}"
        }
