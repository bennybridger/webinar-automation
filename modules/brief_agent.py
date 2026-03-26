"""
Brief Agent — conversational AI agent that turns messy natural language input
into a structured webinar brief, then launches the pipeline.

Uses Claude to interpret unstructured descriptions, extract key details,
fill in intelligent defaults, and confirm with the user before executing.
"""

import sys
import json
from datetime import datetime, timedelta

import anthropic

sys.path.insert(0, "..")
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are the Webinar Launch Agent — a helpful AI assistant that helps marketers set up webinar campaigns through conversation.

Your job:
1. Take a messy, informal description of a webinar idea
2. Extract and structure it into a complete webinar brief
3. Fill in smart defaults for anything missing
4. Present the brief clearly for the user to approve or adjust
5. When approved, you'll signal that the brief is ready for launch

The structured brief needs these fields:
- title: A compelling webinar title (professional, clear)
- speaker: Speaker name and title
- date: YYYY-MM-DD format
- time: e.g. "1:00 PM ET"
- duration_minutes: number (default 45)
- description: 1-2 sentence description of what the webinar covers
- key_takeaways: array of 3 specific things attendees will learn
- target_pain_point: The core problem the audience faces
- cta_customers: CTA text for existing customers (exclusive, insider tone)
- cta_prospects: CTA text for prospects (educational, value-driven tone)

When responding:
- Be conversational and friendly — the user is a marketer, not a developer
- If the user gives you a messy brain dump, work with it — extract what you can and make smart assumptions
- Always show the complete brief before asking for approval
- If key details are missing (like date), suggest reasonable defaults
- Format the brief in a clean, readable way
- When the user approves, respond with EXACTLY this JSON block (and nothing else after it):

```json
{"status": "approved", "brief": { ... the complete brief object ... }}
```

- If the user wants to edit something, make the change and show the updated brief
- Keep your responses concise — marketers are busy"""


def chat(messages):
    """
    Send a conversation to Claude and get a response.

    Args:
        messages: list of {"role": "user"|"assistant", "content": "..."} dicts

    Returns:
        str: Claude's response text
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text
    except anthropic.APIError as e:
        return f"[Error communicating with Claude: {e}]"
    except Exception as e:
        return f"[Unexpected error: {e}]"


def extract_approved_brief(response_text):
    """
    Check if Claude's response contains an approved brief JSON block.

    Returns:
        dict (the brief) if approved, None otherwise
    """
    if '"status": "approved"' not in response_text and '"status":"approved"' not in response_text:
        return None

    # Extract JSON block
    try:
        # Look for ```json ... ``` block
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            # Try to find raw JSON
            start = response_text.index("{")
            # Find the matching closing brace
            depth = 0
            for i, c in enumerate(response_text[start:], start):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        json_str = response_text[start:i + 1]
                        break

        data = json.loads(json_str)

        if data.get("status") == "approved" and "brief" in data:
            return data["brief"]

    except (json.JSONDecodeError, ValueError, UnboundLocalError):
        pass

    return None
