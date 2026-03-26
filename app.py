#!/usr/bin/env python3
"""
Webinar Launch Agent — Web Interface
A conversational AI agent that turns plain English into a full webinar launch.
"""

import json
import os
import sys
import threading
import time
from datetime import datetime

from flask import Flask, render_template_string, request, jsonify, Response
import queue

# Ensure modules can import config
sys.path.insert(0, os.path.dirname(__file__))

app = Flask(__name__)

# Store conversations per session (simple in-memory for demo)
sessions = {}
pipeline_status = {}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Webinar Launch Agent</title>
  <style>
    :root {
      --purple: #6c63ff;
      --purple-dark: #4834d4;
      --bg: #f4f4f7;
      --card: #ffffff;
      --text: #1a1a2e;
      --text-light: #6b7280;
      --border: #e5e7eb;
      --success: #10b981;
      --warning: #f59e0b;
    }

    * { margin: 0; padding: 0; box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Header */
    .header {
      background: linear-gradient(135deg, var(--purple), var(--purple-dark));
      padding: 20px 24px;
      color: white;
      flex-shrink: 0;
    }
    .header h1 { font-size: 20px; font-weight: 700; }
    .header p { font-size: 13px; opacity: 0.85; margin-top: 4px; }

    /* Chat area */
    .chat-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
      max-width: 800px;
      width: 100%;
      margin: 0 auto;
    }

    .message {
      max-width: 85%;
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 15px;
      line-height: 1.6;
      animation: fadeIn 0.3s ease;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .message.agent {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px 16px 16px 4px;
      align-self: flex-start;
      box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }

    .message.user {
      background: var(--purple);
      color: white;
      border-radius: 16px 16px 4px 16px;
      align-self: flex-end;
    }

    .message.system {
      background: #f0fdf4;
      border: 1px solid #bbf7d0;
      border-radius: 12px;
      align-self: center;
      text-align: center;
      font-size: 14px;
      color: #166534;
      max-width: 100%;
    }

    .message.system.error {
      background: #fef2f2;
      border-color: #fecaca;
      color: #991b1b;
    }

    .message.system.pipeline {
      background: #f5f3ff;
      border-color: #c4b5fd;
      color: #4c1d95;
      text-align: left;
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 13px;
      white-space: pre-wrap;
    }

    .message pre {
      background: #f8f7ff;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin: 12px 0 8px;
      overflow-x: auto;
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 13px;
      line-height: 1.5;
    }

    .message .brief-card {
      background: #f9fafb;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 16px;
      margin: 12px 0;
    }
    .message .brief-card h4 {
      font-size: 14px;
      color: var(--purple);
      margin-bottom: 8px;
    }

    /* Typing indicator */
    .typing {
      display: flex;
      gap: 4px;
      padding: 14px 18px;
      align-self: flex-start;
    }
    .typing span {
      width: 8px; height: 8px;
      background: #cbd5e1;
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out;
    }
    .typing span:nth-child(2) { animation-delay: 0.2s; }
    .typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
      40% { transform: scale(1); opacity: 1; }
    }

    /* Input area */
    .input-area {
      border-top: 1px solid var(--border);
      background: var(--card);
      padding: 16px 24px;
      flex-shrink: 0;
    }
    .input-wrapper {
      max-width: 800px;
      margin: 0 auto;
      display: flex;
      gap: 12px;
      align-items: flex-end;
    }
    .input-wrapper textarea {
      flex: 1;
      border: 2px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      font-size: 15px;
      font-family: inherit;
      resize: none;
      outline: none;
      transition: border-color 0.2s;
      min-height: 48px;
      max-height: 200px;
    }
    .input-wrapper textarea:focus { border-color: var(--purple); }
    .input-wrapper textarea::placeholder { color: #9ca3af; }

    .send-btn {
      background: linear-gradient(135deg, var(--purple), var(--purple-dark));
      color: white;
      border: none;
      border-radius: 12px;
      padding: 12px 20px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: opacity 0.2s;
    }
    .send-btn:hover { opacity: 0.9; }
    .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Pipeline status bar */
    .pipeline-bar {
      display: none;
      background: #f5f3ff;
      border-top: 2px solid var(--purple);
      padding: 12px 24px;
      font-size: 13px;
      color: var(--purple-dark);
      text-align: center;
      font-weight: 500;
    }
    .pipeline-bar.active { display: block; }
    .pipeline-bar .spinner {
      display: inline-block;
      width: 14px; height: 14px;
      border: 2px solid var(--purple);
      border-top-color: transparent;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      vertical-align: middle;
      margin-right: 8px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Markdown-like formatting */
    .message strong { font-weight: 600; }
    .message em { font-style: italic; }
    .message ul, .message ol { padding-left: 20px; margin: 8px 0; }
    .message li { margin-bottom: 4px; }
    .message p { margin-bottom: 8px; }
    .message p:last-child { margin-bottom: 0; }
    .message h3 { font-size: 16px; margin: 12px 0 8px; }
    .message code {
      background: #f1f5f9;
      padding: 2px 6px;
      border-radius: 4px;
      font-family: 'SF Mono', Monaco, monospace;
      font-size: 13px;
    }

    @media (max-width: 600px) {
      .header { padding: 16px; }
      .chat-container { padding: 16px; }
      .input-area { padding: 12px 16px; }
      .message { max-width: 92%; }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>Webinar Launch Agent</h1>
    <p>Describe your webinar and I'll handle the rest — Zoom, emails, landing page, the works.</p>
  </div>

  <div class="chat-container" id="chat">
    <div class="message agent">
      <p>Hey! I'm your Webinar Launch Agent. Tell me about the webinar you want to run.</p>
      <p>You can be as messy as you want — just brain dump the idea and I'll structure it. For example:</p>
      <p><em>"I want to do a webinar about how AI is changing demand gen, probably mid-April, 45 min, I'll present. Main thing is marketers are buried in manual work."</em></p>
      <p>What are you thinking?</p>
    </div>
  </div>

  <div class="pipeline-bar" id="pipelineBar">
    <span class="spinner"></span>
    <span id="pipelineStatus">Launching pipeline...</span>
  </div>

  <div class="input-area">
    <div class="input-wrapper">
      <textarea id="input" placeholder="Describe your webinar idea..." rows="1"
        onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMessage()}"></textarea>
      <button class="send-btn" id="sendBtn" onclick="sendMessage()">Send</button>
    </div>
  </div>

  <script>
    const chat = document.getElementById('chat');
    const input = document.getElementById('input');
    const sendBtn = document.getElementById('sendBtn');
    const pipelineBar = document.getElementById('pipelineBar');
    const pipelineStatus = document.getElementById('pipelineStatus');

    // Auto-resize textarea
    input.addEventListener('input', function() {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 200) + 'px';
    });

    function addMessage(text, type) {
      const div = document.createElement('div');
      div.className = 'message ' + type;

      if (type === 'agent') {
        // Simple markdown-ish rendering
        let html = text
          .replace(/```json\\n?([\\s\\S]*?)```/g, '<pre>$1</pre>')
          .replace(/```\\n?([\\s\\S]*?)```/g, '<pre>$1</pre>')
          .replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>')
          .replace(/\\*(.+?)\\*/g, '<em>$1</em>')
          .replace(/^- (.+)$/gm, '<li>$1</li>')
          .replace(/(<li>.*<\\/li>)/s, '<ul>$1</ul>')
          .replace(/\\n\\n/g, '</p><p>')
          .replace(/\\n/g, '<br>');
        if (!html.startsWith('<')) html = '<p>' + html;
        if (!html.endsWith('>')) html += '</p>';
        div.innerHTML = html;
      } else {
        div.textContent = text;
      }

      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
      return div;
    }

    function addTyping() {
      const div = document.createElement('div');
      div.className = 'typing';
      div.id = 'typing';
      div.innerHTML = '<span></span><span></span><span></span>';
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }

    function removeTyping() {
      const el = document.getElementById('typing');
      if (el) el.remove();
    }

    function setInputEnabled(enabled) {
      input.disabled = !enabled;
      sendBtn.disabled = !enabled;
      if (enabled) input.focus();
    }

    async function sendMessage() {
      const text = input.value.trim();
      if (!text) return;

      addMessage(text, 'user');
      input.value = '';
      input.style.height = 'auto';
      setInputEnabled(false);
      addTyping();

      try {
        const resp = await fetch('/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message: text})
        });
        const data = await resp.json();
        removeTyping();

        if (data.response) {
          addMessage(data.response, 'agent');
        }

        if (data.launching) {
          // Pipeline is launching
          pipelineBar.classList.add('active');
          pipelineStatus.textContent = 'Launching pipeline...';
          pollPipeline();
        }

      } catch (err) {
        removeTyping();
        addMessage('Connection error. Is the server running?', 'system error');
      }

      setInputEnabled(true);
    }

    async function pollPipeline() {
      const poll = async () => {
        try {
          const resp = await fetch('/pipeline-status');
          const data = await resp.json();

          if (data.status === 'running') {
            pipelineStatus.textContent = data.step || 'Running...';
            if (data.log && data.log.length > 0) {
              // Update or create pipeline log message
              let logEl = document.getElementById('pipeline-log');
              if (!logEl) {
                logEl = document.createElement('div');
                logEl.className = 'message system pipeline';
                logEl.id = 'pipeline-log';
                chat.appendChild(logEl);
              }
              logEl.textContent = data.log.join('\\n');
              chat.scrollTop = chat.scrollHeight;
            }
            setTimeout(poll, 1000);
          } else if (data.status === 'complete') {
            pipelineBar.classList.remove('active');
            // Show final results
            if (data.summary) {
              addMessage(data.summary, 'agent');
            }
            setInputEnabled(true);
          } else if (data.status === 'error') {
            pipelineBar.classList.remove('active');
            addMessage('Pipeline error: ' + (data.error || 'Unknown error'), 'system error');
            setInputEnabled(true);
          } else {
            // Not started yet
            setTimeout(poll, 1000);
          }
        } catch (err) {
          setTimeout(poll, 2000);
        }
      };
      poll();
    }

    // Focus input on load
    input.focus();
  </script>
</body>
</html>"""


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    from modules.brief_agent import chat, extract_approved_brief

    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"response": "I didn't catch that. What's your webinar idea?"})

    # Get or create session
    session_id = "default"  # Simple single-session for demo
    if session_id not in sessions:
        sessions[session_id] = []

    # Add user message to history
    sessions[session_id].append({"role": "user", "content": user_message})

    # Get Claude's response
    response_text = chat(sessions[session_id])

    # Add assistant response to history
    sessions[session_id].append({"role": "assistant", "content": response_text})

    # Check if brief was approved
    brief = extract_approved_brief(response_text)

    if brief:
        # Launch pipeline in background
        pipeline_status[session_id] = {"status": "running", "step": "Starting...", "log": []}

        # Clean the response text to remove the JSON block for display
        display_text = response_text
        if "```json" in display_text:
            display_text = display_text[:display_text.index("```json")].strip()
        if not display_text:
            display_text = "Brief approved! Launching the pipeline now..."

        thread = threading.Thread(target=run_pipeline_async, args=(session_id, brief))
        thread.daemon = True
        thread.start()

        return jsonify({"response": display_text, "launching": True})

    return jsonify({"response": response_text, "launching": False})


@app.route("/pipeline-status")
def pipeline_status_endpoint():
    session_id = "default"
    status = pipeline_status.get(session_id, {"status": "idle"})
    return jsonify(status)


@app.route("/reset", methods=["POST"])
def reset():
    session_id = "default"
    sessions.pop(session_id, None)
    pipeline_status.pop(session_id, None)
    return jsonify({"ok": True})


# ─── Pipeline Execution ─────────────────────────────────────────────────────

def run_pipeline_async(session_id, brief):
    """Run the full pipeline in a background thread, updating status as it goes."""
    log = []

    def update(step, msg):
        log.append(msg)
        pipeline_status[session_id] = {"status": "running", "step": step, "log": log[-20:]}

    try:
        import config  # noqa — validates env vars

        # Step 1: Zoom + Calendar
        update("Creating Zoom meeting...", "→ Creating Zoom meeting...")
        from modules.event_creator import create_webinar_event
        event = create_webinar_event(
            title=brief["title"],
            description=brief.get("description", ""),
            date_str=brief["date"],
            time_str=brief["time"],
            duration_minutes=brief.get("duration_minutes", 45),
        )

        zoom_url = ""
        if event:
            zoom_url = event.get("zoom_join_url", "")
            update("Event created", f"✓ Zoom meeting created: {zoom_url}")
            update("Event created", f"✓ Calendar event: {event.get('event_link', '')}")
            brief["zoom_join_url"] = zoom_url
            brief["event_link"] = event.get("event_link", "")
            brief["event_id"] = event.get("event_id", "")
        else:
            update("Event failed", "✗ Event creation failed — continuing without it")

        # Step 2: Landing page
        update("Creating landing page...", "→ Creating HubSpot form + landing page...")
        from modules.landing_page import create_hubspot_landing_page
        landing = create_hubspot_landing_page(brief, zoom_url)

        landing_url = ""
        if landing:
            landing_url = landing.get("landing_page_url", "")
            brief["landing_page_url"] = landing_url
            update("Landing page created", f"✓ Landing page generated")
            if landing.get("hubspot_form_id"):
                update("Landing page created", f"✓ HubSpot form: {landing['hubspot_form_id']}")
        else:
            update("Landing page failed", "✗ Landing page creation failed")

        # Step 3: Contacts
        update("Loading contacts...", "→ Loading contacts from Google Sheets...")
        from modules.contact_manager import get_contacts_by_segment, validate_contacts

        customers_raw = get_contacts_by_segment("customer")
        prospects_raw = get_contacts_by_segment("prospect")
        customers, _ = validate_contacts(customers_raw)
        prospects, _ = validate_contacts(prospects_raw)

        update("Contacts loaded", f"✓ Customers: {len(customers)} | Prospects: {len(prospects)}")

        # Step 4: Generate emails
        update("Generating emails...", "→ Generating email content via Claude...")
        from modules.content_generator import generate_email_content

        emails = {}
        if customers:
            content = generate_email_content("invite", "customer", brief)
            if content:
                emails["invite_customer"] = content
                update("Emails generated", f'✓ Customer invite: "{content["subject"]}"')

        if prospects:
            content = generate_email_content("invite", "prospect", brief)
            if content:
                emails["invite_prospect"] = content
                update("Emails generated", f'✓ Prospect invite: "{content["subject"]}"')

        # Step 5: Send emails
        # Registration link = landing page (form) — email CTAs point here
        # Webinar link = Zoom join URL — fallback if no landing page
        registration_link = landing_url if landing_url and not landing_url.startswith("file://") else ""
        webinar_link = zoom_url or brief.get("event_link", "")
        extra_vars = {
            "webinar_link": webinar_link,
            "registration_link": registration_link,
        }

        total_sent = 0
        total_failed = 0

        if "invite_customer" in emails and customers:
            update("Sending customer emails...", f"→ Sending to {len(customers)} customers...")
            from modules.email_sender import send_batch
            result = send_batch(customers, "invite_customer.html", emails["invite_customer"],
                              extra_vars=extra_vars)
            total_sent += result["sent"]
            total_failed += result["failed"]
            update("Sent", f"✓ Customer emails: {result['sent']} sent, {result['failed']} failed")

            # Log
            from modules.tracker import log_campaign, log_sends_batch
            log_campaign(brief["title"], "invite", "customer", len(customers),
                        result["sent"], result["failed"], zoom_url=webinar_link)
            log_sends_batch(brief["title"], result["results"])

        if "invite_prospect" in emails and prospects:
            update("Sending prospect emails...", f"→ Sending to {len(prospects)} prospects...")
            from modules.email_sender import send_batch
            result = send_batch(prospects, "invite_prospect.html", emails["invite_prospect"],
                              extra_vars=extra_vars)
            total_sent += result["sent"]
            total_failed += result["failed"]
            update("Sent", f"✓ Prospect emails: {result['sent']} sent, {result['failed']} failed")

            from modules.tracker import log_campaign, log_sends_batch
            log_campaign(brief["title"], "invite", "prospect", len(prospects),
                        result["sent"], result["failed"], zoom_url=webinar_link)
            log_sends_batch(brief["title"], result["results"])

        # Step 6: Schedule follow-ups
        update("Scheduling follow-ups...", "→ Scheduling follow-up emails...")
        from modules.follow_up import schedule_reminder, schedule_followup
        import os

        # Save brief to temp file for follow-ups
        brief_path = os.path.join(os.path.dirname(__file__), "output", "last_brief.json")
        os.makedirs(os.path.dirname(brief_path), exist_ok=True)
        with open(brief_path, "w") as f:
            json.dump(brief, f, indent=2)

        schedule_reminder(brief["title"], brief["date"], brief_path)
        schedule_followup(brief["title"], brief["date"], brief_path)
        update("Follow-ups scheduled", "✓ Reminder + follow-up emails scheduled")

        # Done!
        update("Complete", "")
        update("Complete", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        update("Complete", f"✓ LAUNCH COMPLETE")
        update("Complete", f"  Emails sent: {total_sent} | Failed: {total_failed}")

        summary = f"""**Launch complete!** Here's your summary:

- **Zoom meeting**: {zoom_url or 'N/A'}
- **Calendar event**: {brief.get('event_link', 'N/A')}
- **Landing page**: Generated in output/ folder
- **Emails sent**: {total_sent} total ({len(customers)} customers, {len(prospects)} prospects)
- **Failed**: {total_failed}
- **Follow-ups**: Reminder scheduled 3 days before, follow-up 1 day after

Everything is logged in your Google Sheet. Run `python3 main.py status` to see the full campaign history.

Want to launch another webinar? Just describe it!"""

        pipeline_status[session_id] = {"status": "complete", "summary": summary, "log": log}

    except Exception as e:
        update("Error", f"✗ Pipeline error: {str(e)}")
        pipeline_status[session_id] = {
            "status": "error",
            "error": str(e),
            "log": log,
        }


if __name__ == "__main__":
    # Import config to validate env vars early
    import config  # noqa
    print("\n" + "=" * 50)
    print("  WEBINAR LAUNCH AGENT")
    print("  Open http://localhost:5001 in your browser")
    print("=" * 50 + "\n")
    app.run(host="0.0.0.0", port=5001, debug=False)
