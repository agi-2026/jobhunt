#!/usr/bin/env python3
"""Create draft email replies or new emails via Microsoft Graph API.

Cross-platform (macOS/Windows/Linux). Uses only Python stdlib.
NEVER auto-sends — only creates drafts for review.

Usage:
    python3 outlook-draft.py --reply-to <message_id> --body "Reply text here"
    python3 outlook-draft.py --new --to "email@example.com" --subject "Subject" --body "Body"
    python3 outlook-draft.py --reply-to <message_id> --body-file /path/to/body.txt
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_SCRIPTS = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", "scripts"))
sys.path.insert(0, WORKSPACE_SCRIPTS)

from outlook_auth import graph_request


def create_reply_draft(message_id, body_text, body_html=None):
    """Create a draft reply to an existing message.

    Uses Graph API: POST /me/messages/{id}/createReply
    Then PATCH the draft with the reply body.
    """
    # Step 1: Create reply draft (empty body, copies thread)
    draft = graph_request(f"/me/messages/{message_id}/createReply", method="POST", body={})
    draft_id = draft.get("id")
    if not draft_id:
        print("ERROR: Failed to create reply draft", file=sys.stderr)
        sys.exit(1)

    # Step 2: Update draft body
    content_type = "html" if body_html else "text"
    content = body_html or body_text

    update_body = {
        "body": {
            "contentType": content_type,
            "content": content,
        }
    }
    updated = graph_request(f"/me/messages/{draft_id}", method="PATCH", body=update_body)

    # Output
    to_recipients = updated.get("toRecipients", [])
    to_str = ", ".join(
        r.get("emailAddress", {}).get("address", "")
        for r in to_recipients
    )
    subject = updated.get("subject", "")

    print(f"DRAFT_CREATED: id={draft_id}")
    print(f"  To: {to_str}")
    print(f"  Subject: {subject}")
    print(f"  Body length: {len(body_text)} chars")
    print(f"  Status: Draft saved (NOT sent)")
    return draft_id


def create_new_draft(to_email, subject, body_text, cc_email=None, body_html=None):
    """Create a new draft email (not a reply).

    Uses Graph API: POST /me/messages
    """
    content_type = "html" if body_html else "text"
    content = body_html or body_text

    message = {
        "subject": subject,
        "body": {
            "contentType": content_type,
            "content": content,
        },
        "toRecipients": [
            {"emailAddress": {"address": to_email}}
        ],
        "isDraft": True,
    }
    if cc_email:
        message["ccRecipients"] = [
            {"emailAddress": {"address": cc_email}}
        ]

    draft = graph_request("/me/messages", method="POST", body=message)
    draft_id = draft.get("id")
    if not draft_id:
        print("ERROR: Failed to create draft", file=sys.stderr)
        sys.exit(1)

    print(f"DRAFT_CREATED: id={draft_id}")
    print(f"  To: {to_email}")
    if cc_email:
        print(f"  CC: {cc_email}")
    print(f"  Subject: {subject}")
    print(f"  Body length: {len(body_text)} chars")
    print(f"  Status: Draft saved (NOT sent)")
    return draft_id


def main():
    parser = argparse.ArgumentParser(description="Outlook draft creator")
    parser.add_argument("--reply-to", help="Message ID to reply to")
    parser.add_argument("--new", action="store_true", help="Create new email (not a reply)")
    parser.add_argument("--to", help="Recipient email (for --new)")
    parser.add_argument("--cc", help="CC recipient (for --new)")
    parser.add_argument("--subject", help="Subject (for --new)")
    parser.add_argument("--body", help="Email body text")
    parser.add_argument("--body-file", help="Read body from file path")
    parser.add_argument("--html", action="store_true", help="Treat body as HTML")
    args = parser.parse_args()

    # Get body text
    if args.body_file:
        with open(args.body_file) as f:
            body_text = f.read()
    elif args.body:
        body_text = args.body
    else:
        print("ERROR: --body or --body-file required", file=sys.stderr)
        sys.exit(1)

    body_html = body_text if args.html else None

    if args.reply_to:
        create_reply_draft(args.reply_to, body_text, body_html)
    elif args.new:
        if not args.to or not args.subject:
            print("ERROR: --to and --subject required for --new", file=sys.stderr)
            sys.exit(1)
        create_new_draft(args.to, args.subject, body_text, args.cc, body_html)
    else:
        print("ERROR: --reply-to or --new required", file=sys.stderr)
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
