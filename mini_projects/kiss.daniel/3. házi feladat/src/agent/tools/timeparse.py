"""Time parsing tool for date/time extraction."""
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from typing import Optional
import re


class TimeParseInput(BaseModel):
    """Input for parse_time tool."""
    text: str = Field(description="Text containing time reference")
    reference_date: Optional[str] = Field(default=None, description="Reference date (ISO format)")


class TimeParseOutput(BaseModel):
    """Output from parse_time tool."""
    success: bool
    date: Optional[str] = None  # ISO format date
    days_from_now: Optional[int] = None
    time_type: Optional[str] = None  # "current", "forecast", "seasonal"
    description: Optional[str] = None
    error_message: Optional[str] = None


def parse_time(text: str, reference_date: Optional[str] = None) -> TimeParseOutput:
    """Parse time references from text.
    
    Args:
        text: Text containing time reference (e.g., "holnap", "jövő héten", "nyáron")
        reference_date: Reference date in ISO format (default: today)
        
    Returns:
        TimeParseOutput with parsed date information
    """
    try:
        text_lower = text.lower()
        today = datetime.now()
        
        # Current/now
        if any(word in text_lower for word in ["most", "jelenleg", "ma", "current", "aktuális"]):
            return TimeParseOutput(
                success=True,
                date=today.strftime("%Y-%m-%d"),
                days_from_now=0,
                time_type="current",
                description="aktuális időjárás"
            )
        
        # Tomorrow
        if "holnap" in text_lower or "tomorrow" in text_lower:
            tomorrow = today + timedelta(days=1)
            return TimeParseOutput(
                success=True,
                date=tomorrow.strftime("%Y-%m-%d"),
                days_from_now=1,
                time_type="forecast",
                description="holnap"
            )
        
        # Day after tomorrow
        if "holnapután" in text_lower or "day after tomorrow" in text_lower:
            day_after = today + timedelta(days=2)
            return TimeParseOutput(
                success=True,
                date=day_after.strftime("%Y-%m-%d"),
                days_from_now=2,
                time_type="forecast",
                description="holnapután"
            )
        
        # Next week
        if "jövő hét" in text_lower or "next week" in text_lower:
            next_week = today + timedelta(days=7)
            return TimeParseOutput(
                success=True,
                date=next_week.strftime("%Y-%m-%d"),
                days_from_now=7,
                time_type="forecast",
                description="jövő héten"
            )
        
        # Specific number of days
        days_match = re.search(r'(\d+)\s*(nap|day)', text_lower)
        if days_match:
            num_days = int(days_match.group(1))
            if num_days <= 5:  # OpenWeather free tier supports 5-day forecast
                future_date = today + timedelta(days=num_days)
                return TimeParseOutput(
                    success=True,
                    date=future_date.strftime("%Y-%m-%d"),
                    days_from_now=num_days,
                    time_type="forecast",
                    description=f"{num_days} nap múlva"
                )
        
        # Seasons (approximate months)
        season_months = {
            "tavasz": (3, "tavasszal"),
            "spring": (3, "tavasszal"),
            "nyár": (7, "nyáron"),
            "summer": (7, "nyáron"),
            "ősz": (10, "ősszel"),
            "fall": (10, "ősszel"),
            "autumn": (10, "ősszel"),
            "tél": (1, "télen"),
            "winter": (1, "télen")
        }
        
        for season, (month, desc) in season_months.items():
            if season in text_lower:
                # Calculate approximate date
                current_year = today.year
                season_year = current_year if month > today.month else current_year + 1
                season_date = datetime(season_year, month, 15)  # Mid-month
                days_diff = (season_date - today).days
                
                return TimeParseOutput(
                    success=True,
                    date=season_date.strftime("%Y-%m-%d"),
                    days_from_now=days_diff,
                    time_type="seasonal",
                    description=desc
                )
        
        # Default to current
        return TimeParseOutput(
            success=True,
            date=today.strftime("%Y-%m-%d"),
            days_from_now=0,
            time_type="current",
            description="jelenleg (nem találtam specifikus időpontot)"
        )
        
    except Exception as e:
        return TimeParseOutput(
            success=False,
            error_message=f"Időpont feldolgozási hiba: {str(e)}"
        )
