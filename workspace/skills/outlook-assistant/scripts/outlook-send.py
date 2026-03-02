#!/usr/bin/env python3
"""Send an existing draft email via Microsoft Graph API.

Safety: Requires explicit --confirm flag to actually send.
Without --confirm, only previews the draft.

Usage:
    python3 outlook-send.py --draft-id <id>                  # Preview only
    python3 outlook-send.py --draft-id <id> --confirm        # Actually send
"""
import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_SCRIPTS = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", "scripts"))
sys.path.insert(0, WORKSPACE_SCRIPTS)

from outlook_auth import graph_request


def preview_draft(draft_id):
    """Preview a draft without sending."""
    params = {
        "$select": "id,subject,from,toRecipients,ccRecipients,body,isDraft",
    }
    msg = graph_request(f"/me/messages/{draft_id}", params=params)

    if not msg.get("isDraft", False):
        print("WARNING: This message is NOT a draft. It may have already been sent.",
              file=sys.stderr)

    to = ", ".join(
        r.get("emailAddress", {}).get("address", "")
        for r in msg.get("toRecipients", [])
    )
    cc = ", ".join(
        r.get("emailAddress", {}).get("address", "")
        for r in msg.get("ccRecipients", [])
    )
    subject = msg.get("subject", "")
    body = msg.get("body", {}).get("content", "")
    body_preview = body[:500] + ("..." if len(body) > 500 else "")

    print(f"PREVIEW_ONLY (not sent)")
    print(f"  Draft ID: {draft_id}")
    print(f"  To: {to}")
    if cc:
        print(f"  CC: {cc}")
    print(f"  Subject: {subject}")
    print(f"  Body preview: {body_preview}")
    print()
    print("To send this draft, run with --confirm flag.")
    return msg


def send_draft(draft_id):
    """Send a draft email."""
    # First preview
    msg = preview_draft(draft_id)

    print()
    print("Sending...")

    # POST /me/messages/{id}/send (no body needed)
    graph_request(f"/me/messages/{draft_id}/send", method="POST", body={})

    to = ", ".join(
        r.get("emailAddress", {}).get("address", "")
        for r in msg.get("toRecipients", [])
    )
    print(f"SENT: To={to} | Subject=\"{msg.get('subject', '')}\"")


def main():
    parser = argparse.ArgumentParser(description="Outlook draft sender (safe)")
    parser.add_argument("--draft-id", required=True, help="Draft message ID to send")
    parser.add_argument("--confirm", action="store_true",
                        help="Actually send the draft (without this, only previews)")
    args = parser.parse_args()

    if args.confirm:
        send_draft(args.draft_id)
    else:
        preview_draft(args.draft_id)


if __name__ == "__main__":
    main()
