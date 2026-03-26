"""
Email Sender — sends transactional emails via Brevo REST API with Jinja2 templating.
"""

import sys
import os

import requests
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, "..")
from config import BREVO_API_KEY, SENDER_EMAIL, SENDER_NAME

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
DAILY_LIMIT = 300

# Set up Jinja2 template loader
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def send_email(to_email, to_name, subject, html_content):
    """
    Send a single email via Brevo transactional API.

    Returns:
        dict with success, message_id, error
    """
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
        return {
            "success": True,
            "message_id": data.get("messageId", ""),
            "error": None,
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        body = e.response.text
        if status == 401:
            error_msg = "Invalid Brevo API key. Check BREVO_API_KEY in .env"
        elif status == 400:
            error_msg = f"Bad request: {body}"
        elif status == 429:
            error_msg = "Rate limited by Brevo. Wait and retry."
        else:
            error_msg = f"HTTP {status}: {body}"
        return {"success": False, "message_id": "", "error": error_msg}
    except requests.exceptions.Timeout:
        return {"success": False, "message_id": "", "error": "Brevo API timed out"}
    except Exception as e:
        return {"success": False, "message_id": "", "error": str(e)}


def render_email_html(template_name, content, contact, extra_vars=None):
    """
    Render an HTML email template with Jinja2.

    Args:
        template_name: e.g. "invite_customer.html"
        content: dict with subject, preview_text, body_text from content generator
        contact: dict with first_name, last_name, company, email
        extra_vars: optional dict with webinar_link, sender_name, etc.

    Returns:
        Rendered HTML string
    """
    template = jinja_env.get_template(template_name)

    # Personalize the body text
    body_text = content["body_text"]
    body_text = body_text.replace("{first_name}", contact.get("first_name", "there"))
    body_text = body_text.replace("{company}", contact.get("company", "your company"))

    # Convert plain text body to HTML paragraphs
    paragraphs = body_text.replace("\\n\\n", "\n\n").replace("\\n", "\n").split("\n\n")
    body_html = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

    vars = {
        "subject": content["subject"],
        "preview_text": content["preview_text"],
        "body_html": body_html,
        "first_name": contact.get("first_name", "there"),
        "company": contact.get("company", ""),
        "sender_name": SENDER_NAME,
        "webinar_link": "",
        "cta_link": "",
    }

    if extra_vars:
        vars.update(extra_vars)

    return template.render(**vars)


def send_batch(contacts, template_name, content, extra_vars=None, dry_run=False, send_count_today=0):
    """
    Send emails to a list of contacts.

    Args:
        contacts: list of contact dicts
        template_name: HTML template filename
        content: dict with subject, preview_text, body_text
        extra_vars: extra template variables (webinar_link, etc.)
        dry_run: if True, render but don't send
        send_count_today: current daily send count for rate limiting

    Returns:
        dict with sent, failed, errors, results (list of per-contact results)
    """
    sent = 0
    failed = 0
    errors = []
    results = []

    for i, contact in enumerate(contacts):
        # Rate limit check
        if not dry_run and (send_count_today + sent) >= DAILY_LIMIT:
            remaining = len(contacts) - i
            msg = f"Brevo daily limit ({DAILY_LIMIT}) reached. {remaining} emails not sent."
            print(f"\n  [WARNING] {msg}")
            errors.append(msg)
            break

        email = contact.get("email", "").strip()
        name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

        if not email:
            failed += 1
            errors.append(f"Missing email for contact: {name}")
            continue

        # Render personalized HTML
        html = render_email_html(template_name, content, contact, extra_vars)

        if dry_run:
            print(f"  [DRY RUN] Would send to {name} <{email}> — subject: \"{content['subject']}\"")
            sent += 1
            results.append({"email": email, "status": "dry_run", "message_id": ""})
            continue

        # Send
        result = send_email(email, name, content["subject"], html)

        if result["success"]:
            sent += 1
            print(f"  [SENT] {name} <{email}> — ID: {result['message_id']}")
        else:
            failed += 1
            print(f"  [FAILED] {name} <{email}> — {result['error']}")
            errors.append(f"{email}: {result['error']}")

        results.append({
            "email": email,
            "status": "sent" if result["success"] else "failed",
            "message_id": result.get("message_id", ""),
            "error": result.get("error", ""),
        })

    return {"sent": sent, "failed": failed, "errors": errors, "results": results}
