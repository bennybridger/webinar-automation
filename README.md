# Webinar Launch Automation Engine

A full-stack automation system that takes a webinar idea — in plain English or JSON — and executes the entire launch: Zoom meeting, Google Calendar event, HubSpot landing page with registration form, AI-generated segmented emails, human review, automated sends via Brevo, confirmation emails with calendar invites, and scheduled follow-ups.

Two interfaces: a **CLI** for power users and a **conversational web agent** for marketers who just want to describe their webinar and hit go.

## Live Demo Links

- **Landing Page** (try it — register and get a real confirmation email): [bennybridger.github.io/webinar-automation](https://bennybridger.github.io/webinar-automation/landing-how-ai-is-changing-b2b-demand-gen-in-2026.html)
- **Webhook API** (deployed on Railway): [webinar-webhook-production.up.railway.app](https://webinar-webhook-production.up.railway.app)
- **Web Agent** (local): `http://localhost:5001`
- **GitHub Repo**: [github.com/bennybridger/webinar-automation](https://github.com/bennybridger/webinar-automation)

## Architecture

```
                         ┌──────────────────────┐
                         │   Input              │
                         │   (Plain English or  │
                         │    JSON brief)       │
                         └──────────┬───────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │                               │
            ┌───────▼───────┐               ┌───────▼───────┐
            │   app.py      │               │   main.py     │
            │   Web Agent   │               │   CLI         │
            │   (Flask)     │               │   (argparse)  │
            └───────┬───────┘               └───────┬───────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    │
         ┌──────────┬───────────────┼───────────────┬──────────┐
         │          │               │               │          │
  ┌──────▼──────┐ ┌─▼───────────┐ ┌▼────────────┐ ┌▼────────┐ │
  │ Event       │ │ Landing     │ │ Content     │ │ Contact │ │
  │ Creator     │ │ Page        │ │ Generator   │ │ Manager │ │
  │ (Zoom +     │ │ (HubSpot   │ │ (Claude AI) │ │ (Google │ │
  │  Google Cal)│ │  Forms +   │ │             │ │  Sheets)│ │
  │             │ │  HTML gen) │ │             │ │         │ │
  └─────────────┘ └────────────┘ └──────┬──────┘ └────┬────┘ │
                                        │              │      │
                                ┌───────▼──────┐       │      │
                                │ Human Review │       │      │
                                │ (Preview     │       │      │
                                │  links +     │       │      │
                                │  approve)    │       │      │
                                └───────┬──────┘       │      │
                                        │              │      │
                                ┌───────▼──────────────▼┐     │
                                │    Email Sender       │     │
                                │    (Brevo API)        │     │
                                └───────┬───────────────┘     │
                                        │                     │
                  ┌─────────────────────┼─────────────────┐   │
                  │                     │                 │   │
          ┌───────▼──────┐     ┌────────▼──────┐  ┌──────▼───▼──┐
          │ Confirmation │     │  Follow-Up    │  │  Tracker    │
          │ Email +      │     │  Scheduler    │  │  (Campaign  │
          │ Calendar     │     │  (Sheets)     │  │   + Send    │
          │ Invite       │     │               │  │   Logs)     │
          └──────────────┘     └───────────────┘  └─────────────┘
```

## What It Does

1. **Creates a Zoom meeting** and adds it to Google Calendar
2. **Builds a landing page** with a HubSpot registration form — hosted on GitHub Pages
3. **Sends confirmation emails** with calendar invite + Zoom link when someone registers
4. **Generates segmented emails** via Claude AI — different tone for customers vs. prospects
5. **Pauses for human review** — preview each email via live links before approving the send
6. **Sends personalized emails** through Brevo with HTML templates
7. **Logs everything** to Google Sheets — campaigns, individual sends, scheduled tasks
8. **Schedules follow-ups** — reminders 3 days before, post-event follow-ups 1 day after

## Deployment

The registration webhook is deployed to **Railway** (free tier) so the GitHub Pages landing pages can trigger confirmation emails for anyone who registers — no localhost required.

| Component | Hosting | URL |
|-----------|---------|-----|
| Landing pages | GitHub Pages | `bennybridger.github.io/webinar-automation/` |
| Registration webhook | Railway | `webinar-webhook-production.up.railway.app` |
| Web agent | Local (Flask) | `localhost:5001` |

The `webhook/` directory contains a self-contained Flask app with just the registration endpoint + Brevo email sending. It reads webinar details from a `BRIEF_JSON` environment variable on Railway.

## APIs Integrated (6)

| API | Purpose |
|-----|---------|
| **Zoom** | Server-to-Server OAuth — creates meetings programmatically |
| **Google Calendar** | Service account — adds events with Zoom join link |
| **Google Sheets** | Contact database, campaign logs, send tracking, follow-up scheduling |
| **HubSpot** | Marketing Forms API (free tier) — registration forms that feed into CRM |
| **Anthropic Claude** | Generates segmented email copy with different tone per audience |
| **Brevo** | Transactional email delivery (300/day free tier) |

## How the Email Segmentation Works

| Email Type | Customer Tone | Prospect Tone |
|-----------|--------------|---------------|
| **Invite** | Exclusive, insider access ("as a valued customer") | Educational, problem-aware ("you're invited") |
| **Reminder** | Shared — friendly urgency | Shared — friendly urgency |
| **Follow-up** | Deeper engagement CTA (strategy call, beta) | Conversion CTA (demo, free trial) |

## Registration Flow

```
Invite email → Landing page (HubSpot form) → Thank-you confirmation
    → Confirmation email with Zoom link + "Add to Calendar" button
    → Reminder email 3 days before (Zoom join link)
    → Post-event follow-up email 1 day after
```

## Two Interfaces

### 1. Web Agent (Conversational)

```bash
python3 app.py
# Open http://localhost:5001
```

Describe your webinar in plain English. The agent extracts a structured brief, confirms it with you, then runs the full pipeline. Emails pause for your review before sending.

### 2. CLI (JSON Brief)

```bash
# Full pipeline
python main.py launch --brief sample_brief.json

# Dry run (no emails sent)
python main.py launch --brief sample_brief.json --dry-run

# Individual commands
python main.py contacts --list
python main.py contacts --segment customer
python main.py event --create --brief sample_brief.json
python main.py generate --brief sample_brief.json --type invite
python main.py landing --brief sample_brief.json
python main.py status
python main.py followup --check
```

## Setup

### Prerequisites

- Python 3.9+
- Google Cloud project with Calendar API + Sheets API enabled
- Google service account with JSON key
- Brevo account (free tier — 300 emails/day)
- Zoom Server-to-Server OAuth app
- HubSpot account with private app (free tier)
- Anthropic API key

### Install

```bash
git clone https://github.com/bennybridger/webinar-automation.git
cd webinar-automation
pip install -r requirements.txt
cp .env.example .env
# Fill in all values in .env
```

### Environment Variables

```
BREVO_API_KEY=your-key
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=./service-account.json
GOOGLE_SHEET_ID=your-sheet-id-from-url
GOOGLE_CALENDAR_ID=your-email@gmail.com
ZOOM_ACCOUNT_ID=your-zoom-account-id
ZOOM_CLIENT_ID=your-zoom-client-id
ZOOM_CLIENT_SECRET=your-zoom-client-secret
HUBSPOT_ACCESS_TOKEN=pat-na2-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
SENDER_EMAIL=your-verified-brevo-email
SENDER_NAME=Your Name
```

### Google Sheets Structure

Create a sheet with 4 tabs:
- **Contacts**: `email | first_name | last_name | company | segment` (segment = `customer` or `prospect`)
- **Campaign Log**: auto-populated by the pipeline
- **Send Log**: auto-populated by the pipeline
- **Scheduled Tasks**: auto-populated for follow-ups

Share the sheet with your service account email (Editor access).

## Project Structure

| File | Purpose |
|------|---------|
| `app.py` | Flask web agent — conversational interface + pipeline with human review |
| `main.py` | CLI entry point + pipeline orchestrator with approval loop |
| `config.py` | Loads and validates all environment variables from `.env` |
| `modules/brief_agent.py` | Conversational AI that turns plain English into structured briefs |
| `modules/contact_manager.py` | Reads contacts from Google Sheets, segments by customer/prospect |
| `modules/event_creator.py` | Creates Zoom meeting + Google Calendar event |
| `modules/landing_page.py` | Creates HubSpot forms, generates HTML landing pages, sends confirmation emails |
| `modules/content_generator.py` | Calls Claude API to generate segmented email copy |
| `modules/email_sender.py` | Sends emails via Brevo API with Jinja2 HTML templates |
| `modules/tracker.py` | Logs campaigns and sends to Google Sheets |
| `modules/follow_up.py` | Schedules and executes reminder + follow-up emails |
| `templates/*.html` | HTML email templates (invite, reminder, follow-up, confirmation) |
| `webhook/` | Standalone webhook server deployed to Railway for registration emails |
| `docs/` | GitHub Pages — hosted landing pages + email previews |

## Built With

- Python 3 + Flask (web agent) + argparse (CLI)
- Anthropic Claude API (email content generation + conversational agent)
- Zoom Server-to-Server OAuth API (meeting creation)
- Google Calendar API (event creation)
- Google Sheets API via gspread (contacts + logging)
- HubSpot Marketing Forms API (registration forms → CRM)
- Brevo REST API (transactional email)
- Jinja2 (HTML email templating)
- GitHub Pages (landing page hosting)
- Railway (webhook deployment)
