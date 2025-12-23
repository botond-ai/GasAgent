from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date as date_type
from typing import Any, Literal, Optional, TypedDict


Priority = Literal["low", "medium", "high"]


class CalendarContext(TypedDict, total=False):
    date: str
    is_holiday: bool
    holiday_name: Optional[str]


@dataclass(frozen=True)
class ActionItem:
    task: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    priority: Priority = "medium"


@dataclass(frozen=True)
class Meeting:
    date: str
    is_holiday: bool
    holiday_name: Optional[str]
    summary: str


@dataclass(frozen=True)
class PublicOutput:
    meeting: Meeting
    decisions: list[str]
    action_items: list[ActionItem]

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        # Keep the output JSON clean: drop null optional fields in action_items.
        cleaned_action_items: list[dict[str, Any]] = []
        for item in raw["action_items"]:
            item_clean = {k: v for k, v in item.items() if v is not None}
            cleaned_action_items.append(item_clean)
        raw["action_items"] = cleaned_action_items
        return raw


def _validate_iso_date(value: str) -> None:
    date_type.fromisoformat(value)


def validate_public_output(payload: dict[str, Any]) -> PublicOutput:
    """
    Minimal public-contract validation (std-lib only).

    Note: The homework spec mentions Pydantic; this module keeps a dependency-free
    validator so the project can run in restricted environments. If you install
    Pydantic later, you can replace/extend this with Pydantic models.
    """
    if not isinstance(payload, dict):
        raise TypeError("Output must be a dict")

    meeting = payload.get("meeting")
    if not isinstance(meeting, dict):
        raise ValueError("Missing/invalid 'meeting'")

    meeting_date = meeting.get("date")
    if not isinstance(meeting_date, str):
        raise ValueError("Missing/invalid meeting.date")
    _validate_iso_date(meeting_date)

    is_holiday = meeting.get("is_holiday")
    if not isinstance(is_holiday, bool):
        raise ValueError("Missing/invalid meeting.is_holiday")

    holiday_name = meeting.get("holiday_name")
    if holiday_name is not None and not isinstance(holiday_name, str):
        raise ValueError("Invalid meeting.holiday_name")

    summary = meeting.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("Missing/invalid meeting.summary")

    decisions = payload.get("decisions", [])
    if not isinstance(decisions, list) or any(not isinstance(d, str) for d in decisions):
        raise ValueError("Invalid 'decisions' (must be list[str])")

    action_items_raw = payload.get("action_items", [])
    if not isinstance(action_items_raw, list):
        raise ValueError("Invalid 'action_items' (must be list)")

    action_items: list[ActionItem] = []
    for item in action_items_raw:
        if not isinstance(item, dict):
            raise ValueError("Invalid action item (must be dict)")
        task = item.get("task")
        if not isinstance(task, str) or not task.strip():
            raise ValueError("Invalid action_item.task")
        owner = item.get("owner")
        if owner is not None and not isinstance(owner, str):
            raise ValueError("Invalid action_item.owner")
        due_date = item.get("due_date")
        if due_date is not None:
            if not isinstance(due_date, str):
                raise ValueError("Invalid action_item.due_date")
            _validate_iso_date(due_date)
        priority = item.get("priority", "medium")
        if priority not in ("low", "medium", "high"):
            raise ValueError("Invalid action_item.priority")
        action_items.append(ActionItem(task=task.strip(), owner=owner, due_date=due_date, priority=priority))  # type: ignore[arg-type]

    return PublicOutput(
        meeting=Meeting(
            date=meeting_date,
            is_holiday=is_holiday,
            holiday_name=holiday_name,
            summary=summary.strip(),
        ),
        decisions=[d.strip() for d in decisions if d.strip()],
        action_items=action_items,
    )
