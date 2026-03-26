"""
Tracker — logs all campaign actions to Google Sheets for tracking and rate limiting.
"""

import sys
from datetime import datetime, date

import gspread

sys.path.insert(0, "..")
from config import GOOGLE_SERVICE_ACCOUNT_JSON_PATH, GOOGLE_SHEET_ID


def _get_sheet():
    """Authenticate and return the Google Sheet."""
    try:
        gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_JSON_PATH)
        sheet = gc.open_by_key(GOOGLE_SHEET_ID)
        return sheet
    except Exception as e:
        print(f"\n[ERROR] Could not connect to Google Sheets: {e}")
        sys.exit(1)


def _get_or_create_tab(sheet, tab_name, headers):
    """Get a worksheet tab, creating it with headers if it doesn't exist."""
    try:
        worksheet = sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
        worksheet.append_row(headers)
    return worksheet


def log_campaign(campaign_name, email_type, segment, total_contacts, sent, failed, event_id="", zoom_url=""):
    """
    Log a campaign summary to the Campaign Log tab.
    """
    sheet = _get_sheet()
    headers = ["date", "campaign_name", "type", "segment", "total_contacts", "sent", "failed", "event_id", "zoom_url"]
    ws = _get_or_create_tab(sheet, "Campaign Log", headers)

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        campaign_name,
        email_type,
        segment,
        total_contacts,
        sent,
        failed,
        event_id,
        zoom_url,
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        print(f"  [LOG] Campaign logged: {campaign_name} — {email_type} ({segment})")
    except Exception as e:
        print(f"  [WARNING] Failed to log campaign: {e}")


def log_send(campaign_name, email, status, message_id="", error=""):
    """
    Log an individual email send to the Send Log tab.
    """
    sheet = _get_sheet()
    headers = ["timestamp", "campaign_name", "email", "status", "message_id", "error"]
    ws = _get_or_create_tab(sheet, "Send Log", headers)

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        campaign_name,
        email,
        status,
        message_id,
        error,
    ]

    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"  [WARNING] Failed to log send for {email}: {e}")


def log_sends_batch(campaign_name, results):
    """
    Log a batch of send results to the Send Log tab (fewer API calls).
    """
    sheet = _get_sheet()
    headers = ["timestamp", "campaign_name", "email", "status", "message_id", "error"]
    ws = _get_or_create_tab(sheet, "Send Log", headers)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for r in results:
        rows.append([
            now,
            campaign_name,
            r.get("email", ""),
            r.get("status", ""),
            r.get("message_id", ""),
            r.get("error", ""),
        ])

    if rows:
        try:
            ws.append_rows(rows, value_input_option="USER_ENTERED")
            print(f"  [LOG] {len(rows)} send records logged.")
        except Exception as e:
            print(f"  [WARNING] Failed to batch log sends: {e}")


def get_today_send_count():
    """
    Count how many emails were sent today (for Brevo rate limiting).
    """
    sheet = _get_sheet()
    try:
        ws = sheet.worksheet("Send Log")
    except gspread.exceptions.WorksheetNotFound:
        return 0

    records = ws.get_all_records()
    today = date.today().strftime("%Y-%m-%d")
    count = sum(
        1 for r in records
        if r.get("status") == "sent" and str(r.get("timestamp", "")).startswith(today)
    )
    return count


def get_campaign_history():
    """Return all campaigns from the Campaign Log tab."""
    sheet = _get_sheet()
    try:
        ws = sheet.worksheet("Campaign Log")
        return ws.get_all_records()
    except gspread.exceptions.WorksheetNotFound:
        return []


def handle_status_command():
    """Handle the 'status' CLI subcommand."""
    campaigns = get_campaign_history()

    if not campaigns:
        print("\n  No campaigns logged yet.")
        return

    print(f"\n--- CAMPAIGN HISTORY ({len(campaigns)} campaigns) ---\n")
    for c in campaigns:
        print(f"  [{c.get('date', '?')}] {c.get('campaign_name', '?')}")
        print(f"    Type: {c.get('type', '?')} | Segment: {c.get('segment', '?')}")
        print(f"    Sent: {c.get('sent', 0)} | Failed: {c.get('failed', 0)} | Total: {c.get('total_contacts', 0)}")
        if c.get("zoom_url"):
            print(f"    Zoom: {c['zoom_url']}")
        print()

    today_count = get_today_send_count()
    print(f"  Today's send count: {today_count}/300 (Brevo daily limit)\n")
