#!/usr/bin/env python3
"""
Mark a job as applied: updates queue status, dedup index, and verifies consistency.

Usage:
  python3 scripts/mark-applied.py "<url>" ["<company>"] ["<title>"] [--force]

Safety default:
  Refuses to mark applied when the URL is not currently in PENDING queue state.
  Use --force only for manual backfill/corrections.
"""
import sys
import re
import os
import fcntl
from datetime import datetime
from urllib.parse import urlparse

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
QUEUE_PATH = os.path.join(WORKSPACE, "job-queue.md")
DEDUP_PATH = os.path.join(WORKSPACE, "dedup-index.md")
TRACKER_PATH = os.path.join(WORKSPACE, "job-tracker.md")
LOCK_PATH = os.path.join(WORKSPACE, ".queue.lock")


def _is_valid_http_url(value):
    if not value:
        return False
    candidate = value.strip()
    if candidate in {"--help", "-h", "help"}:
        return False
    parsed = urlparse(candidate)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _do_mark_applied(url, company, title, force=False):
    if not _is_valid_http_url(url):
        print(f"ERROR: Invalid URL '{url}'. mark-applied.py requires a full http(s) URL.")
        return 2

    now = datetime.now()
    today_date = now.strftime("%Y-%m-%d")

    # 1. Update job-queue.md: REMOVE the entry from PENDING section entirely
    queue_updated = False
    with open(QUEUE_PATH, "r") as f:
        content = f.read()

    lines = content.split('\n')
    url_variants = [url, url + "/application", url.replace("/application", "")]
    i = 0
    while i < len(lines):
        if lines[i].startswith('### '):
            block_start = i
            block_end = i + 1
            while block_end < len(lines) and not lines[block_end].startswith('### ') and not lines[block_end].startswith('## '):
                block_end += 1
            block = '\n'.join(lines[block_start:block_end])
            if any(v in block for v in url_variants) and 'PENDING' in block:
                del lines[block_start:block_end]
                queue_updated = True
                continue
            i = block_end
        else:
            i += 1

    if queue_updated:
        with open(QUEUE_PATH, "w") as f:
            f.write('\n'.join(lines))
        print(f"QUEUE: Marked COMPLETED")
    else:
        print(f"QUEUE: Not PENDING or not found")
        if not force:
            print("ERROR: Refusing to mark APPLIED because URL is not in PENDING queue state. Re-run with --force only for manual correction.")
            return 2

    # 2. Update dedup-index.md: change PENDING → APPLIED
    dedup_updated = False
    url_variants = [url, url + "/application", url.replace("/application", "")]

    with open(DEDUP_PATH, "r") as f:
        dedup_lines = f.readlines()

    seen_urls = set()
    new_dedup_lines = []
    for line in dedup_lines:
        matched = False
        for variant in url_variants:
            if variant in line:
                matched = True
                if "PENDING" in line or "| APPLIED" not in line:
                    # Update to APPLIED
                    parts = line.strip().split(" | ")
                    if len(parts) >= 4:
                        parts[3] = "APPLIED"
                    if len(parts) >= 5:
                        parts[4] = f" {today_date}"
                    new_line = " | ".join(parts) + "\n"
                    norm_url = variant.replace("/application", "")
                    if norm_url not in seen_urls:
                        new_dedup_lines.append(new_line)
                        seen_urls.add(norm_url)
                        dedup_updated = True
                else:
                    norm_url = variant.replace("/application", "")
                    if norm_url not in seen_urls:
                        new_dedup_lines.append(line)
                        seen_urls.add(norm_url)
                break
        if not matched:
            new_dedup_lines.append(line)

    # If URL not in dedup at all, add it
    norm_url = url.replace("/application", "")
    if norm_url not in seen_urls:
        new_entry = f"{url} | {company} | {title} | APPLIED | {today_date}\n"
        new_dedup_lines.append(new_entry)
        dedup_updated = True

    if dedup_updated:
        with open(DEDUP_PATH, "w") as f:
            f.writelines(new_dedup_lines)
        print(f"DEDUP: Updated to APPLIED")
    else:
        print(f"DEDUP: Already APPLIED")

    # 3. Add to job-tracker.md if not already there
    tracker_updated = False
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH, "r") as f:
            tracker_content = f.read()
        # Check if URL already in tracker
        if url not in tracker_content and norm_url not in tracker_content:
            entry = f"\n### {company or 'Unknown'} — {title or 'Unknown'}\n"
            entry += f"- **Stage:** Applied\n"
            entry += f"- **Date Applied:** {today_date}\n"
            entry += f"- **Link:** {url}\n"
            entry += f"- **Notes:** Auto-applied by agent\n"

            if "## Priority Follow-ups" in tracker_content:
                tracker_content = tracker_content.replace(
                    "## Priority Follow-ups", entry + "\n## Priority Follow-ups"
                )
            else:
                tracker_content += entry
            with open(TRACKER_PATH, "w") as f:
                f.write(tracker_content)
            tracker_updated = True
            print(f"TRACKER: Added entry")
        else:
            print(f"TRACKER: Already exists")
    else:
        print(f"TRACKER: File not found, skipping")

    print(f"DONE: {company} — {title}")
    return 0


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/mark-applied.py '<url>' ['<company>'] ['<title>']")
        sys.exit(1)

    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]
    if not args:
        print("Usage: python3 scripts/mark-applied.py '<url>' ['<company>'] ['<title>'] [--force]")
        sys.exit(1)

    url = args[0].strip().rstrip("/")
    company = args[1] if len(args) > 1 else ""
    title = args[2] if len(args) > 2 else ""

    if not _is_valid_http_url(url):
        print(f"ERROR: Invalid URL '{url}'. mark-applied.py requires a full http(s) URL.")
        sys.exit(2)

    with open(LOCK_PATH, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            rc = _do_mark_applied(url, company, title, force=force)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)
    sys.exit(rc)

if __name__ == "__main__":
    main()
