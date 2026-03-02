#!/usr/bin/env python3
"""Inbox scanner with heuristic scoring for Outlook Assistant.

Cross-platform (macOS/Windows/Linux). Uses Microsoft Graph API.

Usage:
    python3 outlook-scan.py                    # Scan last 7 days
    python3 outlook-scan.py --days 3           # Last 3 days
    python3 outlook-scan.py --unread-only      # Only unread
    python3 outlook-scan.py --json             # JSON output for agent parsing
    python3 outlook-scan.py --urgent-only      # Score >= 150 only
    python3 outlook-scan.py --top 10           # Limit to top N results
"""
import argparse
import html.parser
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_SCRIPTS = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", "scripts"))
sys.path.insert(0, WORKSPACE_SCRIPTS)

from outlook_auth import graph_request

CONFIG_DIR = os.path.join(SCRIPT_DIR, "..", "config")
HEURISTICS_PATH = os.path.join(CONFIG_DIR, "heuristics.json")

# Path to job-tracker.md for applied company matching
WORKSPACE_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
JOB_TRACKER_PATH = os.path.join(WORKSPACE_DIR, "job-tracker.md")


class HTMLStripper(html.parser.HTMLParser):
    """Minimal HTML to text converter using stdlib."""
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
        return "".join(self.parts).strip()


def strip_html(html_content):
    """Convert HTML to plain text."""
    if not html_content:
        return ""
    stripper = HTMLStripper()
    try:
        stripper.feed(html_content)
        return stripper.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", html_content)


def load_heuristics():
    """Load scoring heuristics from config."""
    if not os.path.isfile(HEURISTICS_PATH):
        return {"priority_rules": [], "skip_senders": [], "skip_subject_patterns": [],
                "known_recruiter_domains": []}
    with open(HEURISTICS_PATH) as f:
        return json.load(f)


def load_applied_companies():
    """Extract company names from job-tracker.md for cross-referencing."""
    companies = set()
    if not os.path.isfile(JOB_TRACKER_PATH):
        return companies
    try:
        with open(JOB_TRACKER_PATH) as f:
            for line in f:
                # Match "### Company - Title" or "| Company | Title |" patterns
                m = re.match(r"^###\s+(.+?)\s*[-–—]\s+", line)
                if m:
                    companies.add(m.group(1).strip().lower())
                m2 = re.match(r"^\|\s*(.+?)\s*\|", line)
                if m2 and m2.group(1).strip().lower() not in ("company", "---", ""):
                    companies.add(m2.group(1).strip().lower())
    except Exception:
        pass
    return companies


def _time_ago(dt_str):
    """Convert ISO datetime string to human-readable 'X ago'."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        if delta.days > 0:
            return f"{delta.days}d ago"
        hours = delta.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = delta.seconds // 60
        return f"{minutes}m ago"
    except Exception:
        return dt_str


def should_skip_sender(sender_email, skip_senders):
    """Check if sender should be skipped."""
    email_lower = sender_email.lower()
    for skip in skip_senders:
        if skip in email_lower:
            return True
    return False


def should_skip_subject(subject, skip_patterns):
    """Check if subject matches skip patterns."""
    subject_lower = subject.lower()
    for pattern in skip_patterns:
        try:
            if re.search(pattern, subject, re.IGNORECASE):
                return True
        except re.error:
            if pattern.lower() in subject_lower:
                return True
    return False


def score_email(msg, heuristics, applied_companies):
    """Score a single email based on heuristics. Returns (score, tags)."""
    score = 0
    tags = []
    subject = (msg.get("subject") or "").lower()
    sender_email = msg.get("from", {}).get("emailAddress", {}).get("address", "").lower()
    sender_domain = sender_email.split("@")[-1] if "@" in sender_email else ""
    body_preview = (msg.get("bodyPreview") or "").lower()

    for rule in heuristics.get("priority_rules", []):
        rule_type = rule.get("type", "")
        boost = rule.get("boost", 0)
        tag = rule.get("tag", "")

        if rule_type == "keyword_subject":
            for kw in rule.get("keywords", []):
                if kw.lower() in subject or kw.lower() in body_preview:
                    score += boost
                    if tag and tag not in tags:
                        tags.append(tag)
                    break

        elif rule_type == "domain_from":
            for domain in rule.get("domains", []):
                if domain.lower() in sender_domain:
                    score += boost
                    if tag and tag not in tags:
                        tags.append(tag)
                    break

        elif rule_type == "applied_company_match":
            sender_name = msg.get("from", {}).get("emailAddress", {}).get("name", "").lower()
            for company in applied_companies:
                if company in sender_domain or company in sender_name or company in subject:
                    score += boost
                    if tag and tag not in tags:
                        tags.append(tag)
                    break

        elif rule_type == "unread":
            if not msg.get("isRead", True):
                score += boost

        elif rule_type == "flagged":
            flag = msg.get("flag", {}).get("flagStatus", "notFlagged")
            if flag == "flagged":
                score += boost
                if tag and tag not in tags:
                    tags.append(tag)

        elif rule_type == "importance_high":
            if msg.get("importance", "normal") == "high":
                score += boost
                if tag and tag not in tags:
                    tags.append(tag)

    # Boost for known recruiter domains
    for domain in heuristics.get("known_recruiter_domains", []):
        if domain.lower() in sender_domain:
            if "RECRUITER" not in tags:
                score += 20
                tags.append("KNOWN-CO")
            break

    return score, tags


def scan_inbox(days=7, unread_only=False, max_results=50):
    """Scan inbox and return scored results."""
    heuristics = load_heuristics()
    applied_companies = load_applied_companies()

    # Build filter
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    filter_parts = [f"receivedDateTime ge {since}"]
    if unread_only:
        filter_parts.append("isRead eq false")
    odata_filter = " and ".join(filter_parts)

    # Query Graph API
    params = {
        "$filter": odata_filter,
        "$orderby": "receivedDateTime desc",
        "$top": str(min(max_results, 100)),
        "$select": "id,subject,from,receivedDateTime,isRead,importance,bodyPreview,conversationId,flag,hasAttachments",
    }
    result = graph_request("/me/messages", params=params)
    messages = result.get("value", [])

    # Load dismissed state
    state_script = os.path.join(SCRIPT_DIR, "outlook-state.py")
    dismissed_path = os.path.join(SCRIPT_DIR, "..", "state", "dismissed.json")
    dismissed_ids = set()
    snoozed = {}
    if os.path.isfile(dismissed_path):
        with open(dismissed_path) as f:
            state_data = json.load(f)
            dismissed_ids = set(state_data.get("dismissed", {}).keys())
            snoozed = state_data.get("snoozed", {})

    # Score and filter
    scored = []
    now = time.time()
    for msg in messages:
        msg_id = msg.get("id", "")
        sender_email = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        subject = msg.get("subject", "")

        # Skip dismissed
        if msg_id in dismissed_ids:
            continue
        # Skip active snoozes
        if msg_id in snoozed and snoozed[msg_id].get("until_ts", 0) > now:
            continue
        # Skip broadcast senders
        if should_skip_sender(sender_email, heuristics.get("skip_senders", [])):
            continue
        # Skip by subject pattern
        if should_skip_subject(subject, heuristics.get("skip_subject_patterns", [])):
            continue

        score, tags = score_email(msg, heuristics, applied_companies)
        if score > 0:
            scored.append({
                "id": msg_id,
                "subject": subject,
                "from_name": msg.get("from", {}).get("emailAddress", {}).get("name", ""),
                "from_email": sender_email,
                "received": msg.get("receivedDateTime", ""),
                "time_ago": _time_ago(msg.get("receivedDateTime", "")),
                "is_read": msg.get("isRead", True),
                "importance": msg.get("importance", "normal"),
                "has_attachments": msg.get("hasAttachments", False),
                "conversation_id": msg.get("conversationId", ""),
                "score": score,
                "tags": tags,
                "preview": (msg.get("bodyPreview") or "")[:200],
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def main():
    parser = argparse.ArgumentParser(description="Outlook inbox scanner")
    parser.add_argument("--days", type=int, default=7, help="Scan last N days (default: 7)")
    parser.add_argument("--unread-only", action="store_true", help="Only scan unread messages")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--urgent-only", action="store_true", help="Only show score >= 150")
    parser.add_argument("--top", type=int, default=0, help="Limit to top N results")
    args = parser.parse_args()

    results = scan_inbox(days=args.days, unread_only=args.unread_only)

    if args.urgent_only:
        results = [r for r in results if r["score"] >= 150]

    if args.top > 0:
        results = results[:args.top]

    # Count by tier
    urgent = [r for r in results if r["score"] >= 150]
    high = [r for r in results if 80 <= r["score"] < 150]
    normal = [r for r in results if 30 <= r["score"] < 80]

    if args.json:
        output = {
            "scan_time": datetime.now(timezone.utc).isoformat(),
            "days_scanned": args.days,
            "count": len(results),
            "urgent": len(urgent),
            "high": len(high),
            "normal": len(normal),
            "items": results,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"INBOX SCAN: {len(results)} needing attention | "
              f"{len(urgent)} urgent | {len(high)} high | {len(normal)} normal")
        print()
        for item in results:
            read_flag = "" if item["is_read"] else " | UNREAD"
            tags_str = ", ".join(item["tags"]) if item["tags"] else ""
            tag_prefix = f"{tags_str}: " if tags_str else ""
            attach = " [+attach]" if item["has_attachments"] else ""
            print(f"[{item['score']:>3}] {tag_prefix}{item['from_name']} <{item['from_email']}>"
                  f" — \"{item['subject']}\""
                  f" | {item['time_ago']}{read_flag}{attach}")
        if not results:
            print("(no actionable emails found)")


if __name__ == "__main__":
    main()
