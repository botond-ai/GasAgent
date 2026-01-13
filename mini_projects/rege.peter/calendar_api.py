from __future__ import annotations

import json
from datetime import date as date_type
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def fetch_calendar_context(date: str, year: int, country: str) -> dict[str, Any]:
    """
    Fetch public-holiday context for `date` using Nager.Date.

    Returns:
        {
          "date": "YYYY-MM-DD",
          "is_holiday": bool,
          "holiday_name": Optional[str]
        }
    """
    try:
        parsed_date = date_type.fromisoformat(date)
    except ValueError:
        # Invalid input; keep public contract stable and fail "closed".
        return _normalize_calendar_result(date=date, is_holiday=False, holiday_name=None)

    if parsed_date.year != year:
        # Caller error; do not hard-fail in the public layer.
        year = parsed_date.year

    country = country.strip().upper()
    if not country:
        return _normalize_calendar_result(date=date, is_holiday=False, holiday_name=None)

    url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ai-meeting-assistant/1.0 (homework)",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, ValueError):
        return _normalize_calendar_result(date=date, is_holiday=False, holiday_name=None)

    try:
        holidays = json.loads(payload)
    except json.JSONDecodeError:
        return _normalize_calendar_result(date=date, is_holiday=False, holiday_name=None)

    if not isinstance(holidays, list):
        return _normalize_calendar_result(date=date, is_holiday=False, holiday_name=None)

    for holiday in holidays:
        if not isinstance(holiday, dict):
            continue
        if holiday.get("date") != date:
            continue
        holiday_name = holiday.get("localName") or holiday.get("name")
        if holiday_name is not None and not isinstance(holiday_name, str):
            holiday_name = None
        return _normalize_calendar_result(date=date, is_holiday=True, holiday_name=holiday_name)

    return _normalize_calendar_result(date=date, is_holiday=False, holiday_name=None)


def _normalize_calendar_result(
    *, date: str, is_holiday: bool, holiday_name: Optional[str]
) -> dict[str, Any]:
    return {"date": date, "is_holiday": is_holiday, "holiday_name": holiday_name}
