#!/usr/bin/env python3
"""
Build dedup-index.md from all sources:
1. job-tracker.md — extract URL + Company + Title from each ### entry
2. job-queue.md — extract URL + Company + Title from ALL sections
3. job-queue-archive.md — extract from archived entries
4. manual-dedup.md — extract URLs
Output: dedup-index.md with one line per unique URL.
Runs every 30 min via launchd (after compact-queue.py).
"""
import re
import os
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
TRACKER_FILE = os.path.join(WORKSPACE, "job-tracker.md")
QUEUE_FILE = os.path.join(WORKSPACE, "job-queue.md")
ARCHIVE_FILE = os.path.join(WORKSPACE, "job-queue-archive.md")
MANUAL_DEDUP_FILE = os.path.join(WORKSPACE, "manual-dedup.md")
OUTPUT_FILE = os.path.join(WORKSPACE, "dedup-index.md")
LOG_FILE = "/tmp/openclaw/compaction.log"

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def read_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()

def extract_from_tracker(content):
    """Extract entries from job-tracker.md format:
    ### [Company] — [Title]
    - **Link:** URL
    - **Date Applied:** YYYY-MM-DD
    """
    entries = {}
    current_company = None
    current_title = None
    current_url = None
    current_date = None

    for line in content.split("\n"):
        # Match ### [Company] — [Title] or ### Company — Title
        m = re.match(r"^### \[?(.+?)\]?\s*[—–-]\s*(.+?)$", line)
        if m:
            # Save previous entry
            if current_url and current_url not in entries:
                entries[current_url] = {
                    "company": current_company or "Unknown",
                    "title": current_title or "Unknown",
                    "status": "APPLIED",
                    "date": current_date or "",
                }
            current_company = m.group(1).strip()
            current_title = m.group(2).strip()
            current_url = None
            current_date = None
            continue

        # Match URL
        m = re.match(r"^- \*\*(?:Link|URL):\*\*\s*(.+)$", line)
        if m:
            current_url = m.group(1).strip()
            continue

        # Match date
        m = re.match(r"^- \*\*Date Applied:\*\*\s*(.+)$", line)
        if m:
            current_date = m.group(1).strip()
            continue

    # Save last entry
    if current_url and current_url not in entries:
        entries[current_url] = {
            "company": current_company or "Unknown",
            "title": current_title or "Unknown",
            "status": "APPLIED",
            "date": current_date or "",
        }

    return entries

def extract_from_queue(content):
    """Extract entries from job-queue.md format:
    ### [SCORE] Company — Title
    - **URL:** https://...
    - **Status:** COMPLETED/SKIPPED/PENDING
    """
    entries = {}
    current_company = None
    current_title = None
    current_url = None
    current_status = None

    for line in content.split("\n"):
        # Match ### [SCORE] Company — Title
        m = re.match(r"^### \[\d+\]\s*(.+?)\s*[—–-]\s*(.+?)$", line)
        if m:
            if current_url and current_url not in entries:
                entries[current_url] = {
                    "company": current_company or "Unknown",
                    "title": current_title or "Unknown",
                    "status": current_status or "UNKNOWN",
                    "date": "",
                }
            current_company = m.group(1).strip()
            current_title = m.group(2).strip()
            current_url = None
            current_status = None
            continue

        m = re.match(r"^- \*\*URL:\*\*\s*(.+)$", line)
        if m:
            current_url = m.group(1).strip()
            continue

        m = re.match(r"^- \*\*Status:\*\*\s*(\w+)", line)
        if m:
            current_status = m.group(1).strip()
            continue

        # Also detect status from section context
        if line.strip().startswith("- **Applied:"):
            current_status = "COMPLETED"
        elif line.strip().startswith("- **Reason:"):
            current_status = "SKIPPED"

    if current_url and current_url not in entries:
        entries[current_url] = {
            "company": current_company or "Unknown",
            "title": current_title or "Unknown",
            "status": current_status or "UNKNOWN",
            "date": "",
        }

    return entries

def extract_manual_urls(content):
    """Extract bare URLs from manual-dedup.md."""
    entries = {}
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("http"):
            url = line.split()[0]
            entries[url] = {
                "company": "Manual",
                "title": "Manual",
                "status": "MANUAL",
                "date": "",
            }
    return entries

def main():
    all_entries = {}

    # 1. Job tracker (highest priority — these are confirmed applications)
    tracker_content = read_file(TRACKER_FILE)
    tracker_entries = extract_from_tracker(tracker_content)
    all_entries.update(tracker_entries)

    # 2. Queue (current)
    queue_content = read_file(QUEUE_FILE)
    queue_entries = extract_from_queue(queue_content)
    for url, data in queue_entries.items():
        if url not in all_entries:
            all_entries[url] = data

    # 3. Archive
    archive_content = read_file(ARCHIVE_FILE)
    archive_entries = extract_from_queue(archive_content)
    for url, data in archive_entries.items():
        if url not in all_entries:
            all_entries[url] = data

    # 4. Manual dedup
    manual_content = read_file(MANUAL_DEDUP_FILE)
    manual_entries = extract_manual_urls(manual_content)
    for url, data in manual_entries.items():
        if url not in all_entries:
            all_entries[url] = data

    # Build output
    ts = datetime.now().strftime("%Y-%m-%d %H:%M CT")
    lines = [
        f"# Dedup Index (auto-generated {ts})",
        f"# {len(all_entries)} unique URLs. Agent: check this file for dedup, NOT full tracker/queue.",
        "# Format: URL | Company | Title | Status | Date",
        "",
    ]

    for url, data in sorted(all_entries.items()):
        # Skip template/placeholder entries
        if url.startswith("[") or "example.com" in url or not url.startswith("http"):
            continue
        company = data["company"].replace("|", "/")
        title = data["title"].replace("|", "/")
        status = data["status"]
        date = data["date"]
        lines.append(f"{url} | {company} | {title} | {status} | {date}")

    output = "\n".join(lines) + "\n"

    with open(OUTPUT_FILE, "w") as f:
        f.write(output)

    log(f"Dedup index rebuilt: {len(all_entries)} unique URLs, {os.path.getsize(OUTPUT_FILE)} bytes")

if __name__ == "__main__":
    main()