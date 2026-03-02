#!/usr/bin/env python3
"""Read individual emails or threads from Outlook via Microsoft Graph API.

Cross-platform (macOS/Windows/Linux). Uses only Python stdlib.

Usage:
    python3 outlook-read.py --id <message_id>
    python3 outlook-read.py --thread <conversation_id>
    python3 outlook-read.py --search "from:recruiter@company.com subject:interview"
    python3 outlook-read.py --latest 5
    python3 outlook-read.py --json --id <message_id>
"""
import argparse
import html.parser
import json
import os
import re
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_SCRIPTS = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", "scripts"))
sys.path.insert(0, WORKSPACE_SCRIPTS)

from outlook_auth import graph_request


class HTMLStripper(html.parser.HTMLParser):
    """Minimal HTML to text converter."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True
        elif tag == "br":
            self.parts.append("\n")
        elif tag in ("p", "div", "tr", "li"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def get_text(self):
        return re.sub(r"\n{3,}", "\n\n", "".join(self.parts).strip())


def strip_html(html_content):
    if not html_content:
        return ""
    stripper = HTMLStripper()
    try:
        stripper.feed(html_content)
        return stripper.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html_content)


def _format_recipients(field):
    """Format a list of recipients."""
    if not field:
        return ""
    parts = []
    for r in field:
        email_data = r.get("emailAddress", {})
        name = email_data.get("name", "")
        addr = email_data.get("address", "")
        if name and name != addr:
            parts.append(f"{name} <{addr}>")
        else:
            parts.append(addr)
    return ", ".join(parts)


def format_message(msg, include_body=True, body_max_chars=8000):
    """Format a single message for display."""
    sender = msg.get("from", {}).get("emailAddress", {})
    sender_str = f"{sender.get('name', '')} <{sender.get('address', '')}>"
    to_str = _format_recipients(msg.get("toRecipients", []))
    cc_str = _format_recipients(msg.get("ccRecipients", []))
    received = msg.get("receivedDateTime", "")
    subject = msg.get("subject", "(no subject)")
    read_status = "Read" if msg.get("isRead", True) else "UNREAD"
    importance = msg.get("importance", "normal")
    has_attach = msg.get("hasAttachments", False)

    lines = [
        f"## {subject}",
        f"**From:** {sender_str}",
        f"**To:** {to_str}",
    ]
    if cc_str:
        lines.append(f"**CC:** {cc_str}")
    lines.extend([
        f"**Date:** {received}",
        f"**Status:** {read_status} | Importance: {importance}"
        + (f" | Attachments: Yes" if has_attach else ""),
        f"**Message ID:** {msg.get('id', '')}",
        f"**Conversation ID:** {msg.get('conversationId', '')}",
    ])

    if include_body:
        body = msg.get("body", {})
        content_type = body.get("contentType", "text")
        content = body.get("content", "")
        if content_type == "html":
            text = strip_html(content)
        else:
            text = content
        if len(text) > body_max_chars:
            text = text[:body_max_chars] + "\n\n... (truncated)"
        lines.extend(["", "---", "", text])

    return "\n".join(lines)


def read_by_id(message_id, as_json=False):
    """Read a single message by ID."""
    params = {
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "isRead,importance,body,conversationId,hasAttachments,flag",
    }
    msg = graph_request(f"/me/messages/{message_id}", params=params)

    if as_json:
        print(json.dumps(msg, indent=2))
    else:
        print(format_message(msg))


def read_thread(conversation_id, as_json=False):
    """Read all messages in a conversation thread."""
    params = {
        "$filter": f"conversationId eq '{conversation_id}'",
        "$orderby": "receivedDateTime asc",
        "$top": "25",
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "isRead,importance,body,conversationId,hasAttachments",
    }
    result = graph_request("/me/messages", params=params)
    messages = result.get("value", [])

    if not messages:
        print(f"No messages found for conversation: {conversation_id}")
        return

    if as_json:
        print(json.dumps(messages, indent=2))
    else:
        subject = messages[0].get("subject", "(no subject)")
        print(f"# Thread: {subject}")
        print(f"Messages: {len(messages)}")
        print()
        for i, msg in enumerate(messages, 1):
            print(f"--- Message {i}/{len(messages)} ---\n")
            print(format_message(msg, body_max_chars=4000))
            print()


def search_messages(query, top=10, as_json=False):
    """Search messages using Microsoft Graph search syntax.

    Supports: from:, subject:, body: prefixes and free text.
    """
    params = {
        "$search": f'"{query}"',
        "$top": str(top),
        "$select": "id,subject,from,toRecipients,receivedDateTime,isRead,importance,"
                   "bodyPreview,conversationId,hasAttachments",
    }
    result = graph_request("/me/messages", params=params)
    messages = result.get("value", [])

    if as_json:
        print(json.dumps(messages, indent=2))
    else:
        print(f"Search: \"{query}\" — {len(messages)} results")
        print()
        for msg in messages:
            sender = msg.get("from", {}).get("emailAddress", {})
            read = "" if msg.get("isRead", True) else " [UNREAD]"
            preview = (msg.get("bodyPreview") or "")[:100].replace("\n", " ")
            print(f"  {msg.get('receivedDateTime', '')[:16]} | "
                  f"{sender.get('name', sender.get('address', ''))}"
                  f" — \"{msg.get('subject', '')}\"{read}")
            print(f"    ID: {msg.get('id', '')}")
            print(f"    Preview: {preview}")
            print()


def read_latest(count=5, as_json=False):
    """Read the latest N messages from inbox."""
    params = {
        "$orderby": "receivedDateTime desc",
        "$top": str(count),
        "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,"
                   "isRead,importance,body,conversationId,hasAttachments,flag",
    }
    result = graph_request("/me/messages", params=params)
    messages = result.get("value", [])

    if as_json:
        print(json.dumps(messages, indent=2))
    else:
        print(f"Latest {len(messages)} messages:")
        print()
        for i, msg in enumerate(messages, 1):
            print(f"--- Message {i} ---\n")
            print(format_message(msg, body_max_chars=2000))
            print()


def main():
    parser = argparse.ArgumentParser(description="Outlook email reader")
    parser.add_argument("--id", help="Read message by ID")
    parser.add_argument("--thread", help="Read conversation thread by conversation ID")
    parser.add_argument("--search", help="Search messages (supports from:, subject: prefixes)")
    parser.add_argument("--latest", type=int, help="Read latest N messages")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.id:
        read_by_id(args.id, as_json=args.json)
    elif args.thread:
        read_thread(args.thread, as_json=args.json)
    elif args.search:
        search_messages(args.search, as_json=args.json)
    elif args.latest:
        read_latest(args.latest, as_json=args.json)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
