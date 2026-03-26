"""
Event Creator — creates a Zoom meeting and a Google Calendar event with the Zoom link.
"""

import sys
from datetime import datetime, timedelta

import requests
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

sys.path.insert(0, "..")
from config import (
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH,
    GOOGLE_CALENDAR_ID,
    ZOOM_ACCOUNT_ID,
    ZOOM_CLIENT_ID,
    ZOOM_CLIENT_SECRET,
)

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_zoom_access_token():
    """Get an OAuth access token from Zoom using Server-to-Server OAuth."""
    try:
        resp = requests.post(
            "https://zoom.us/oauth/token",
            params={"grant_type": "account_credentials", "account_id": ZOOM_ACCOUNT_ID},
            auth=(ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("\n[ERROR] Zoom auth failed — check ZOOM_CLIENT_ID and ZOOM_CLIENT_SECRET in .env")
        else:
            print(f"\n[ERROR] Zoom OAuth error: {e.response.status_code} — {e.response.text}")
        return None
    except Exception as e:
        print(f"\n[ERROR] Could not get Zoom token: {e}")
        return None


def _create_zoom_meeting(title, date_str, time_str, duration_minutes, description=""):
    """
    Create a Zoom meeting and return the join URL.

    Returns:
        dict with zoom_join_url, zoom_meeting_id, zoom_start_url, or None on failure
    """
    token = _get_zoom_access_token()
    if not token:
        return None

    # Parse date/time into ISO format for Zoom
    tz_map = {
        "ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York",
        "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago",
        "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver",
        "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
    }

    time_clean = time_str.strip()
    timezone = "America/New_York"
    for tz_abbr, tz_name in tz_map.items():
        if time_clean.upper().endswith(tz_abbr):
            timezone = tz_name
            time_clean = time_clean[: -len(tz_abbr)].strip()
            break

    try:
        parsed_time = datetime.strptime(time_clean, "%I:%M %p")
    except ValueError:
        parsed_time = datetime.strptime(time_clean, "%H:%M")

    parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
    start_dt = parsed_date.replace(hour=parsed_time.hour, minute=parsed_time.minute)

    payload = {
        "topic": title,
        "type": 2,  # Scheduled meeting
        "start_time": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration": duration_minutes,
        "timezone": timezone,
        "agenda": description,
        "settings": {
            "join_before_host": True,
            "approval_type": 0,  # Automatically approve registrants
            "registration_type": 1,  # Attendees register once
            "auto_recording": "cloud",
            "registrants_email_notification": True,
        },
    }

    try:
        # Create the meeting
        resp = requests.post(
            "https://api.zoom.us/v2/users/me/meetings",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        meeting_id = data["id"]

        # Enable registration via PATCH — this gives us the registration URL
        patch_payload = {
            "settings": {
                "approval_type": 0,
                "registration_type": 1,
            }
        }
        patch_resp = requests.patch(
            f"https://api.zoom.us/v2/meetings/{meeting_id}",
            json=patch_payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        # PATCH returns 204 on success, ignore errors (registration may not be available on free)

        # Re-fetch meeting to get registration_url
        get_resp = requests.get(
            f"https://api.zoom.us/v2/meetings/{meeting_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        get_resp.raise_for_status()
        meeting_data = get_resp.json()

        registration_url = meeting_data.get("registration_url", "")
        join_url = meeting_data.get("join_url", data["join_url"])

        result = {
            "zoom_join_url": join_url,
            "zoom_registration_url": registration_url,
            "zoom_meeting_id": meeting_id,
            "zoom_start_url": data.get("start_url", ""),
        }

        print(f"\n[SUCCESS] Zoom meeting created!")
        if registration_url:
            print(f"  Registration: {registration_url}")
        print(f"  Join URL:     {join_url}")
        print(f"  Meeting ID:   {meeting_id}")

        return result

    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] Zoom API error: {e.response.status_code} — {e.response.text}")
        return None
    except Exception as e:
        print(f"\n[ERROR] Failed to create Zoom meeting: {e}")
        return None


def _get_calendar_service():
    """Authenticate and return Google Calendar API service."""
    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_SERVICE_ACCOUNT_JSON_PATH, scopes=SCOPES
        )
        service = build("calendar", "v3", credentials=creds)
        return service
    except Exception as e:
        print(f"\n[ERROR] Could not connect to Google Calendar: {e}")
        print("Check your service account JSON and that the Calendar API is enabled in Google Cloud.")
        sys.exit(1)


def _parse_time(time_str):
    """Parse a time string like '1:00 PM ET' into (datetime, timezone)."""
    tz_map = {
        "ET": "America/New_York", "EST": "America/New_York", "EDT": "America/New_York",
        "CT": "America/Chicago", "CST": "America/Chicago", "CDT": "America/Chicago",
        "MT": "America/Denver", "MST": "America/Denver", "MDT": "America/Denver",
        "PT": "America/Los_Angeles", "PST": "America/Los_Angeles", "PDT": "America/Los_Angeles",
    }

    time_clean = time_str.strip()
    timezone = "America/New_York"
    for tz_abbr, tz_name in tz_map.items():
        if time_clean.upper().endswith(tz_abbr):
            timezone = tz_name
            time_clean = time_clean[: -len(tz_abbr)].strip()
            break

    try:
        parsed_time = datetime.strptime(time_clean, "%I:%M %p")
    except ValueError:
        try:
            parsed_time = datetime.strptime(time_clean, "%H:%M")
        except ValueError:
            return None, None

    return parsed_time, timezone


def create_webinar_event(title, description, date_str, time_str, duration_minutes):
    """
    Create a Zoom meeting and a Google Calendar event with the Zoom link.

    Returns:
        dict with event_id, event_link, zoom_join_url, zoom_meeting_id, start_time, end_time
    """
    # Step 1: Create Zoom meeting
    print("\n--- Creating Zoom meeting ---")
    zoom = _create_zoom_meeting(title, date_str, time_str, duration_minutes, description)
    if not zoom:
        print("[WARNING] Zoom meeting creation failed. Creating calendar event without a meeting link.")

    zoom_join_url = zoom["zoom_join_url"] if zoom else ""
    zoom_registration_url = zoom.get("zoom_registration_url", "") if zoom else ""
    # Use registration URL as the primary link (it's the landing page for attendees)
    zoom_primary_url = zoom_registration_url or zoom_join_url

    # Step 2: Create Google Calendar event with Zoom link in description
    print("\n--- Creating Google Calendar event ---")
    service = _get_calendar_service()

    parsed_time, timezone = _parse_time(time_str)
    if not parsed_time:
        print(f"\n[ERROR] Could not parse time: '{time_str}'")
        print("Use format like '1:00 PM ET' or '13:00 ET'")
        return None

    parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
    start_dt = parsed_date.replace(hour=parsed_time.hour, minute=parsed_time.minute)
    end_dt = start_dt + timedelta(minutes=duration_minutes)

    start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Add Zoom link to event description
    cal_description = description
    if zoom_registration_url:
        cal_description += f"\n\nRegister for this webinar:\n{zoom_registration_url}"
    elif zoom_join_url:
        cal_description += f"\n\nJoin Zoom Meeting:\n{zoom_join_url}"

    event_body = {
        "summary": title,
        "description": cal_description,
        "start": {"dateTime": start_str, "timeZone": timezone},
        "end": {"dateTime": end_str, "timeZone": timezone},
    }

    if zoom_primary_url:
        event_body["location"] = zoom_primary_url

    try:
        event = (
            service.events()
            .insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body)
            .execute()
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to create calendar event: {e}")
        return None

    result = {
        "event_id": event["id"],
        "event_link": event.get("htmlLink", ""),
        "zoom_join_url": zoom_primary_url,
        "zoom_registration_url": zoom_registration_url,
        "zoom_meeting_id": zoom["zoom_meeting_id"] if zoom else "",
        "start_time": f"{date_str} {time_str}",
        "end_time": end_str,
        "title": title,
    }

    print(f"\n[SUCCESS] Calendar event created!")
    print(f"  Title:     {title}")
    print(f"  When:      {date_str} {time_str} ({duration_minutes} min)")
    print(f"  Event:     {result['event_link']}")
    print(f"  Zoom:      {zoom_join_url or 'N/A'}")

    return result


def handle_event_command(args):
    """Handle the 'event' CLI subcommand."""
    if not args.create:
        print("Usage: python main.py event --create [--brief path/to/brief.json]")
        return

    if args.brief:
        import json
        try:
            with open(args.brief) as f:
                brief = json.load(f)
            title = brief["title"]
            description = brief["description"]
            date_str = brief["date"]
            time_str = brief["time"]
            duration = brief["duration_minutes"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            print(f"\n[ERROR] Could not read brief: {e}")
            return
    else:
        print("\n--- Create Webinar Event ---\n")
        title = input("  Title: ").strip()
        description = input("  Description: ").strip()
        date_str = input("  Date (YYYY-MM-DD): ").strip()
        time_str = input("  Time (e.g. 1:00 PM ET): ").strip()
        duration = int(input("  Duration (minutes): ").strip())

    return create_webinar_event(title, description, date_str, time_str, duration)
