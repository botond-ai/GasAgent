"""
Google Calendar tool for creating events.
Supports both Service Account and OAuth authentication.
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.agent.state import EventDetails, CalendarEventResult

logger = logging.getLogger(__name__)


class GoogleCalendarTool:
    """
    Tool for interacting with Google Calendar API.
    Supports Service Account and OAuth authentication.
    """
    
    SCOPES = ["https://www.googleapis.com/auth/calendar"]
    
    def __init__(self):
        self.settings = get_settings()
        self._service = None
        self._credentials = None
    
    def _get_credentials(self):
        """Get Google API credentials based on configuration."""
        if self._credentials:
            return self._credentials
        
        try:
            # Try Service Account first
            if self.settings.has_google_service_account():
                self._credentials = self._get_service_account_credentials()
            # Fall back to OAuth
            elif self.settings.has_google_oauth():
                self._credentials = self._get_oauth_credentials()
            else:
                raise ValueError(
                    "No Google Calendar credentials configured. "
                    "Set either GOOGLE_SERVICE_ACCOUNT_FILE/JSON or GOOGLE_OAUTH_CLIENT_ID/SECRET"
                )
            
            return self._credentials
            
        except ImportError as e:
            logger.error(f"Google API libraries not installed: {e}")
            raise RuntimeError(
                "Google API libraries required. Install with: "
                "pip install google-auth google-auth-oauthlib google-api-python-client"
            )
    
    def _get_service_account_credentials(self):
        """Get credentials from service account."""
        from google.oauth2 import service_account
        
        if self.settings.google_service_account_json:
            # Load from JSON string
            info = json.loads(self.settings.google_service_account_json)
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=self.SCOPES
            )
        elif self.settings.google_service_account_file:
            # Load from file
            credentials = service_account.Credentials.from_service_account_file(
                self.settings.google_service_account_file, scopes=self.SCOPES
            )
        else:
            raise ValueError("No service account credentials found")
        
        # Domain-wide delegation if configured
        if self.settings.google_impersonate_user:
            credentials = credentials.with_subject(self.settings.google_impersonate_user)
        
        return credentials
    
    def _get_oauth_credentials(self):
        """Get credentials from OAuth flow."""
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import os
        
        token_path = self.settings.google_oauth_token_path
        credentials = None
        
        # Load existing token
        if os.path.exists(token_path):
            credentials = Credentials.from_authorized_user_file(token_path, self.SCOPES)
        
        # Refresh or create new token
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                # Create client config
                client_config = {
                    "installed": {
                        "client_id": self.settings.google_oauth_client_id,
                        "client_secret": self.settings.google_oauth_client_secret,
                        "redirect_uris": [self.settings.google_oauth_redirect_uri],
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
                
                flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                credentials = flow.run_local_server(port=8080)
            
            # Save token
            with open(token_path, "w") as f:
                f.write(credentials.to_json())
        
        return credentials
    
    def _get_service(self):
        """Get or create the Google Calendar service."""
        if self._service:
            return self._service
        
        from googleapiclient.discovery import build
        
        credentials = self._get_credentials()
        self._service = build("calendar", "v3", credentials=credentials)
        return self._service
    
    def create_event(
        self,
        event: EventDetails,
        calendar_id: Optional[str] = None,
    ) -> CalendarEventResult:
        """
        Create a Google Calendar event.
        
        Args:
            event: EventDetails with event information
            calendar_id: Calendar ID (default from settings)
            
        Returns:
            CalendarEventResult with event ID and link
        """
        try:
            service = self._get_service()
            cal_id = calendar_id or self.settings.google_calendar_id
            
            # Build event body
            event_body = self._build_event_body(event)
            
            logger.info(f"Creating calendar event: {event.title}")
            logger.debug(f"Event body: {event_body}")
            
            result = service.events().insert(
                calendarId=cal_id,
                body=event_body,
                sendUpdates="all" if event.attendees else "none",
            ).execute()
            
            return CalendarEventResult(
                success=True,
                event_id=result.get("id"),
                html_link=result.get("htmlLink"),
                status=result.get("status"),
            )
            
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return CalendarEventResult(
                success=False,
                error=str(e),
            )
    
    def _build_event_body(self, event: EventDetails) -> dict:
        """Build the event body for Google Calendar API."""
        # Build description with conference link if available
        description = event.description or ""
        if event.conference_link:
            if description:
                description += f"\n\nMeeting Link: {event.conference_link}"
            else:
                description = f"Meeting Link: {event.conference_link}"
        
        # Format datetime for API
        start_dt = self._format_datetime(event.start_datetime, event.timezone)
        end_dt = self._format_datetime(event.end_datetime, event.timezone)
        
        body = {
            "summary": event.title,
            "start": start_dt,
            "end": end_dt,
        }
        
        if description:
            body["description"] = description
        
        if event.location:
            body["location"] = event.location
        elif event.conference_link:
            body["location"] = event.conference_link
        
        if event.attendees:
            body["attendees"] = [{"email": email} for email in event.attendees]
        
        return body
    
    def _format_datetime(self, dt: Optional[datetime], timezone: str) -> dict:
        """Format datetime for Google Calendar API."""
        if not dt:
            raise ValueError("datetime is required")
        
        # If datetime has no timezone, use the event timezone
        if dt.tzinfo is None:
            return {
                "dateTime": dt.isoformat(),
                "timeZone": timezone,
            }
        else:
            return {
                "dateTime": dt.isoformat(),
            }
    
    def find_conflicts(
        self,
        start: datetime,
        end: datetime,
        calendar_id: Optional[str] = None,
    ) -> list[dict]:
        """
        Find events that conflict with the given time range.
        
        Args:
            start: Start datetime
            end: End datetime
            calendar_id: Calendar ID
            
        Returns:
            List of conflicting events
        """
        try:
            service = self._get_service()
            cal_id = calendar_id or self.settings.google_calendar_id
            
            events_result = service.events().list(
                calendarId=cal_id,
                timeMin=start.isoformat() + "Z",
                timeMax=end.isoformat() + "Z",
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            
            return events_result.get("items", [])
            
        except Exception as e:
            logger.error(f"Failed to check conflicts: {e}")
            return []


class MockGoogleCalendarTool(GoogleCalendarTool):
    """Mock implementation for testing without actual Google Calendar access."""
    
    def __init__(self):
        self.created_events: list[dict] = []
        self._event_counter = 0
    
    def _get_credentials(self):
        return None
    
    def _get_service(self):
        return None
    
    def create_event(
        self,
        event: EventDetails,
        calendar_id: Optional[str] = None,
    ) -> CalendarEventResult:
        """Mock event creation that returns fake success."""
        self._event_counter += 1
        event_id = f"mock_event_{self._event_counter}"
        
        self.created_events.append({
            "id": event_id,
            "event": event.model_dump(),
            "calendar_id": calendar_id,
        })
        
        logger.info(f"[MOCK] Created event: {event.title} -> {event_id}")
        
        return CalendarEventResult(
            success=True,
            event_id=event_id,
            html_link=f"https://calendar.google.com/event?eid={event_id}",
            status="confirmed",
        )
    
    def find_conflicts(
        self,
        start: datetime,
        end: datetime,
        calendar_id: Optional[str] = None,
    ) -> list[dict]:
        """Mock conflict check that returns no conflicts."""
        return []


def get_calendar_tool(use_mock: bool = False) -> GoogleCalendarTool:
    """Get the appropriate calendar tool instance."""
    if use_mock:
        return MockGoogleCalendarTool()
    return GoogleCalendarTool()
