"""
Content Generator — uses Claude API to generate segmented email content for webinar campaigns.
"""

import sys
import json
import anthropic

sys.path.insert(0, "..")
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are an expert B2B email copywriter. You write high-converting emails for webinar campaigns.

Your writing rules:
- Short paragraphs (2-3 sentences max)
- Single, clear CTA per email
- Mobile-friendly: no long lines, no complex formatting
- Personalization tokens: use {first_name} and {company} where appropriate
- Professional but warm tone — never salesy or pushy
- Subject lines under 50 characters
- Preview text under 90 characters that complements (not repeats) the subject line

You return structured JSON only. No markdown, no extra text."""


def _build_prompt(template_type, segment, webinar_info):
    """Build the user prompt for Claude based on template type and segment."""

    brief_context = f"""Webinar Details:
- Title: {webinar_info['title']}
- Speaker: {webinar_info.get('speaker', 'TBD')}
- Date: {webinar_info['date']} at {webinar_info['time']}
- Duration: {webinar_info.get('duration_minutes', 45)} minutes
- Description: {webinar_info['description']}
- Key Takeaways: {json.dumps(webinar_info.get('key_takeaways', []))}
- Target Pain Point: {webinar_info.get('target_pain_point', '')}
"""

    landing_url = webinar_info.get("landing_page_url", "")
    zoom_url = webinar_info.get("zoom_join_url", "")
    event_link = webinar_info.get("event_link", "")
    registration_link = landing_url or zoom_url or event_link or "{webinar_link}"

    if template_type == "invite" and segment == "customer":
        tone = f"""Tone: Exclusive, insider access. These are existing customers.
CTA text: {webinar_info.get('cta_customers', 'Join us for an exclusive look')}
Registration link: {registration_link}"""

    elif template_type == "invite" and segment == "prospect":
        tone = f"""Tone: Educational, problem-aware. These are prospects who haven't bought yet.
CTA text: {webinar_info.get('cta_prospects', 'See how leading teams are doing this')}
Registration link: {registration_link}"""

    elif template_type == "reminder":
        tone = f"""Tone: Friendly urgency. The webinar is in 3 days. Keep it short.
This goes to both customers and prospects who were already invited.
Registration link: {registration_link}"""

    elif template_type == "followup" and segment == "customer":
        tone = """Tone: Grateful, deepening relationship. Thank them for attending (or share the recording if they missed it).
CTA: Invite them to a deeper engagement — a 1:1 strategy call, beta access, or exclusive community.
Recording link: {recording_link}"""

    elif template_type == "followup" and segment == "prospect":
        tone = """Tone: Helpful, next-step focused. Share the recording and key takeaways.
CTA: Invite them to book a demo or start a free trial.
Recording link: {recording_link}"""

    else:
        tone = "Tone: Professional and clear."

    return f"""{brief_context}

{tone}

Generate a single email. Return ONLY valid JSON with these exact keys:
{{
  "subject": "subject line here",
  "preview_text": "preview text here",
  "body_text": "full email body as plain text with {{first_name}} and {{company}} tokens. Use \\n for line breaks."
}}"""


def generate_email_content(template_type, segment, webinar_info):
    """
    Generate email content using Claude API.

    Args:
        template_type: "invite", "reminder", or "followup"
        segment: "customer" or "prospect"
        webinar_info: dict with webinar details from the brief + event creation results

    Returns:
        dict with subject, preview_text, body_text — or None on failure
    """
    prompt = _build_prompt(template_type, segment, webinar_info)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[0].text.strip()

        # Parse JSON from response (handle possible markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        content = json.loads(raw)

        required_keys = {"subject", "preview_text", "body_text"}
        if not required_keys.issubset(content.keys()):
            missing = required_keys - content.keys()
            print(f"\n[ERROR] Claude response missing keys: {missing}")
            return None

        return content

    except json.JSONDecodeError:
        print(f"\n[ERROR] Claude returned invalid JSON. Raw response:\n{raw[:500]}")
        return None
    except anthropic.RateLimitError:
        print("\n[ERROR] Claude API rate limited. Wait a moment and try again.")
        return None
    except anthropic.APIError as e:
        print(f"\n[ERROR] Claude API error: {e}")
        return None
    except Exception as e:
        print(f"\n[ERROR] Unexpected error generating content: {e}")
        return None


def generate_all_campaign_emails(webinar_info):
    """
    Generate all 5 email variants for a webinar campaign.

    Returns:
        dict keyed by "{type}_{segment}" with email content, e.g.:
        {
            "invite_customer": {subject, preview_text, body_text},
            "invite_prospect": {subject, preview_text, body_text},
            "reminder_all": {subject, preview_text, body_text},
            "followup_customer": {subject, preview_text, body_text},
            "followup_prospect": {subject, preview_text, body_text},
        }
    """
    variants = [
        ("invite", "customer"),
        ("invite", "prospect"),
        ("reminder", "all"),
        ("followup", "customer"),
        ("followup", "prospect"),
    ]

    results = {}
    for template_type, segment in variants:
        key = f"{template_type}_{segment}"
        print(f"\n  Generating {key}...", end=" ", flush=True)
        content = generate_email_content(template_type, segment, webinar_info)
        if content:
            results[key] = content
            print(f"done — subject: \"{content['subject']}\"")
        else:
            print("FAILED")

    return results


def preview_email(content, contact=None):
    """
    Print a formatted preview of an email to the terminal.

    Args:
        content: dict with subject, preview_text, body_text
        contact: optional dict with first_name, company for personalization preview
    """
    body = content["body_text"]

    if contact:
        body = body.replace("{first_name}", contact.get("first_name", "Friend"))
        body = body.replace("{company}", contact.get("company", "your company"))

    print(f"\n  {'='*60}")
    print(f"  Subject:  {content['subject']}")
    print(f"  Preview:  {content['preview_text']}")
    print(f"  {'─'*60}")
    # Convert \n in body text to actual newlines for display
    body_display = body.replace("\\n", "\n")
    for line in body_display.split("\n"):
        print(f"  {line}")
    print(f"  {'='*60}")


def handle_generate_command(args):
    """Handle the 'generate' CLI subcommand."""
    import json as json_mod

    try:
        with open(args.brief) as f:
            brief = json_mod.load(f)
    except (FileNotFoundError, json_mod.JSONDecodeError) as e:
        print(f"\n[ERROR] Could not read brief: {e}")
        return

    email_type = args.type

    if email_type == "invite":
        segments = ["customer", "prospect"]
    elif email_type == "reminder":
        segments = ["all"]
    elif email_type == "followup":
        segments = ["customer", "prospect"]
    else:
        segments = ["customer"]

    print(f"\n--- Generating {email_type} emails via Claude API ---")

    for segment in segments:
        key = f"{email_type}_{segment}"
        print(f"\n  Generating {key}...")
        content = generate_email_content(email_type, segment, brief)

        if content:
            # Show preview with a sample contact
            sample = {"first_name": "Sarah", "company": "Acme Corp"}
            print(f"\n  Preview (personalized for {sample['first_name']} at {sample['company']}):")
            preview_email(content, sample)
        else:
            print(f"  [FAILED] Could not generate {key}")
