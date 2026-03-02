#!/usr/bin/env python3
"""Generate formatted inbox digest for Outlook Assistant.

Can output in full format or WhatsApp-ready short format.

Usage:
    python3 outlook-digest.py                  # From cached scan
    python3 outlook-digest.py --scan           # Fresh scan first
    python3 outlook-digest.py --scan --days 3  # Fresh scan, last 3 days
    python3 outlook-digest.py --whatsapp       # Short format for WhatsApp (<4000 chars)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_SCRIPTS = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", "scripts"))
sys.path.insert(0, WORKSPACE_SCRIPTS)

STATE_DIR = os.path.join(SCRIPT_DIR, "..", "state")
SCAN_CACHE_PATH = os.path.join(STATE_DIR, "scan-cache.json")


def load_cached_scan():
    """Load scan results from cache."""
    if not os.path.isfile(SCAN_CACHE_PATH):
        return None
    with open(SCAN_CACHE_PATH) as f:
        return json.load(f)


def run_fresh_scan(days=7):
    """Run outlook-scan.py and cache results."""
    scan_script = os.path.join(SCRIPT_DIR, "outlook-scan.py")
    import subprocess
    result = subprocess.run(
        [sys.executable, scan_script, "--days", str(days), "--json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: Scan failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(result.stdout)

    # Cache it
    os.makedirs(STATE_DIR, exist_ok=True)
    data["cached_at"] = int(datetime.now(timezone.utc).timestamp())
    tmp = SCAN_CACHE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, SCAN_CACHE_PATH)
    return data


def format_full_digest(data):
    """Format a full digest."""
    items = data.get("items", [])
    if not items:
        return "Inbox is clear — no actionable emails found."

    urgent = [i for i in items if i["score"] >= 150]
    high = [i for i in items if 80 <= i["score"] < 150]
    normal = [i for i in items if 30 <= i["score"] < 80]

    lines = [
        f"# Inbox Digest",
        f"Scanned: {data.get('days_scanned', '?')} days | "
        f"Total: {data.get('count', len(items))} | "
        f"Urgent: {len(urgent)} | High: {len(high)} | Normal: {len(normal)}",
        "",
    ]

    if urgent:
        lines.append("## URGENT (action needed now)")
        for item in urgent:
            tags = ", ".join(item.get("tags", []))
            lines.append(
                f"- [{item['score']}] **{tags}** | {item['from_name']} — "
                f"\"{item['subject']}\" | {item['time_ago']}"
            )
            if item.get("preview"):
                lines.append(f"  > {item['preview'][:150]}")
        lines.append("")

    if high:
        lines.append("## HIGH PRIORITY")
        for item in high:
            tags = ", ".join(item.get("tags", []))
            read = " [UNREAD]" if not item.get("is_read", True) else ""
            lines.append(
                f"- [{item['score']}] {tags} | {item['from_name']} — "
                f"\"{item['subject']}\" | {item['time_ago']}{read}"
            )
        lines.append("")

    if normal:
        lines.append(f"## NORMAL ({len(normal)} items)")
        for item in normal[:5]:  # Show max 5 normal items
            lines.append(
                f"- [{item['score']}] {item['from_name']} — "
                f"\"{item['subject']}\" | {item['time_ago']}"
            )
        if len(normal) > 5:
            lines.append(f"  ... and {len(normal) - 5} more")

    return "\n".join(lines)


def format_whatsapp_digest(data):
    """Format a short digest for WhatsApp (<4000 chars)."""
    items = data.get("items", [])
    if not items:
        return ""  # Empty = no WhatsApp sent (announce mode)

    urgent = [i for i in items if i["score"] >= 150]
    high = [i for i in items if 80 <= i["score"] < 150]

    if not urgent and not high:
        return ""  # Nothing worth alerting about

    lines = []
    if urgent:
        lines.append(f"[URGENT INBOX] {len(urgent)} email(s) need attention:")
        for item in urgent[:3]:
            tags = "/".join(item.get("tags", []))
            lines.append(
                f"  {tags}: \"{item['subject']}\" "
                f"from {item['from_name']} ({item['time_ago']})"
            )

    if high:
        lines.append(f"\n[HIGH] {len(high)} more:")
        for item in high[:3]:
            lines.append(
                f"  {item['from_name']}: \"{item['subject']}\" ({item['time_ago']})"
            )
        if len(high) > 3:
            lines.append(f"  +{len(high) - 3} more")

    result = "\n".join(lines)
    # Respect WhatsApp 4000 char limit
    if len(result) > 3900:
        result = result[:3900] + "\n..."
    return result


def main():
    parser = argparse.ArgumentParser(description="Outlook inbox digest generator")
    parser.add_argument("--scan", action="store_true", help="Run fresh scan first")
    parser.add_argument("--days", type=int, default=7, help="Days to scan (with --scan)")
    parser.add_argument("--whatsapp", action="store_true", help="Short format for WhatsApp")
    parser.add_argument("--json", action="store_true", help="Output raw scan data as JSON")
    args = parser.parse_args()

    if args.scan:
        data = run_fresh_scan(days=args.days)
    else:
        data = load_cached_scan()
        if not data:
            print("No cached scan. Run with --scan flag.", file=sys.stderr)
            sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2))
    elif args.whatsapp:
        result = format_whatsapp_digest(data)
        if result:
            print(result)
        else:
            # Empty output = silent (announce mode won't send)
            pass
    else:
        print(format_full_digest(data))


if __name__ == "__main__":
    main()
