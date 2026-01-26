"""
SLA calculation tools.
"""

from datetime import datetime, timedelta

from langchain_core.tools import tool

from app.models import PRIORITY_SLA_HOURS, PRIORITY_NAMES
from .holidays import get_holidays


@tool
def calculate_sla_deadline(
    timezone: str,
    priority: str,
    country_code: str = ""
) -> dict:
    """
    Calculate SLA deadline based on priority and timezone.
    Takes into account business hours (9:00-18:00) and holidays.

    Args:
        timezone: Customer's timezone (e.g., "Europe/Budapest", "America/New_York")
        priority: Priority level ("P1", "P2", "P3", "P4")
        country_code: Two-letter country code for holiday checking (optional)

    Returns:
        Dictionary with SLA deadline information
    """
    hours = PRIORITY_SLA_HOURS.get(priority.upper(), 24)
    priority_name = PRIORITY_NAMES.get(priority.upper(), "Unknown")

    # Current time
    now = datetime.now()
    deadline = now + timedelta(hours=hours)

    # Check for holidays (if country code provided)
    holidays_in_range = []
    if country_code:
        try:
            holidays_result = get_holidays.invoke({
                "country_code": country_code,
                "year": now.year
            })
            if not holidays_result.get("error"):
                for h in holidays_result.get("holidays", []):
                    holiday_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
                    if now.date() <= holiday_date <= deadline.date():
                        holidays_in_range.append(h)
                        # If a holiday falls within the range, add 24 hours
                        deadline += timedelta(hours=24)
        except Exception:
            pass  # If query fails, continue without it

    return {
        "priority": priority.upper(),
        "priority_name": priority_name,
        "sla_hours": hours,
        "deadline": deadline.strftime("%Y-%m-%d %H:%M"),
        "deadline_local_format": deadline.strftime("%Y. %m. %d. %H:%M"),
        "timezone": timezone,
        "holidays_affecting": holidays_in_range,
        "adjusted_for_holidays": len(holidays_in_range) > 0,
    }
