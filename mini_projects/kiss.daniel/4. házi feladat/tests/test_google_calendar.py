"""
Unit tests for Google Calendar tool.
Uses mock implementation to avoid actual API calls.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.agent.state import EventDetails, CalendarEventResult
from app.tools.google_calendar import (
    GoogleCalendarTool,
    MockGoogleCalendarTool,
    get_calendar_tool,
)


class TestMockGoogleCalendarTool:
    """Tests for MockGoogleCalendarTool."""
    
    @pytest.fixture
    def tool(self):
        """Create a mock calendar tool."""
        return MockGoogleCalendarTool()
    
    def test_create_event_success(self, tool):
        """Test successful event creation."""
        event = EventDetails(
            title="Test Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
            timezone="Europe/Budapest",
        )
        
        result = tool.create_event(event)
        
        assert result.success is True
        assert result.event_id is not None
        assert result.html_link is not None
        assert result.status == "confirmed"
        assert len(tool.created_events) == 1
    
    def test_create_multiple_events(self, tool):
        """Test creating multiple events generates unique IDs."""
        event = EventDetails(
            title="Test Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
        )
        
        result1 = tool.create_event(event)
        result2 = tool.create_event(event)
        
        assert result1.event_id != result2.event_id
        assert len(tool.created_events) == 2
    
    def test_find_conflicts_returns_empty(self, tool):
        """Test that mock conflict check returns empty list."""
        conflicts = tool.find_conflicts(
            start=datetime.now(),
            end=datetime.now() + timedelta(hours=1),
        )
        
        assert conflicts == []
    
    def test_stores_event_details(self, tool):
        """Test that event details are stored for verification."""
        event = EventDetails(
            title="Stored Meeting",
            start_datetime=datetime.now(),
            end_datetime=datetime.now() + timedelta(hours=1),
            attendees=["alice@test.com"],
        )
        
        tool.create_event(event, calendar_id="test-calendar")
        
        stored = tool.created_events[0]
        assert stored["event"]["title"] == "Stored Meeting"
        assert stored["calendar_id"] == "test-calendar"


class TestGoogleCalendarToolIntegration:
    """Integration tests for GoogleCalendarTool (mocked)."""
    
    @pytest.fixture
    def mock_google_service(self):
        """Create a mock Google Calendar service."""
        with patch('app.tools.google_calendar.GoogleCalendarTool._get_service') as mock:
            service = Mock()
            events = Mock()
            insert = Mock()
            
            insert.execute.return_value = {
                "id": "real_event_123",
                "htmlLink": "https://calendar.google.com/event?eid=real_event_123",
                "status": "confirmed",
            }
            
            events.insert.return_value = insert
            service.events.return_value = events
            mock.return_value = service
            
            yield mock
    
    def test_build_event_body(self):
        """Test event body construction."""
        tool = GoogleCalendarTool()
        event = EventDetails(
            title="Test Meeting",
            start_datetime=datetime(2026, 1, 20, 10, 0),
            end_datetime=datetime(2026, 1, 20, 11, 0),
            timezone="Europe/Budapest",
            location="Conference Room A",
            description="Test description",
            attendees=["alice@test.com", "bob@test.com"],
            conference_link="https://meet.google.com/test",
        )
        
        body = tool._build_event_body(event)
        
        assert body["summary"] == "Test Meeting"
        assert body["location"] == "Conference Room A"
        assert "Test description" in body["description"]
        assert "https://meet.google.com/test" in body["description"]
        assert len(body["attendees"]) == 2
        assert body["start"]["timeZone"] == "Europe/Budapest"
    
    def test_build_event_body_minimal(self):
        """Test event body with minimal fields."""
        tool = GoogleCalendarTool()
        event = EventDetails(
            title="Simple Meeting",
            start_datetime=datetime(2026, 1, 20, 10, 0),
            end_datetime=datetime(2026, 1, 20, 11, 0),
            timezone="Europe/Budapest",
        )
        
        body = tool._build_event_body(event)
        
        assert body["summary"] == "Simple Meeting"
        assert "description" not in body
        assert "attendees" not in body


class TestGetCalendarTool:
    """Tests for get_calendar_tool factory function."""
    
    def test_returns_mock_when_requested(self):
        """Test that mock tool is returned when use_mock=True."""
        tool = get_calendar_tool(use_mock=True)
        
        assert isinstance(tool, MockGoogleCalendarTool)
    
    def test_returns_real_by_default(self):
        """Test that real tool is returned by default."""
        tool = get_calendar_tool(use_mock=False)
        
        assert isinstance(tool, GoogleCalendarTool)
        assert not isinstance(tool, MockGoogleCalendarTool)
