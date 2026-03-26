# Webinar Launch Automation Engine

A CLI tool that takes a webinar brief and executes a full launch sequence: Zoom meeting creation, AI-generated segmented emails, automated sends via Brevo, and scheduled follow-ups — all from a single command.

Built to demonstrate how a Growth Marketing Engineer automates the repetitive parts of webinar execution while keeping human judgment in the loop for brand messaging.

## Architecture

```
                    ┌─────────────────┐
                    │  Webinar Brief   │
                    │    (JSON)        │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   main.py       │
                    │   Orchestrator  │
                    └────────┬────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
  ┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
  │ Event Creator │ │   Content     │ │   Contact     │
  │ (Zoom +       │ │   Generator   │ │   Manager     │
  │  Google Cal)  │ │ (Claude API)  │ │ (Google       │
  │               │ │               │ │  Sheets)      │
  └───────────────┘ └───────┬───────┘ └───────┬───────┘
                            │                  │
                   ┌────────▼────────┐         │
                   │  Human Approval │         │
                   │  (CLI review)   │         │
                   └────────┬────────┘         │
                            │                  │
                   ┌────────▼──────────────────▼┐
                   │      Email Sender          │
                   │      (Brevo API)           │
                   └────────┬───────────────────┘
                            │
               ┌────────────┼────────────┐
               │            │            │
       ┌───────▼──┐  ┌─────▼─────┐ ┌────▼──────┐
       │ Tracker  │  │ Follow-Up │ │ Campaign  │
       │ (Send    │  │ Scheduler │ │ Log       │
       │  Log)    │  │ (Sheets)  │ │ (Sheets)  │
       └──────────┘  └───────────┘ └───────────┘
```

## What It Does

1. **Creates a Zoom meeting** with a registration page and adds it to Google Calendar
2. **Generates segmented emails** via Claude AI — different tone for customers vs. prospects
3. **Shows you every email for approval** before anything sends (approve, edit subject, regenerate with feedback, or skip)
4. **Sends personalized emails** through Brevo with HTML templates and first name/company personalization
5. **Logs everything** to Google Sheets — campaign summaries, individual sends, and scheduled tasks
6. **Schedules follow-ups** — reminder emails 3 days before, post-event follow-ups 1 day after

## How the Email Segmentation Works

The system generates different emails for each audience:

| Email Type | Customer Tone | Prospect Tone |
|-----------|--------------|---------------|
| **Invite** | Exclusive, insider access ("as a valued customer") | Educational, problem-aware ("you're invited") |
| **Reminder** | Shared — friendly urgency | Shared — friendly urgency |
| **Follow-up** | Deeper engagement CTA (strategy call, beta) | Conversion CTA (demo, free trial) |

## Setup (Step by Step)

### Prerequisites

- Python 3.9+
- A Google Cloud project with Calendar API and Sheets API enabled
- A Google service account with a JSON key file
- A Brevo account (free tier — 300 emails/day)
- A Zoom account with a Server-to-Server OAuth app
- An Anthropic API key

### 1. Clone the repo

```bash
git clone https://github.com/bennybridger/webinar-automation.git
cd webinar-automation
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up Google Cloud

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Google Calendar API** and **Google Sheets API**
3. Create a **Service Account** (IAM > Service Accounts > Create)
4. Download the JSON key file and save it in the project directory
5. Copy the service account email (looks like `name@project.iam.gserviceaccount.com`)

### 4. Set up Google Sheets

1. Create a new Google Sheet
2. Create 4 tabs: **Contacts**, **Campaign Log**, **Send Log**, **Scheduled Tasks**
3. In the **Contacts** tab, add these column headers in row 1:
   `email | first_name | last_name | company | segment`
4. Add your contacts with segment as `customer` or `prospect`
5. Share the sheet with your service account email (Editor access)

### 5. Share your Google Calendar

1. Go to Google Calendar > Settings > your calendar
2. Share with specific people > Add your service account email
3. Permission: **Make changes to events**

### 6. Set up Zoom

1. Go to [marketplace.zoom.us](https://marketplace.zoom.us) > Develop > Build App
2. Choose **Server-to-Server OAuth**
3. Add scope: `meeting:write`
4. Copy Account ID, Client ID, and Client Secret
5. Activate the app

### 7. Set up Brevo

1. Sign up at [brevo.com](https://brevo.com) (free tier)
2. Go to Settings > API Keys > Generate a new key
3. Verify your sender email in Settings > Senders & IP

### 8. Configure environment

```bash
cp .env.example .env
```

Fill in all values in `.env`:

```
BREVO_API_KEY=your-key
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=./service-account.json
GOOGLE_SHEET_ID=your-sheet-id-from-url
GOOGLE_CALENDAR_ID=your-email@gmail.com
ZOOM_ACCOUNT_ID=your-zoom-account-id
ZOOM_CLIENT_ID=your-zoom-client-id
ZOOM_CLIENT_SECRET=your-zoom-client-secret
ANTHROPIC_API_KEY=sk-ant-xxxxx
SENDER_EMAIL=your-verified-brevo-email
SENDER_NAME=Your Name
```

## Usage

### Full Launch (the main command)

```bash
python main.py launch --brief sample_brief.json
```

This runs the entire pipeline: Zoom meeting → calendar event → AI email generation → human approval → send → log → schedule follow-ups.

Add `--dry-run` to test without sending:

```bash
python main.py launch --brief sample_brief.json --dry-run
```

### Individual Commands

```bash
# List all contacts
python main.py contacts --list

# List only customers
python main.py contacts --segment customer

# Create a calendar event from a brief
python main.py event --create --brief sample_brief.json

# Generate invite emails
python main.py generate --brief sample_brief.json --type invite

# Check campaign history and send counts
python main.py status

# Execute any due follow-up emails
python main.py followup --check
```

### Webinar Brief Format

Create a JSON file with your webinar details:

```json
{
  "title": "Your Webinar Title",
  "speaker": "Speaker Name, Title",
  "date": "2026-04-15",
  "time": "1:00 PM ET",
  "duration_minutes": 45,
  "description": "What the webinar covers.",
  "key_takeaways": [
    "Takeaway 1",
    "Takeaway 2",
    "Takeaway 3"
  ],
  "target_pain_point": "The problem your audience faces.",
  "cta_customers": "CTA text for existing customers",
  "cta_prospects": "CTA text for prospects"
}
```

## What Each Module Does

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point + full pipeline orchestrator with human approval loop |
| `config.py` | Loads and validates all environment variables from `.env` |
| `modules/contact_manager.py` | Reads contacts from Google Sheets, segments by customer/prospect |
| `modules/event_creator.py` | Creates Zoom meeting with registration + Google Calendar event |
| `modules/content_generator.py` | Calls Claude API to generate segmented email copy |
| `modules/email_sender.py` | Sends emails via Brevo API with Jinja2 HTML templates |
| `modules/tracker.py` | Logs campaigns and sends to Google Sheets |
| `modules/follow_up.py` | Schedules and executes reminder + post-event follow-up emails |
| `templates/*.html` | HTML email templates with personalization tokens |

## Example Output

```
============================================================
  WEBINAR LAUNCH AUTOMATION ENGINE
============================================================

  Campaign: How AI is Changing B2B Demand Gen in 2026
  Date:     2026-04-15 at 1:00 PM ET

  STEP 1: Creating event
  [SUCCESS] Zoom meeting created!
    Registration: https://zoom.us/meeting/register/...
  [SUCCESS] Calendar event created!

  STEP 2: Loading contacts
  Customers: 2 valid    Prospects: 2 valid

  STEP 3: Generating email content via Claude
  STEP 4: Review & approve emails
  STEP 5: Sending emails
  [SENT] Sarah Chen <sarah@acme.com> — ID: <abc123>
  [SENT] Mike Johnson <mike@beta.com> — ID: <def456>

  STEP 6: Scheduling follow-ups
  [SCHEDULED] Reminder emails for 2026-04-12
  [SCHEDULED] Follow-up emails for 2026-04-16

  LAUNCH SUMMARY
  Emails sent: 4    Failed: 0
============================================================
```

## Rate Limits

- **Brevo free tier**: 300 emails/day. The system tracks sends in Google Sheets and warns you before hitting the limit.
- **Claude API**: Standard rate limits apply. Email generation uses Claude Sonnet for cost efficiency (~$0.001 per campaign).

## Built With

- Python 3 + argparse (CLI)
- Anthropic Claude API (email content generation)
- Brevo REST API (transactional email)
- Google Sheets API via gspread (contact database + logging)
- Google Calendar API (event creation)
- Zoom API (meeting creation with registration)
- Jinja2 (HTML email templating)
