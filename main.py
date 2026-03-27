#!/usr/bin/env python3
"""
Webinar Launch Automation Engine
CLI entry point for managing webinar campaigns.
"""

import argparse
import json
import sys


def approval_loop(email_key, content, sample_contact, generate_fn, template_type, segment, webinar_info):
    """
    Human-in-the-loop approval for generated email content.
    Returns approved content dict, or None if skipped.
    """
    from modules.content_generator import preview_email

    while True:
        print(f"\n  --- {email_key.upper()} ---")
        preview_email(content, sample_contact)

        print("\n  Actions:")
        print("    [a] Approve and continue")
        print("    [e] Edit subject line")
        print("    [r] Regenerate with feedback")
        print("    [s] Skip this segment")
        print("    [q] Quit pipeline")

        choice = input("\n  Your choice: ").strip().lower()

        if choice == "a":
            return content
        elif choice == "e":
            new_subject = input("  New subject line: ").strip()
            if new_subject:
                content["subject"] = new_subject
                print(f"  Subject updated to: \"{new_subject}\"")
        elif choice == "r":
            feedback = input("  Feedback for Claude (e.g. 'make it shorter', 'more urgency'): ").strip()
            if feedback:
                print(f"  Regenerating with feedback: \"{feedback}\"...")
                # Add feedback to webinar_info temporarily
                info_with_feedback = dict(webinar_info)
                info_with_feedback["_feedback"] = feedback
                new_content = generate_fn(template_type, segment, info_with_feedback)
                if new_content:
                    content = new_content
                else:
                    print("  [ERROR] Regeneration failed. Keeping previous version.")
        elif choice == "s":
            print(f"  Skipping {email_key}.")
            return None
        elif choice == "q":
            print("\n  Pipeline stopped by user.")
            sys.exit(0)
        else:
            print("  Invalid choice. Try again.")


def run_launch(brief_path, dry_run=False):
    """Run the full webinar launch pipeline."""
    from modules.contact_manager import get_contacts_by_segment, validate_contacts
    from modules.event_creator import create_webinar_event
    from modules.landing_page import create_hubspot_landing_page
    from modules.content_generator import generate_email_content
    from modules.email_sender import send_batch
    from modules.tracker import log_campaign, log_sends_batch, get_today_send_count

    # Step 1: Read brief
    print("\n" + "=" * 60)
    print("  WEBINAR LAUNCH AUTOMATION ENGINE")
    print("=" * 60)

    try:
        with open(brief_path) as f:
            brief = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"\n[ERROR] Could not read brief: {e}")
        return

    campaign_name = brief["title"]
    print(f"\n  Campaign: {campaign_name}")
    print(f"  Date:     {brief['date']} at {brief['time']}")
    if dry_run:
        print("  Mode:     DRY RUN (no emails will be sent)")

    # Step 2: Create calendar event + Zoom meeting
    print(f"\n{'─' * 60}")
    print("  STEP 1: Creating event")
    print(f"{'─' * 60}")

    event = create_webinar_event(
        title=brief["title"],
        description=brief["description"],
        date_str=brief["date"],
        time_str=brief["time"],
        duration_minutes=brief["duration_minutes"],
    )

    # Add event info to brief for email generation
    if event:
        brief["zoom_join_url"] = event.get("zoom_join_url", "")
        brief["event_link"] = event.get("event_link", "")
        brief["event_id"] = event.get("event_id", "")

    # Step 2b: Create landing page
    print(f"\n{'─' * 60}")
    print("  STEP 1b: Creating registration landing page")
    print(f"{'─' * 60}")

    zoom_url = brief.get("zoom_join_url", "")
    landing = create_hubspot_landing_page(brief, zoom_url)

    if landing:
        brief["landing_page_url"] = landing.get("landing_page_url", "")
        brief["landing_page_source"] = landing.get("source", "")
        if landing.get("hubspot_form_id"):
            brief["hubspot_form_id"] = landing["hubspot_form_id"]

    # Step 3: Pull contacts
    print(f"\n{'─' * 60}")
    print("  STEP 2: Loading contacts")
    print(f"{'─' * 60}")

    customers_raw = get_contacts_by_segment("customer")
    prospects_raw = get_contacts_by_segment("prospect")

    customers, invalid_c = validate_contacts(customers_raw)
    prospects, invalid_p = validate_contacts(prospects_raw)

    print(f"\n  Customers: {len(customers)} valid, {len(invalid_c)} invalid")
    print(f"  Prospects: {len(prospects)} valid, {len(invalid_p)} invalid")

    if not customers and not prospects:
        print("\n[ERROR] No valid contacts found. Add contacts to your Google Sheet and try again.")
        return

    # Step 4: Generate email content
    print(f"\n{'─' * 60}")
    print("  STEP 3: Generating email content via Claude")
    print(f"{'─' * 60}")

    sample_customer = customers[0] if customers else {"first_name": "Customer", "company": "Your Company"}
    sample_prospect = prospects[0] if prospects else {"first_name": "Prospect", "company": "Their Company"}

    emails = {}

    if customers:
        print("\n  Generating customer invite...")
        content = generate_email_content("invite", "customer", brief)
        if content:
            emails["invite_customer"] = content

    if prospects:
        print("\n  Generating prospect invite...")
        content = generate_email_content("invite", "prospect", brief)
        if content:
            emails["invite_prospect"] = content

    if not emails:
        print("\n[ERROR] No emails generated. Check your Anthropic API key.")
        return

    # Step 5: Human approval loop
    print(f"\n{'─' * 60}")
    print("  STEP 4: Review & approve emails")
    print(f"{'─' * 60}")
    print("  Review each email below. You can approve, edit, regenerate, or skip.")

    approved = {}

    if "invite_customer" in emails:
        result = approval_loop(
            "invite_customer", emails["invite_customer"], sample_customer,
            generate_email_content, "invite", "customer", brief
        )
        if result:
            approved["invite_customer"] = result

    if "invite_prospect" in emails:
        result = approval_loop(
            "invite_prospect", emails["invite_prospect"], sample_prospect,
            generate_email_content, "invite", "prospect", brief
        )
        if result:
            approved["invite_prospect"] = result

    if not approved:
        print("\n  No emails approved. Pipeline complete (nothing sent).")
        return

    # Step 6: Send emails
    print(f"\n{'─' * 60}")
    print("  STEP 5: Sending emails" + (" (DRY RUN)" if dry_run else ""))
    print(f"{'─' * 60}")

    send_count = get_today_send_count() if not dry_run else 0
    if not dry_run:
        print(f"\n  Today's sends so far: {send_count}/300")

    # Registration link = landing page (with form) — this is where email CTAs should go
    # Webinar link = Zoom join URL — this is the actual meeting link
    registration_link = brief.get("landing_page_url") or ""
    webinar_link = (
        brief.get("zoom_registration_url")
        or brief.get("zoom_join_url")
        or brief.get("event_link")
        or ""
    )
    extra_vars = {
        "webinar_link": webinar_link,
        "registration_link": registration_link,
    }

    total_sent = 0
    total_failed = 0

    if "invite_customer" in approved and customers:
        print(f"\n  Sending customer invites ({len(customers)} contacts)...")
        result = send_batch(
            customers, "invite_customer.html", approved["invite_customer"],
            extra_vars=extra_vars, dry_run=dry_run, send_count_today=send_count,
        )
        total_sent += result["sent"]
        total_failed += result["failed"]

        # Log
        if not dry_run:
            log_campaign(campaign_name, "invite", "customer", len(customers), result["sent"], result["failed"],
                         event_id=brief.get("event_id", ""), zoom_url=webinar_link)
            log_sends_batch(campaign_name, result["results"])
            send_count += result["sent"]

    if "invite_prospect" in approved and prospects:
        print(f"\n  Sending prospect invites ({len(prospects)} contacts)...")
        result = send_batch(
            prospects, "invite_prospect.html", approved["invite_prospect"],
            extra_vars=extra_vars, dry_run=dry_run, send_count_today=send_count,
        )
        total_sent += result["sent"]
        total_failed += result["failed"]

        # Log
        if not dry_run:
            log_campaign(campaign_name, "invite", "prospect", len(prospects), result["sent"], result["failed"],
                         event_id=brief.get("event_id", ""), zoom_url=webinar_link)
            log_sends_batch(campaign_name, result["results"])

    # Step 7: Schedule follow-ups
    print(f"\n{'─' * 60}")
    print("  STEP 6: Scheduling follow-ups")
    print(f"{'─' * 60}")

    if not dry_run:
        from modules.follow_up import schedule_reminder, schedule_followup
        import os
        abs_brief_path = os.path.abspath(brief_path)
        schedule_reminder(campaign_name, brief["date"], abs_brief_path)
        schedule_followup(campaign_name, brief["date"], abs_brief_path)
    else:
        from datetime import datetime as dt, timedelta
        event_date = dt.strptime(brief["date"], "%Y-%m-%d")
        reminder_date = (event_date - timedelta(days=3)).strftime("%Y-%m-%d")
        followup_date = (event_date + timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"  [DRY RUN] Would schedule reminders for {reminder_date}")
        print(f"  [DRY RUN] Would schedule follow-ups for {followup_date}")

    # Step 8: Summary
    print(f"\n{'─' * 60}")
    print("  LAUNCH SUMMARY")
    print(f"{'─' * 60}")
    print(f"  Campaign:    {campaign_name}")
    print(f"  Event:       {brief.get('event_link', 'N/A')}")
    print(f"  Zoom:        {brief.get('zoom_join_url', 'N/A')}")
    if brief.get("landing_page_url"):
        print(f"  Landing:     {brief['landing_page_url']}")
    print(f"  CTA link:    {webinar_link or 'N/A'}")
    print(f"  Emails sent: {total_sent}")
    print(f"  Failed:      {total_failed}")
    if dry_run:
        print(f"  Mode:        DRY RUN (no emails actually sent)")
    print(f"\n  Next steps:")
    print(f"    - Reminder emails fire 3 days before event")
    print(f"    - Post-event follow-ups fire 1 day after")
    print(f"    - Run: python main.py followup --check")
    print(f"\n{'=' * 60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Webinar Launch Automation Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  contacts    List and segment contacts from Google Sheets
  event       Create a webinar event on Google Calendar
  generate    Generate email content via Claude AI
  send        Send emails via Brevo
  status      View campaign log and send history
  followup    Check and execute scheduled follow-ups
  launch      Run the full webinar launch pipeline
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # contacts
    contacts_parser = subparsers.add_parser("contacts", help="Manage contacts")
    contacts_parser.add_argument("--list", action="store_true", help="List all contacts")
    contacts_parser.add_argument("--segment", type=str, help="Filter by segment (customer/prospect)")

    # event
    event_parser = subparsers.add_parser("event", help="Create webinar event")
    event_parser.add_argument("--create", action="store_true", help="Create a new event")
    event_parser.add_argument("--brief", type=str, help="Path to webinar brief JSON")

    # generate
    generate_parser = subparsers.add_parser("generate", help="Generate email content")
    generate_parser.add_argument("--brief", type=str, required=True, help="Path to webinar brief JSON")
    generate_parser.add_argument("--type", type=str, default="invite", choices=["invite", "reminder", "followup"], help="Email type to generate")

    # send
    send_parser = subparsers.add_parser("send", help="Send emails")
    send_parser.add_argument("--brief", type=str, help="Path to webinar brief JSON")
    send_parser.add_argument("--type", type=str, default="invite", choices=["invite", "reminder", "followup"])
    send_parser.add_argument("--dry-run", action="store_true", help="Render emails without sending")

    # status
    subparsers.add_parser("status", help="View campaign history")

    # followup
    followup_parser = subparsers.add_parser("followup", help="Manage follow-ups")
    followup_parser.add_argument("--check", action="store_true", help="Check and execute due follow-ups")

    # landing
    landing_parser = subparsers.add_parser("landing", help="Create webinar landing page")
    landing_parser.add_argument("--brief", type=str, required=True, help="Path to webinar brief JSON")

    # launch
    launch_parser = subparsers.add_parser("launch", help="Run full webinar launch pipeline")
    launch_parser.add_argument("--brief", type=str, required=True, help="Path to webinar brief JSON")
    launch_parser.add_argument("--dry-run", action="store_true", help="Run pipeline without sending emails")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Import config (validates env vars on import)
    import config  # noqa: F401

    if args.command == "contacts":
        from modules.contact_manager import handle_contacts_command
        handle_contacts_command(args)
    elif args.command == "event":
        from modules.event_creator import handle_event_command
        handle_event_command(args)
    elif args.command == "generate":
        from modules.content_generator import handle_generate_command
        handle_generate_command(args)
    elif args.command == "landing":
        from modules.landing_page import handle_landing_page_command
        handle_landing_page_command(args)
    elif args.command == "send":
        from modules.email_sender import handle_send_command
        handle_send_command(args)
    elif args.command == "status":
        from modules.tracker import handle_status_command
        handle_status_command()
    elif args.command == "followup":
        from modules.follow_up import handle_followup_command
        handle_followup_command(args)
    elif args.command == "launch":
        run_launch(args.brief, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
