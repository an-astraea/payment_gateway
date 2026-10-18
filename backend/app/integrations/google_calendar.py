"""Google Calendar events with an automatic Google Meet link, on the company account
(info@lextria.in). If Google credentials are not configured, calendar steps are skipped
and logged, so the rest of the booking flow still works."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from ..config import get_settings

log = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    s = get_settings()
    creds = Credentials(
        token=None,
        refresh_token=s.google_refresh_token,
        client_id=s.google_client_id,
        client_secret=s.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _when(start: datetime, end: datetime) -> dict:
    tz = get_settings().timezone
    return {
        "start": {"dateTime": start.isoformat(), "timeZone": tz},
        "end": {"dateTime": end.isoformat(), "timeZone": tz},
    }


def create_event(summary: str, description: str, start: datetime, end: datetime, attendees: list[str]) -> tuple[str | None, str | None]:
    """Returns (event_id, meet_link)."""
    s = get_settings()
    if not s.google_enabled:
        log.warning("Google Calendar not configured: skipped creating '%s'", summary)
        return None, None
    body = {
        "summary": summary,
        "description": description,
        **_when(start, end),
        "attendees": [{"email": a} for a in attendees],
        "conferenceData": {
            "createRequest": {"requestId": uuid.uuid4().hex, "conferenceSolutionKey": {"type": "hangoutsMeet"}}
        },
        "reminders": {"useDefault": True},
    }
    event = (
        _service()
        .events()
        .insert(calendarId=s.google_calendar_id, body=body, conferenceDataVersion=1, sendUpdates=s.google_send_updates)
        .execute()
    )
    meet = event.get("hangoutLink")
    if not meet:
        for ep in event.get("conferenceData", {}).get("entryPoints", []):
            if ep.get("entryPointType") == "video":
                meet = ep.get("uri")
    return event.get("id"), meet


def move_event(event_id: str | None, start: datetime, end: datetime) -> None:
    s = get_settings()
    if not (s.google_enabled and event_id):
        return
    _service().events().patch(
        calendarId=s.google_calendar_id, eventId=event_id, body=_when(start, end), sendUpdates=s.google_send_updates
    ).execute()


def set_attendees(event_id: str | None, attendees: list[str]) -> None:
    s = get_settings()
    if not (s.google_enabled and event_id):
        return
    _service().events().patch(
        calendarId=s.google_calendar_id,
        eventId=event_id,
        body={"attendees": [{"email": a} for a in attendees]},
        sendUpdates=s.google_send_updates,
    ).execute()


def delete_event(event_id: str | None) -> None:
    s = get_settings()
    if not (s.google_enabled and event_id):
        return
    _service().events().delete(
        calendarId=s.google_calendar_id, eventId=event_id, sendUpdates=s.google_send_updates
    ).execute()
