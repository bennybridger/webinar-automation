"""
Follow-Up Scheduler — schedules and executes reminder + post-event follow-up emails.
Uses a Google Sheets "Scheduled Tasks" tab as the task queue.
"""

import sys
from datetime import datetime, timedelta

import gspread

sys.path.insert(0, "..")
from config import GOOGLE_SERVICE_ACCOUNT_JSON_PATH, GOOGLE_SHEET_ID


def _get_sheet():
    gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_JSON_PATH)
    return gc.open_by_key(GOOGLE_SHEET_ID)


def _get_or_create_tab(sheet, tab_name, headers):
    try:
        worksheet = sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=len(headers))
        worksheet.append_row(headers)
    return worksheet


TASK_HEADERS = ["campaign_name", "task_type", "target_date", "segment", "status", "executed_at", "brief_path"]


def schedule_reminder(campaign_name, event_date_str, brief_path, days_before=3):
    """
    Schedule reminder emails for 3 days before the event.
    """
    event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
    target_date = (event_date - timedelta(days=days_before)).strftime("%Y-%m-%d")

    sheet = _get_sheet()
    ws = _get_or_create_tab(sheet, "Scheduled Tasks", TASK_HEADERS)

    for segment in ["customer", "prospect"]:
        row = [campaign_name, "reminder", target_date, segment, "pending", "", brief_path]
        ws.append_row(row, value_input_option="USER_ENTERED")

    print(f"  [SCHEDULED] Reminder emails for {target_date} (3 days before event)")


def schedule_followup(campaign_name, event_date_str, brief_path, days_after=1):
    """
    Schedule post-event follow-up emails for 1 day after the event.
    """
    event_date = datetime.strptime(event_date_str, "%Y-%m-%d")
    target_date = (event_date + timedelta(days=days_after)).strftime("%Y-%m-%d")

    sheet = _get_sheet()
    ws = _get_or_create_tab(sheet, "Scheduled Tasks", TASK_HEADERS)

    for segment in ["customer", "prospect"]:
        row = [campaign_name, "followup", target_date, segment, "pending", "", brief_path]
        ws.append_row(row, value_input_option="USER_ENTERED")

    print(f"  [SCHEDULED] Follow-up emails for {target_date} (1 day after event)")


def check_and_execute_due_tasks():
    """
    Check for tasks due today (or overdue) and execute them.
    Returns dict with executed count and details.
    """
    import json
    from modules.contact_manager import get_contacts_by_segment, validate_contacts
    from modules.content_generator import generate_email_content
    from modules.email_sender import send_batch
    from modules.tracker import log_campaign, log_sends_batch, get_today_send_count

    sheet = _get_sheet()
    try:
        ws = sheet.worksheet("Scheduled Tasks")
    except gspread.exceptions.WorksheetNotFound:
        print("\n  No scheduled tasks found.")
        return {"executed": 0}

    records = ws.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    due_tasks = [
        (i + 2, r) for i, r in enumerate(records)  # +2 for header row + 0-index
        if r.get("status") == "pending" and r.get("target_date", "") <= today
    ]

    if not due_tasks:
        print(f"\n  No tasks due today ({today}). Next scheduled tasks:")
        pending = [r for r in records if r.get("status") == "pending"]
        for t in pending[:5]:
            print(f"    {t['target_date']} — {t['task_type']} ({t['segment']}) for \"{t['campaign_name']}\"")
        if not pending:
            print("    None")
        return {"executed": 0}

    print(f"\n  Found {len(due_tasks)} task(s) due today or overdue.")
    executed = 0

    for row_num, task in due_tasks:
        campaign_name = task["campaign_name"]
        task_type = task["task_type"]
        segment = task["segment"]
        brief_path = task.get("brief_path", "")

        print(f"\n  Processing: {task_type} — {segment} — \"{campaign_name}\"")

        # Load brief
        if not brief_path:
            print(f"    [SKIP] No brief path stored for this task.")
            continue

        try:
            with open(brief_path) as f:
                brief = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"    [ERROR] Could not read brief at {brief_path}: {e}")
            continue

        # Get contacts
        contacts_raw = get_contacts_by_segment(segment) if segment != "all" else (
            get_contacts_by_segment("customer") + get_contacts_by_segment("prospect")
        )
        contacts, _ = validate_contacts(contacts_raw)

        if not contacts:
            print(f"    [SKIP] No {segment} contacts found.")
            continue

        # Generate content
        print(f"    Generating {task_type} email for {segment}...")
        content = generate_email_content(task_type, segment, brief)
        if not content:
            print(f"    [ERROR] Failed to generate content.")
            continue

        # Determine template
        if task_type == "reminder":
            template = "reminder.html"
        elif task_type == "followup":
            template = f"followup_{segment}.html" if segment in ("customer", "prospect") else "followup_customer.html"
        else:
            template = f"{task_type}_{segment}.html"

        webinar_link = brief.get("zoom_join_url", "") or brief.get("event_link", "")
        extra_vars = {"webinar_link": webinar_link, "cta_link": webinar_link}

        # Send
        send_count = get_today_send_count()
        print(f"    Sending to {len(contacts)} {segment} contacts...")
        result = send_batch(contacts, template, content, extra_vars=extra_vars, send_count_today=send_count)

        # Log
        log_campaign(campaign_name, task_type, segment, len(contacts), result["sent"], result["failed"],
                     zoom_url=webinar_link)
        log_sends_batch(campaign_name, result["results"])

        # Mark task as executed
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        ws.update_cell(row_num, 5, "executed")  # status column
        ws.update_cell(row_num, 6, now)  # executed_at column

        print(f"    [DONE] Sent: {result['sent']}, Failed: {result['failed']}")
        executed += 1

    return {"executed": executed}


def handle_followup_command(args):
    """Handle the 'followup' CLI subcommand."""
    if args.check:
        print("\n--- Checking for due follow-up tasks ---")
        result = check_and_execute_due_tasks()
        print(f"\n  Tasks executed: {result['executed']}")
    else:
        print("Usage: python main.py followup --check")
