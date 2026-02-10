"""Google Calendar service abstraction and implementation.

Provides a GoogleCalendarService interface and concrete implementation
for retrieving and managing Google Calendar events.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# Google Calendar API scopes
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class CalendarService(ABC):
    @abstractmethod
    def get_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Retrieve upcoming calendar events."""

    @abstractmethod
    def get_events_by_date(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """Retrieve events within a date range (YYYY-MM-DD format)."""

    @abstractmethod
    def create_event(
        self, title: str, description: str, start_time: str, end_time: str
    ) -> Optional[Dict[str, Any]]:
        """Create a new calendar event."""


class GoogleCalendarService(CalendarService):
    """Google Calendar service using OAuth2 credentials."""

    def __init__(self, credentials_file: str, token_file: Optional[str] = None) -> None:
        """Initialize Google Calendar service.

        Args:
            credentials_file: Path to client_credentials.json from Google Cloud Console.
            token_file: Path to store OAuth2 token (e.g., token.pickle).
        """
        self.credentials_file = credentials_file
        self.token_file = token_file or "./token.pickle"
        self.service = None
        self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Google Calendar API using OAuth2."""
        try:
            import os
            import pickle

            # Try to load existing token
            if os.path.exists(self.token_file):
                with open(self.token_file, "rb") as token_fh:
                    creds = pickle.load(token_fh)
                    if creds and creds.valid:
                        self.service = build("calendar", "v3", credentials=creds)
                        logger.info("Loaded cached Google Calendar credentials")
                        return
                    elif creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                        self.service = build("calendar", "v3", credentials=creds)
                        logger.info("Refreshed Google Calendar credentials")
                        return

            # Perform new OAuth2 flow
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)

            # Save token for future use
            with open(self.token_file, "wb") as token_fh:
                pickle.dump(creds, token_fh)

            self.service = build("calendar", "v3", credentials=creds)
            logger.info("Google Calendar service authenticated")
        except Exception as exc:
            logger.error("Google Calendar authentication failed: %s", exc)
            raise

    def get_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Retrieve upcoming calendar events."""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return []

        try:
            now = datetime.utcnow().isoformat() + "Z"
            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=now,
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            formatted_events = []
            for event in events:
                formatted_events.append(
                    {
                        "id": event.get("id"),
                        "title": event.get("summary", "Untitled"),
                        "description": event.get("description", ""),
                        "start": event["start"].get(
                            "dateTime", event["start"].get("date")
                        ),
                        "end": event["end"].get("dateTime", event["end"].get("date")),
                        "organizer": event.get("organizer", {}).get("email", "Unknown"),
                        "location": event.get("location", ""),
                    }
                )
            return formatted_events
        except HttpError as exc:
            logger.error("Error retrieving calendar events: %s", exc)
            return []

    def get_events_by_date(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        """Retrieve events within a date range (YYYY-MM-DD format)."""
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return []

        try:
            # Convert date strings to ISO format with time
            start_datetime = f"{start_date}T00:00:00Z"
            end_datetime = f"{end_date}T23:59:59Z"

            events_result = (
                self.service.events()
                .list(
                    calendarId="primary",
                    timeMin=start_datetime,
                    timeMax=end_datetime,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )

            events = events_result.get("items", [])
            formatted_events = []
            for event in events:
                formatted_events.append(
                    {
                        "id": event.get("id"),
                        "title": event.get("summary", "Untitled"),
                        "description": event.get("description", ""),
                        "start": event["start"].get(
                            "dateTime", event["start"].get("date")
                        ),
                        "end": event["end"].get("dateTime", event["end"].get("date")),
                        "organizer": event.get("organizer", {}).get("email", "Unknown"),
                        "location": event.get("location", ""),
                    }
                )
            return formatted_events
        except HttpError as exc:
            logger.error("Error retrieving calendar events: %s", exc)
            return []

    def create_event(
        self, title: str, description: str, start_time: str, end_time: str
    ) -> Optional[Dict[str, Any]]:
        """Create a new calendar event.

        Args:
            title: Event title.
            description: Event description.
            start_time: Start time in ISO format (e.g., '2026-01-20T10:00:00').
            end_time: End time in ISO format (e.g., '2026-01-20T11:00:00').

        Returns:
            Created event dict or None if failed.
        """
        if not self.service:
            logger.error("Google Calendar service not initialized")
            return None

        try:
            event = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start_time, "timeZone": "UTC"},
                "end": {"dateTime": end_time, "timeZone": "UTC"},
            }

            created_event = (
                self.service.events().insert(calendarId="primary", body=event).execute()
            )
            logger.info("Event created: %s", created_event.get("id"))
            return created_event
        except HttpError as exc:
            logger.error("Error creating calendar event: %s", exc)
            return None
