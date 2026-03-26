"""
Contact Manager — reads and segments contacts from Google Sheets.
"""

import sys
import gspread

# Import config at module level so auth is available
sys.path.insert(0, "..")
from config import GOOGLE_SERVICE_ACCOUNT_JSON_PATH, GOOGLE_SHEET_ID


def _get_sheet():
    """Authenticate and return the Google Sheet."""
    try:
        gc = gspread.service_account(filename=GOOGLE_SERVICE_ACCOUNT_JSON_PATH)
        sheet = gc.open_by_key(GOOGLE_SHEET_ID)
        return sheet
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"\n[ERROR] Google Sheet not found with ID: {GOOGLE_SHEET_ID}")
        print("Check GOOGLE_SHEET_ID in .env and make sure the sheet is shared with your service account.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Could not connect to Google Sheets: {e}")
        print("Check your service account JSON and that the Sheets API is enabled in Google Cloud.")
        sys.exit(1)


def get_all_contacts():
    """Fetch all contacts from the Contacts tab. Returns list of dicts."""
    sheet = _get_sheet()
    try:
        worksheet = sheet.worksheet("Contacts")
    except gspread.exceptions.WorksheetNotFound:
        print('\n[ERROR] No "Contacts" tab found in your Google Sheet.')
        print('Create a tab named "Contacts" with columns: email, first_name, last_name, company, segment')
        sys.exit(1)

    records = worksheet.get_all_records()
    if not records:
        print("[WARNING] Contacts tab is empty. Add some contacts and try again.")
        return []

    return records


def get_contacts_by_segment(segment):
    """Fetch contacts filtered by segment (customer or prospect)."""
    contacts = get_all_contacts()
    segment = segment.lower().strip()
    filtered = [c for c in contacts if c.get("segment", "").lower().strip() == segment]

    if not filtered:
        print(f"[WARNING] No contacts found with segment '{segment}'.")

    return filtered


def validate_contacts(contacts):
    """
    Validate contacts have required fields.
    Returns (valid, invalid) tuple of lists.
    """
    valid = []
    invalid = []

    for contact in contacts:
        email = contact.get("email", "").strip()
        first_name = contact.get("first_name", "").strip()

        if email and first_name:
            valid.append(contact)
        else:
            reason = []
            if not email:
                reason.append("missing email")
            if not first_name:
                reason.append("missing first_name")
            contact["_validation_error"] = ", ".join(reason)
            invalid.append(contact)

    return valid, invalid


def handle_contacts_command(args):
    """Handle the 'contacts' CLI subcommand."""
    if args.segment:
        contacts = get_contacts_by_segment(args.segment)
        label = f"{args.segment} contacts"
    elif args.list:
        contacts = get_all_contacts()
        label = "all contacts"
    else:
        print("Usage: python main.py contacts --list OR --segment customer|prospect")
        return

    if not contacts:
        return

    valid, invalid = validate_contacts(contacts)

    print(f"\n--- {label.upper()} ({len(valid)} valid, {len(invalid)} invalid) ---\n")
    for c in valid:
        segment_tag = f"[{c.get('segment', '?')}]"
        print(f"  {segment_tag:12s} {c['first_name']} {c.get('last_name', '')} <{c['email']}> — {c.get('company', 'N/A')}")

    if invalid:
        print(f"\n--- INVALID CONTACTS ({len(invalid)}) ---\n")
        for c in invalid:
            print(f"  {c} — Error: {c['_validation_error']}")

    print()
