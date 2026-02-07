"""Tests for Google Calendar service integration."""

from __future__ import annotations

import tempfile

import pytest
from app.google_calendar import CalendarService, GoogleCalendarService


class MockCalendarService(CalendarService):
    """Mock calendar service for testing."""

    def __init__(self):
        self.events = [
            {
                "id": "event1",
                "title": "Meeting 1",
                "description": "Test meeting",
                "start": "2026-01-20T10:00:00Z",
                "end": "2026-01-20T11:00:00Z",
                "organizer": {"email": "test@example.com"},
                "location": "Room A",
            },
            {
                "id": "event2",
                "title": "Meeting 2",
                "description": "Another test",
                "start": "2026-01-20T14:00:00Z",
                "end": "2026-01-20T15:00:00Z",
                "organizer": {"email": "other@example.com"},
                "location": "Zoom",
            },
        ]

    def get_upcoming_events(self, max_results: int = 10):
        return self.events[:max_results]

    def get_events_by_date(self, start_date: str, end_date: str):
        # Filter by date range
        return [e for e in self.events if start_date <= e["start"][:10] <= end_date]

    def create_event(
        self, title: str, description: str, start_time: str, end_time: str
    ):
        return {
            "id": "new_event",
            "summary": title,
            "description": description,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
        }


def test_mock_calendar_get_upcoming():
    cal = MockCalendarService()
    events = cal.get_upcoming_events(max_results=2)
    assert len(events) == 2
    assert events[0]["title"] == "Meeting 1"


def test_mock_calendar_get_by_date():
    cal = MockCalendarService()
    events = cal.get_events_by_date("2026-01-20", "2026-01-20")
    assert len(events) == 2
    assert all("2026-01-20" in e["start"] for e in events)


def test_mock_calendar_create_event():
    cal = MockCalendarService()
    new_event = cal.create_event(
        "New Meeting",
        "Test description",
        "2026-01-21T09:00:00Z",
        "2026-01-21T10:00:00Z",
    )
    assert new_event["summary"] == "New Meeting"
    assert new_event["description"] == "Test description"
