# Google Calendar API Integration - Summary

## Overview
Google Calendar API has been integrated into the Homework.02 (and Homework.03) RAG embedding CLI application, allowing users to retrieve and view their calendar events directly from the interactive CLI.

## Files Added/Modified

### New Files
- **`app/google_calendar.py`** — Core Google Calendar service module
  - `CalendarService` (ABC) — Abstract interface for calendar operations
  - `GoogleCalendarService` — Concrete implementation using OAuth2 and Google API client
  - Methods:
    - `get_upcoming_events(max_results)` — Retrieve next N upcoming events
    - `get_events_by_date(start_date, end_date)` — Retrieve events in a date range
    - `create_event(title, description, start_time, end_time)` — Create new calendar event

- **`tests/test_google_calendar.py`** — Unit tests
  - `MockCalendarService` for testing without real credentials
  - Tests for event retrieval and date filtering

### Modified Files

**`requirements.txt`** — Added Google API dependencies
```
google-api-python-client>=2.100.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
```

**`.env.example`** — Added Google Calendar configuration
```
GOOGLE_CALENDAR_CREDENTIALS_FILE=./client_credentials.json
GOOGLE_CALENDAR_TOKEN_FILE=./token.pickle
```

**`app/config.py`** — Extended `Config` dataclass
```python
google_calendar_credentials_file: str | None = None
google_calendar_token_file: str | None = None
```

**`app/cli.py`**
- Added `calendar_service` parameter to `CLI.__init__()`
- New method `_print_calendar_events()` for formatted event display
- New calendar command handlers in `run()` loop:
  - `/calendar events` — Show upcoming events
  - `/calendar today` — Show today's events
  - `/calendar range START END` — Show events in date range

**`app/main.py`**
- Imports `GoogleCalendarService`
- Instantiates calendar service if credentials are configured
- Passes calendar service to CLI

**`README.md`** — Added "Google Calendar Integration" section
- Setup instructions (Google Cloud Console, OAuth2)
- Usage examples
- Example output

## Architecture

The Google Calendar integration follows **SOLID principles**:

✅ **Single Responsibility**: `GoogleCalendarService` only handles calendar operations
✅ **Open/Closed**: New calendar backends can implement `CalendarService` ABC
✅ **Liskov Substitution**: `CalendarService` implementations are interchangeable
✅ **Interface Segregation**: Minimal focused ABC with only calendar methods
✅ **Dependency Inversion**: `CLI` depends on `CalendarService` abstraction, not concrete implementation

## Usage

### Setup

1. Create Google Cloud project and enable Calendar API:
   ```bash
   # Visit https://console.cloud.google.com/
   # Create project → Enable Google Calendar API → Create OAuth2 credential
   # Download as client_credentials.json
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   # Set OPENAI_API_KEY (existing)
   # Set GOOGLE_CALENDAR_CREDENTIALS_FILE=./client_credentials.json (new)
   ```

3. Run the application:
   ```bash
   python -m app.main
   ```

   On first run, OAuth2 flow opens browser for login and saves token to `./token.pickle`.

### Interactive Commands

```
/calendar events              # Next 5 upcoming events
/calendar today              # Events for today
/calendar range 2026-01-20 2026-02-01   # Events in date range
```

### Example Output

```
Upcoming Events (2):

[1] Team Standup
    Start: 2026-01-20T09:00:00Z
    End: 2026-01-20T09:30:00Z
    Location: Zoom
    Description: Daily sync...

[2] Project Review
    Start: 2026-01-20T14:00:00Z
    End: 2026-01-20T15:00:00Z
    Location: Conference Room A
    Description: Monthly project update...
```

## Implementation Details

### Authentication Flow

1. User configures `GOOGLE_CALENDAR_CREDENTIALS_FILE` path (client_credentials.json)
2. `GoogleCalendarService._authenticate()` checks for cached token (`token.pickle`)
3. If token exists and valid, reuses it (no new OAuth flow needed)
4. If token expired, refreshes using refresh token
5. If no token, performs OAuth2 flow (browser opens, user logs in)
6. Token saved for future sessions

### Error Handling

- Missing credentials file: Service not initialized, calendar commands show error
- API errors: Logged to console, graceful error messages shown to user
- Network errors: `HttpError` caught and handled

### Performance

- Token caching reduces OAuth2 overhead on subsequent runs
- Event queries use Google's native date/time filtering (efficient server-side)
- No batch event retrieval limits (efficient pagination)

## Testing

Mock calendar service allows testing without real credentials:

```bash
pytest tests/test_google_calendar.py -v
```

## Future Enhancements

1. **Event Creation**: Extended `/calendar create TITLE DESCRIPTION START END`
2. **Event Management**: Delete/update events from CLI
3. **Calendar Search**: Filter by organizer, attendees, keywords
4. **Multiple Calendars**: Support accessing other calendars (shared calendars)
5. **Event-Document Integration**: Index calendar event titles/descriptions as embeddings for RAG search
6. **Notifications**: Alert on event changes
7. **Timezone Support**: Handle different timezones properly

## Files Applied To

- ✅ Homework.02 (primary)
- ✅ Homework.03 (synced)

Both projects now have complete Google Calendar integration.
