"""
Standalone webhook server for webinar registration confirmation emails.
Deployed to Render (free tier) so GitHub Pages landing pages can trigger
confirmation emails for anyone who registers — no localhost needed.
"""

import os
import re
import json
from datetime import datetime, timedelta
from urllib.parse import quote

import requests
from flask import Flask, request, jsonify
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__)

# --- Config (env vars only, no .env file) ---
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
SENDER_NAME = os.environ.get("SENDER_NAME", "Webinar Team")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

# Jinja2 templates
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def load_brief():
    """
    Load webinar brief from BRIEF_JSON env var (preferred) or local file fallback.
    """
    brief_json = os.environ.get("BRIEF_JSON", "")
    if brief_json:
        try:
            return json.loads(brief_json)
        except json.JSONDecodeError:
            pass

    brief_path = os.path.join(os.path.dirname(__file__), "brief.json")
    try:
        with open(brief_path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def send_email(to_email, to_name, subject, html_content):
    """Send a single email via Brevo transactional API."""
    payload = {
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        resp = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return {"success": True, "message_id": data.get("messageId", ""), "error": None}
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        body = e.response.text
        if status == 401:
            error_msg = "Invalid Brevo API key"
        elif status == 400:
            error_msg = f"Bad request: {body}"
        elif status == 429:
            error_msg = "Rate limited by Brevo"
        else:
            error_msg = f"HTTP {status}: {body}"
        return {"success": False, "message_id": "", "error": error_msg}
    except requests.exceptions.Timeout:
        return {"success": False, "message_id": "", "error": "Brevo API timed out"}
    except Exception as e:
        return {"success": False, "message_id": "", "error": str(e)}


def _build_gcal_link(webinar_info):
    """Build a Google Calendar 'Add to Calendar' URL from webinar info."""
    title = webinar_info.get("title", "Webinar")
    description = webinar_info.get("description", "")
    date_str = webinar_info.get("date", "")
    time_str = webinar_info.get("time", "")
    duration = webinar_info.get("duration_minutes", 45)

    clean_time = re.sub(
        r'\s*(ET|EST|EDT|CT|CST|CDT|PT|PST|PDT|MT|MST|MDT)\s*$',
        '', time_str, flags=re.IGNORECASE
    ).strip()

    try:
        start_dt = datetime.strptime(f"{date_str} {clean_time}", "%Y-%m-%d %I:%M %p")
    except ValueError:
        try:
            start_dt = datetime.strptime(f"{date_str} {clean_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12)

    end_dt = start_dt + timedelta(minutes=duration)
    fmt = "%Y%m%dT%H%M%S"
    dates = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"

    zoom_url = webinar_info.get("zoom_join_url", "")
    details = description
    if zoom_url:
        details = f"Join link: {zoom_url}\n\n{description}"

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": dates,
        "details": details,
        "location": zoom_url,
    }
    query = "&".join(f"{k}={quote(str(v), safe='/')}" for k, v in params.items())
    return f"https://calendar.google.com/calendar/render?{query}"


def send_confirmation_email(to_email, to_name, webinar_info):
    """Send a registration confirmation email with calendar invite link."""
    template = jinja_env.get_template("confirmation.html")
    gcal_link = _build_gcal_link(webinar_info)

    raw_date = webinar_info.get("date", "")
    try:
        nice_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except (ValueError, TypeError):
        nice_date = raw_date

    webinar_link = webinar_info.get("zoom_join_url", "") or webinar_info.get("event_link", "")

    html = template.render(
        first_name=to_name.split()[0] if to_name else "there",
        webinar_title=webinar_info.get("title", "Webinar"),
        webinar_date=nice_date,
        webinar_time=webinar_info.get("time", ""),
        duration=webinar_info.get("duration_minutes", 45),
        speaker=webinar_info.get("speaker", ""),
        webinar_link=webinar_link,
        gcal_link=gcal_link,
        sender_name=SENDER_NAME,
    )

    subject = f"You're registered: {webinar_info.get('title', 'Webinar')}"
    result = send_email(to_email, to_name, subject, html)
    return result


# --- Routes ---

@app.route("/")
def home():
    """Portfolio-ready landing page for the webhook service."""
    brief = load_brief()
    brief_loaded = brief is not None
    webinar_title = brief.get("title", "—") if brief else "—"
    landing_url = brief.get("landing_page_url", "") if brief else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Webinar Webhook API</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f4f4f7; color: #1a1a2e; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 24px; }}
    .card {{ background: #fff; border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); max-width: 600px; width: 100%; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #6c63ff 0%, #4834d4 100%); padding: 40px 32px; text-align: center; }}
    .header h1 {{ color: #fff; font-size: 24px; font-weight: 700; margin-bottom: 8px; }}
    .header p {{ color: rgba(255,255,255,0.85); font-size: 14px; }}
    .badge {{ display: inline-block; background: rgba(255,255,255,0.2); color: #fff; font-size: 11px; text-transform: uppercase; letter-spacing: 2px; font-weight: 600; padding: 4px 12px; border-radius: 12px; margin-bottom: 16px; }}
    .body {{ padding: 32px; }}
    .status {{ display: flex; align-items: center; gap: 8px; margin-bottom: 20px; padding: 12px 16px; background: #f0fdf4; border-radius: 8px; border: 1px solid #bbf7d0; }}
    .dot {{ width: 8px; height: 8px; background: #22c55e; border-radius: 50%; }}
    .status span {{ font-size: 14px; color: #166534; font-weight: 500; }}
    .info {{ margin-bottom: 24px; }}
    .info p {{ font-size: 14px; color: #64748b; line-height: 1.6; margin-bottom: 12px; }}
    .info strong {{ color: #1a1a2e; }}
    .section-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #94a3b8; font-weight: 600; margin-bottom: 8px; }}
    .detail {{ font-size: 14px; color: #334155; margin-bottom: 16px; }}
    .links {{ display: flex; flex-direction: column; gap: 8px; }}
    .links a {{ display: flex; align-items: center; gap: 8px; padding: 12px 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; text-decoration: none; color: #6c63ff; font-size: 14px; font-weight: 500; transition: all 0.15s; }}
    .links a:hover {{ background: #f0edff; border-color: #6c63ff; }}
    .links .arrow {{ margin-left: auto; color: #94a3b8; }}
    .footer {{ text-align: center; padding: 16px 32px 24px; }}
    .footer p {{ font-size: 12px; color: #94a3b8; }}
    .endpoint {{ font-family: 'SF Mono', Monaco, Consolas, monospace; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="badge">API Service</div>
      <h1>Webinar Launch Automation Engine</h1>
      <p>Registration webhook powering confirmation emails</p>
    </div>
    <div class="body">
      <div class="status">
        <div class="dot"></div>
        <span>Service running &mdash; brief {"loaded" if brief_loaded else "not loaded"}</span>
      </div>

      <div class="info">
        <p>This API receives registration form submissions from hosted landing pages and sends confirmation emails with Zoom links and calendar invites via Brevo.</p>
        <div class="section-label">Current Webinar</div>
        <div class="detail">{webinar_title}</div>
        <div class="section-label">Endpoint</div>
        <div class="detail"><span class="endpoint">POST /webhook/registration</span></div>
      </div>

      <div class="section-label">Links</div>
      <div class="links">
        {"<a href='" + landing_url + "'>Try it &mdash; register on the live landing page<span class='arrow'>&rarr;</span></a>" if landing_url else ""}
        <a href="https://github.com/bennybridger/webinar-automation">GitHub repo + full README<span class="arrow">&rarr;</span></a>
        <a href="https://github.com/bennybridger/webinar-automation/blob/main/README.md">Architecture &amp; API documentation<span class="arrow">&rarr;</span></a>
      </div>
    </div>
    <div class="footer">
      <p>Built by Benny Bridger &middot; Python + Flask + Brevo + HubSpot + Zoom + Google Calendar</p>
    </div>
  </div>
</body>
</html>"""


@app.route("/health")
def health():
    """JSON health check for programmatic use."""
    return jsonify({"status": "ok", "service": "webinar-webhook"})


@app.route("/webhook/registration", methods=["POST", "OPTIONS"])
def registration_webhook():
    """Receive form submission data and send a confirmation email."""
    if request.method == "OPTIONS":
        resp = app.make_default_options_response()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()

    if not email:
        resp = jsonify({"error": "Missing email"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 400

    name = f"{first_name} {last_name}".strip() or email

    brief = load_brief()
    if not brief:
        resp = jsonify({"error": "No active webinar found"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 404

    result = send_confirmation_email(email, name, brief)

    if result["success"]:
        resp = jsonify({"ok": True, "message_id": result["message_id"]})
    else:
        resp = jsonify({"error": result["error"]})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp, 500

    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5002))
    print(f"\n{'='*50}")
    print(f"  WEBINAR WEBHOOK SERVER")
    print(f"  Running on http://localhost:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
