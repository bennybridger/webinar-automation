"""
Landing Page Creator — creates a HubSpot registration form (free tier) and generates
a hosted-ready landing page with the form embedded.

Flow:
1. Creates a HubSpot form via Marketing Forms API → registrations go into HubSpot CRM
2. After form submission, redirects registrant to the Zoom meeting link
3. Generates a beautiful HTML landing page with the HubSpot form embedded
4. The HTML file can be hosted on GitHub Pages, Netlify, or Vercel for a live URL
"""

import sys
import os
import json
import re
from datetime import datetime
from urllib.parse import quote

import requests

sys.path.insert(0, "..")
from config import HUBSPOT_ACCESS_TOKEN, SENDER_NAME

HUBSPOT_BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
    "Content-Type": "application/json",
}


def _build_gcal_link(webinar_info):
    """
    Build a Google Calendar 'Add to Calendar' URL from webinar info.
    No API call needed — just a URL that opens Google Calendar with pre-filled fields.
    """
    title = webinar_info.get("title", "Webinar")
    description = webinar_info.get("description", "")
    date_str = webinar_info.get("date", "")  # "2026-04-15"
    time_str = webinar_info.get("time", "")  # "1:00 PM ET"
    duration = webinar_info.get("duration_minutes", 45)

    # Parse date + time into start datetime
    # Strip timezone abbreviation for parsing (e.g., "1:00 PM ET" → "1:00 PM")
    clean_time = re.sub(r'\s*(ET|EST|EDT|CT|CST|CDT|PT|PST|PDT|MT|MST|MDT)\s*$', '', time_str, flags=re.IGNORECASE).strip()

    try:
        start_dt = datetime.strptime(f"{date_str} {clean_time}", "%Y-%m-%d %I:%M %p")
    except ValueError:
        try:
            start_dt = datetime.strptime(f"{date_str} {clean_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            # Fallback: just use date at noon
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12)

    from datetime import timedelta
    end_dt = start_dt + timedelta(minutes=duration)

    # Google Calendar URL format: YYYYMMDDTHHMMSS
    fmt = "%Y%m%dT%H%M%S"
    dates = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": dates,
        "details": description,
    }

    query = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    return f"https://calendar.google.com/calendar/render?{query}"


def send_confirmation_email(to_email, to_name, webinar_info):
    """
    Send a registration confirmation email with calendar invite link.
    Called when someone submits the landing page registration form.

    Returns:
        dict with success, message_id, error
    """
    from modules.email_sender import send_email
    from jinja2 import Environment, FileSystemLoader

    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    jinja_env = Environment(loader=FileSystemLoader(templates_dir))
    template = jinja_env.get_template("confirmation.html")

    # Build Google Calendar link
    gcal_link = _build_gcal_link(webinar_info)

    # Format date nicely
    raw_date = webinar_info.get("date", "")
    try:
        nice_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except (ValueError, TypeError):
        nice_date = raw_date

    # Zoom join link from the brief
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

    if result["success"]:
        print(f"  [CONFIRMATION] Sent to {to_name} <{to_email}>")
    else:
        print(f"  [CONFIRMATION FAILED] {to_email}: {result['error']}")

    return result


def _get_portal_id():
    """Get the HubSpot portal ID for form embedding."""
    try:
        resp = requests.get(
            f"{HUBSPOT_BASE}/account-info/v3/details",
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return str(resp.json().get("portalId", ""))
    except Exception:
        return ""


def _create_hubspot_form(webinar_info, zoom_join_url=""):
    """
    Create a HubSpot form for webinar registration.
    Registrations flow into HubSpot CRM as contacts.
    After submission, redirects to Zoom meeting link.

    Returns:
        dict with form_id, portal_id, or None on failure
    """
    title = webinar_info["title"]
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def field(name, label, field_type, required=True):
        return {
            "name": name,
            "label": label,
            "fieldType": field_type,
            "objectTypeId": "0-1",
            "required": required,
            "validation": {
                "blockedEmailDomains": [],
                "useDefaultBlockList": False,
            },
        }

    # After form submission, show a thank you message (NOT a redirect to Zoom).
    # The Zoom link is sent via email — invite emails for pre-event, reminder day-of.
    post_submit = {
        "type": "thank_you",
        "value": "You're registered! Check your email for a calendar invite with the webinar link.",
    }

    payload = {
        "name": f"Webinar Registration: {title}",
        "formType": "hubspot",
        "createdAt": now,
        "updatedAt": now,
        "fieldGroups": [
            {"groupType": "default_group", "richTextType": "text", "fields": [field("firstname", "First Name", "single_line_text")]},
            {"groupType": "default_group", "richTextType": "text", "fields": [field("lastname", "Last Name", "single_line_text")]},
            {"groupType": "default_group", "richTextType": "text", "fields": [field("email", "Email", "email")]},
            {"groupType": "default_group", "richTextType": "text", "fields": [field("company", "Company", "single_line_text", False)]},
        ],
        "configuration": {
            "language": "en",
            "createNewContactForNewEmail": True,
            "postSubmitAction": post_submit,
        },
    }

    try:
        resp = requests.post(
            f"{HUBSPOT_BASE}/marketing/v3/forms",
            headers=HEADERS,
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        form_id = data.get("id", "")
        portal_id = _get_portal_id()

        print(f"  [SUCCESS] HubSpot form created (ID: {form_id})")
        print(f"  Registrations will appear in HubSpot CRM as contacts.")
        print(f"  After submission, shows thank-you confirmation (no redirect).")

        return {"form_id": form_id, "portal_id": portal_id}

    except requests.exceptions.HTTPError as e:
        status = e.response.status_code
        body = e.response.text
        if status == 401:
            print(f"  [ERROR] HubSpot auth failed — check HUBSPOT_ACCESS_TOKEN in .env")
        elif status == 403:
            print(f"  [ERROR] HubSpot scope missing — add 'forms' scope to your private app")
        else:
            print(f"  [ERROR] HubSpot Forms API error ({status}): {body[:300]}")
        return None
    except Exception as e:
        print(f"  [ERROR] Failed to create HubSpot form: {e}")
        return None


def _generate_landing_page_html(webinar_info, form_data, zoom_join_url="", webhook_url=""):
    """Generate a beautiful, mobile-responsive HTML landing page."""

    title = webinar_info["title"]
    speaker = webinar_info.get("speaker", "")
    raw_date = webinar_info.get("date", "")
    time = webinar_info.get("time", "")

    # Format date as human-readable (e.g., "April 15, 2026")
    try:
        date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except (ValueError, TypeError):
        date = raw_date
    duration = webinar_info.get("duration_minutes", 45)
    description = webinar_info.get("description", "")
    takeaways = webinar_info.get("key_takeaways", [])
    pain_point = webinar_info.get("target_pain_point", "")

    takeaways_html = "\n".join(f"            <li>{t}</li>" for t in takeaways)

    # Build form embed
    if form_data:
        portal_id = form_data["portal_id"]
        form_id = form_data["form_id"]
        form_section = f"""
        <div id="hubspot-form"></div>
        <div id="thank-you" style="display:none;text-align:center;padding:40px 20px;">
          <div style="width:56px;height:56px;background:#10b981;border-radius:50%;margin:0 auto 16px;display:flex;align-items:center;justify-content:center;">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          </div>
          <h3 style="color:#1a1a2e;font-size:22px;margin-bottom:8px;">You're registered!</h3>
          <p style="color:#6b7280;font-size:15px;line-height:1.6;">Check your inbox for a calendar invite<br>with the webinar link.</p>
        </div>
        <script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/embed/v2.js"></script>
        <script>
          hbspt.forms.create({{
            region: "na2",
            portalId: "{portal_id}",
            formId: "{form_id}",
            target: "#hubspot-form",
            css: "",
            cssClass: "hs-custom-form",
            onFormSubmit: function($form) {{
              // Capture form values before HubSpot clears them
              var email = $form.find('input[name="email"]').val() || '';
              var firstName = $form.find('input[name="firstname"]').val() || '';
              var lastName = $form.find('input[name="lastname"]').val() || '';
              // POST to our webhook to trigger confirmation email
              var webhookUrl = "{webhook_url}";
              if (webhookUrl) {{
                fetch(webhookUrl + '/webhook/registration', {{
                  method: 'POST',
                  headers: {{'Content-Type': 'application/json'}},
                  body: JSON.stringify({{
                    email: email,
                    first_name: firstName,
                    last_name: lastName
                  }})
                }}).catch(function() {{}});
              }}
            }},
            onFormSubmitted: function() {{
              document.getElementById('hubspot-form').style.display = 'none';
              document.getElementById('thank-you').style.display = 'block';
            }}
          }});
        </script>"""
    else:
        # Fallback: simple HTML form that redirects to Zoom
        redirect = zoom_join_url or "#"
        form_section = f"""
        <form action="{redirect}" method="GET" class="fallback-form">
          <input type="text" name="first_name" placeholder="First Name" required>
          <input type="text" name="last_name" placeholder="Last Name" required>
          <input type="email" name="email" placeholder="Work Email" required>
          <input type="text" name="company" placeholder="Company (optional)">
          <button type="submit">Register Now — It's Free</button>
        </form>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | Live Webinar</title>
  <meta name="description" content="{description[:155]}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description[:155]}">
  <meta property="og:type" content="website">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f4f4f7; color: #1a1a2e; }}

    /* Hero */
    .hero {{
      background: linear-gradient(135deg, #6c63ff 0%, #4834d4 100%);
      padding: 64px 24px 80px;
      text-align: center;
    }}
    .hero .tag {{
      display: inline-block;
      color: rgba(255,255,255,0.9);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 2.5px;
      font-weight: 600;
      background: rgba(255,255,255,0.15);
      padding: 6px 16px;
      border-radius: 20px;
      margin-bottom: 20px;
    }}
    .hero h1 {{
      color: #fff;
      font-size: 40px;
      line-height: 1.15;
      max-width: 640px;
      margin: 0 auto 20px;
      font-weight: 700;
    }}
    .hero .meta {{
      color: rgba(255,255,255,0.9);
      font-size: 17px;
      font-weight: 400;
    }}
    .hero .meta strong {{ font-weight: 600; }}

    /* Card */
    .container {{ max-width: 720px; margin: -48px auto 48px; padding: 0 16px; }}
    .card {{
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.1);
      overflow: hidden;
    }}

    /* Content */
    .content {{ padding: 36px 32px; }}
    .content > p {{ font-size: 17px; line-height: 1.75; color: #374151; margin-bottom: 24px; }}

    /* Takeaways */
    .takeaways {{
      background: #f8f7ff;
      border-left: 4px solid #6c63ff;
      padding: 24px 28px;
      margin: 28px 0;
      border-radius: 0 12px 12px 0;
    }}
    .takeaways h3 {{ font-size: 17px; margin-bottom: 12px; color: #1a1a2e; }}
    .takeaways ul {{ padding-left: 20px; color: #374151; }}
    .takeaways li {{ margin-bottom: 10px; line-height: 1.65; font-size: 15px; }}

    /* Pain Point */
    .pain {{
      background: #fef3cd;
      border-left: 4px solid #f59e0b;
      padding: 18px 24px;
      margin: 28px 0;
      border-radius: 0 12px 12px 0;
    }}
    .pain p {{ color: #92400e; font-size: 15px; line-height: 1.6; margin: 0; }}

    /* Speaker */
    .speaker {{
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 18px 20px;
      background: #f9fafb;
      border-radius: 12px;
      margin: 28px 0 0;
    }}
    .speaker-avatar {{
      width: 48px; height: 48px;
      background: linear-gradient(135deg, #6c63ff, #4834d4);
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 700; font-size: 18px;
      flex-shrink: 0;
    }}
    .speaker .name {{ font-weight: 600; font-size: 15px; }}
    .speaker .role {{ color: #6b7280; font-size: 13px; margin-top: 2px; }}

    /* Form Section */
    .form-section {{
      padding: 36px 32px;
      background: #f9fafb;
      border-top: 1px solid #e5e7eb;
    }}
    .form-section h3 {{
      font-size: 22px;
      margin-bottom: 6px;
      text-align: center;
      font-weight: 700;
    }}
    .form-section .subtitle {{
      color: #6b7280;
      font-size: 14px;
      text-align: center;
      margin-bottom: 24px;
    }}

    /* HubSpot form overrides */
    .hs-custom-form .hs-form-field {{ margin-bottom: 12px; }}
    .hs-custom-form input[type="text"],
    .hs-custom-form input[type="email"] {{
      width: 100% !important;
      padding: 12px 16px !important;
      border: 2px solid #e5e7eb !important;
      border-radius: 8px !important;
      font-size: 15px !important;
      outline: none !important;
      transition: border-color 0.2s !important;
      font-family: inherit !important;
    }}
    .hs-custom-form input:focus {{
      border-color: #6c63ff !important;
    }}
    .hs-custom-form .hs-submit {{
      margin-top: 8px;
    }}
    .hs-custom-form input[type="submit"],
    .hs-custom-form .hs-button,
    .hs-custom-form .hs-button.primary,
    #hubspot-form input[type="submit"],
    #hubspot-form .hs-button {{
      width: 100% !important;
      background: linear-gradient(135deg, #6c63ff, #4834d4) !important;
      background-color: #6c63ff !important;
      color: #fff !important;
      padding: 14px 28px !important;
      border: none !important;
      border-radius: 8px !important;
      font-size: 16px !important;
      font-weight: 600 !important;
      cursor: pointer !important;
      font-family: inherit !important;
      -webkit-appearance: none !important;
    }}
    .hs-custom-form label {{
      font-size: 14px !important;
      font-weight: 500 !important;
      color: #374151 !important;
      margin-bottom: 4px !important;
      display: block !important;
    }}

    /* Fallback form */
    .fallback-form {{ display: flex; flex-direction: column; gap: 12px; }}
    .fallback-form input {{
      padding: 12px 16px;
      border: 2px solid #e5e7eb;
      border-radius: 8px;
      font-size: 15px;
      outline: none;
      transition: border-color 0.2s;
      font-family: inherit;
    }}
    .fallback-form input:focus {{ border-color: #6c63ff; }}
    .fallback-form button {{
      background: linear-gradient(135deg, #6c63ff, #4834d4);
      color: #fff;
      padding: 14px 28px;
      border: none;
      border-radius: 8px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      margin-top: 4px;
    }}

    /* Footer */
    .footer {{
      text-align: center;
      padding: 28px;
      color: #9ca3af;
      font-size: 13px;
    }}

    /* Mobile */
    @media (max-width: 480px) {{
      .hero {{ padding: 44px 16px 64px; }}
      .hero h1 {{ font-size: 28px; }}
      .content, .form-section {{ padding: 24px 20px; }}
    }}
  </style>
</head>
<body>
  <div class="hero">
    <span class="tag">Live Webinar</span>
    <h1>{title}</h1>
    <p class="meta"><strong>{date}</strong> at <strong>{time}</strong> &middot; {duration} minutes</p>
  </div>

  <div class="container">
    <div class="card">
      <div class="content">
        <p>{description}</p>

        <div class="takeaways">
          <h3>What you'll learn:</h3>
          <ul>
{takeaways_html}
          </ul>
        </div>

        <div class="pain">
          <p><strong>Sound familiar?</strong> {pain_point}</p>
        </div>

        <div class="speaker">
          <div class="speaker-avatar">{speaker[0] if speaker else "?"}</div>
          <div>
            <p class="name">{speaker}</p>
            <p class="role">Your host for this session</p>
          </div>
        </div>
      </div>

      <div class="form-section">
        <h3>Save Your Spot</h3>
        <p class="subtitle">Free &middot; {duration} minutes &middot; Live Q&A included</p>
        {form_section}
      </div>
    </div>
  </div>

  <div class="footer">
    <p>&copy; {datetime.now().year} {SENDER_NAME}. All rights reserved.</p>
  </div>
</body>
</html>"""


def create_hubspot_landing_page(webinar_info, zoom_join_url="", webhook_url=""):
    """
    Create a webinar registration landing page with HubSpot form integration.

    1. Creates a HubSpot form (registrations → CRM)
    2. Generates a beautiful HTML landing page with the form embedded
    3. Saves the HTML file to output/ directory

    Args:
        webinar_info: dict with webinar brief details
        zoom_join_url: the Zoom meeting link
        webhook_url: base URL for the confirmation email webhook (e.g. "http://localhost:5001")

    Returns:
        dict with landing_page_file, hubspot_form_id, etc. or None on failure
    """
    title = webinar_info["title"]

    # Step 1: Create HubSpot form
    print("\n  Creating HubSpot registration form...")
    form_data = _create_hubspot_form(webinar_info, zoom_join_url)

    # Step 2: Generate landing page HTML
    print("\n  Generating landing page...")
    html = _generate_landing_page_html(webinar_info, form_data, zoom_join_url, webhook_url=webhook_url)

    # Step 3: Save to output directory
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    slug = title.lower().replace(" ", "-")
    slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
    filename = f"landing-{slug}.html"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w") as f:
        f.write(html)

    # Also copy to docs/ for GitHub Pages hosting
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
    os.makedirs(docs_dir, exist_ok=True)
    docs_filepath = os.path.join(docs_dir, filename)
    with open(docs_filepath, "w") as f:
        f.write(html)

    # GitHub Pages URL (live public URL)
    github_pages_url = f"https://bennybridger.github.io/webinar-automation/{filename}"

    print(f"\n[SUCCESS] Landing page created: {filepath}")
    print(f"  → Local preview: file://{filepath}")
    print(f"  → GitHub Pages:  {github_pages_url}")
    if form_data:
        print(f"  → HubSpot form embedded — registrations flow into your CRM")
        print(f"  → After registration, shows thank-you confirmation")

    result = {
        "landing_page_file": filepath,
        "landing_page_url": github_pages_url,
        "source": "hubspot_form" if form_data else "standalone",
    }
    if form_data:
        result["hubspot_form_id"] = form_data["form_id"]
        result["hubspot_portal_id"] = form_data["portal_id"]

    return result


def handle_landing_page_command(args):
    """Handle the 'landing' CLI subcommand."""
    import json as json_mod

    if not args.brief:
        print("Usage: python main.py landing --brief path/to/brief.json")
        return

    try:
        with open(args.brief) as f:
            brief = json_mod.load(f)
    except (FileNotFoundError, json_mod.JSONDecodeError) as e:
        print(f"\n[ERROR] Could not read brief: {e}")
        return

    zoom_url = brief.get("zoom_join_url", "")
    print("\n--- Creating webinar landing page ---")
    result = create_hubspot_landing_page(brief, zoom_url)

    if result:
        print(f"\n  Landing page ready!")
    else:
        print(f"\n  [ERROR] Could not create landing page.")
