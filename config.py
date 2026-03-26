"""
Loads and validates environment variables from .env file.
Every other module imports from here.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv(override=True)

REQUIRED_VARS = {
    "BREVO_API_KEY": "Brevo API key (get it from https://app.brevo.com/settings/keys/api)",
    "GOOGLE_SERVICE_ACCOUNT_JSON_PATH": "Path to your Google service account JSON file",
    "GOOGLE_SHEET_ID": "Google Sheet ID (the long string in the sheet URL)",
    "GOOGLE_CALENDAR_ID": "Google Calendar ID (your Gmail address for personal calendar)",
    "ANTHROPIC_API_KEY": "Anthropic API key (get it from https://console.anthropic.com)",
    "SENDER_EMAIL": "Email address that outbound emails come from",
    "SENDER_NAME": "Display name for outbound emails",
    "ZOOM_ACCOUNT_ID": "Zoom Server-to-Server OAuth Account ID",
    "ZOOM_CLIENT_ID": "Zoom Server-to-Server OAuth Client ID",
    "ZOOM_CLIENT_SECRET": "Zoom Server-to-Server OAuth Client Secret",
    "HUBSPOT_ACCESS_TOKEN": "HubSpot private app access token (Settings > Integrations > Private Apps)",
}

missing = []
for var, description in REQUIRED_VARS.items():
    if not os.getenv(var):
        missing.append(f"  {var} — {description}")

if missing:
    print("\n[ERROR] Missing required environment variables in .env:\n")
    print("\n".join(missing))
    print("\nCopy .env.example to .env and fill in your values.")
    sys.exit(1)

# Export all config values
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
GOOGLE_SERVICE_ACCOUNT_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_NAME = os.getenv("SENDER_NAME")
ZOOM_ACCOUNT_ID = os.getenv("ZOOM_ACCOUNT_ID")
ZOOM_CLIENT_ID = os.getenv("ZOOM_CLIENT_ID")
ZOOM_CLIENT_SECRET = os.getenv("ZOOM_CLIENT_SECRET")
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")

# Validate service account file exists
if not os.path.isfile(GOOGLE_SERVICE_ACCOUNT_JSON_PATH):
    print(f"\n[ERROR] Service account JSON not found at: {GOOGLE_SERVICE_ACCOUNT_JSON_PATH}")
    print("Check GOOGLE_SERVICE_ACCOUNT_JSON_PATH in your .env file.")
    sys.exit(1)
