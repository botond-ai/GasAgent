"""
US Holiday tools for LLM function calling.

Uses Nager.Date API (https://date.nager.at/) - free, no API key required.
"""
import httpx
from dataclasses import dataclass
from typing import Any, Optional
from datetime import date


@dataclass
class Holiday:
    """Represents a US holiday."""
    date: str
    name: str
    local_name: str
    is_fixed: bool
    is_global: bool


class HolidayTools:
    """
    LLM tools for US holiday information.

    Uses Nager.Date API which provides free public holiday data.
    """

    BASE_URL = "https://date.nager.at/api/v3"
    COUNTRY_CODE = "US"

    # OpenAI function calling schemas
    TOOL_DEFINITIONS = [
        {
            "type": "function",
            "function": {
                "name": "is_us_holiday",
                "description": "Check if a specific date is a US public holiday",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date": {
                            "type": "string",
                            "description": "The date to check in YYYY-MM-DD format"
                        }
                    },
                    "required": ["date"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_us_holidays",
                "description": "List all US public holidays for a given year",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year": {
                            "type": "integer",
                            "description": "The year to get holidays for (e.g., 2024)"
                        }
                    },
                    "required": ["year"]
                }
            }
        }
    ]

    async def is_us_holiday(self, date_str: str) -> tuple[bool, Optional[str]]:
        """
        Check if a date is a US public holiday.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Tuple of (is_holiday, holiday_name or None)
        """
        parsed_date = date.fromisoformat(date_str)
        year = parsed_date.year

        holidays = await self._fetch_holidays(year)

        for holiday in holidays:
            if holiday["date"] == date_str:
                return True, holiday["name"]

        return False, None

    async def list_us_holidays(self, year: int) -> list[Holiday]:
        """
        List all US public holidays for a given year.

        Args:
            year: The year to get holidays for

        Returns:
            List of Holiday objects
        """
        holidays_data = await self._fetch_holidays(year)

        return [
            Holiday(
                date=h["date"],
                name=h["name"],
                local_name=h["localName"],
                is_fixed=h.get("fixed", False),
                is_global=h.get("global", True)
            )
            for h in holidays_data
        ]

    async def _fetch_holidays(self, year: int) -> list[dict]:
        """Fetch holidays from the API for a given year."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/PublicHolidays/{year}/{self.COUNTRY_CODE}"
            )
            response.raise_for_status()
            return response.json()

    async def execute(self, function_name: str, arguments: dict[str, Any]) -> str:
        """
        Execute the tool based on function name and arguments.

        This method is called by the LLM tool executor.
        """
        if function_name == "is_us_holiday":
            is_holiday, holiday_name = await self.is_us_holiday(arguments["date"])
            if is_holiday:
                return f"Yes, {arguments['date']} is a US holiday: {holiday_name}"
            return f"No, {arguments['date']} is not a US public holiday"

        if function_name == "list_us_holidays":
            holidays = await self.list_us_holidays(arguments["year"])
            lines = [f"US Public Holidays for {arguments['year']}:"]
            for h in holidays:
                lines.append(f"  - {h.date}: {h.name}")
            return "\n".join(lines)

        raise ValueError(f"Unknown function: {function_name}")
