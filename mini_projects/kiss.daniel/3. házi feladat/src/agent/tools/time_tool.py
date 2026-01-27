"""Get current time tool."""
from datetime import datetime
from pydantic import BaseModel


class TimeOutput(BaseModel):
    """Output from get_time tool."""
    current_time: str
    timezone: str = "UTC"


def get_time() -> TimeOutput:
    """Get the current server time in ISO format.
    
    Returns:
        TimeOutput with current time in ISO format
    """
    now = datetime.now()
    return TimeOutput(
        current_time=now.isoformat(),
        timezone="Europe/Budapest"
    )
