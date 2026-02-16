#!/usr/bin/env python3
"""Clean expired/dead jobs from the queue by checking URLs."""
import re, sys, subprocess, time, urllib.request, urllib.error, ssl

QUEUE_PATH = "/Users/howard/.openclaw/workspace/job-queue.md"

def check_url(url, timeout=10):
    """Returns (alive, status_code, reason)"""
    if not url.startswith("http"):
        url = "https://" + url
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, method='HEAD', headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    })
    try:
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        return (True, resp.status, "OK")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (False, 404, "Not Found")
        if e.code == 410:
            return (False, 410, "Gone")
        # 403/405 might just block HEAD
        return (True, e.code, str(e.reason))
    except Exception as e:
        return (True, 0, str(e)[:50])  # network error = don't remove

def main():
    dry_run = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 500
    
    with open(QUEUE_PATH, "r") as f:
        content = f.read()
    
    lines = content.split("\n")
    dead_jobs = []
    checked = 0
    
    # Find PENDING job entries
    i = 0
    while i < len(lines) and checked < limit:
        line = lines[i]
        if line.startswith("### ") and "PENDING" in content[content.index(line):content.index(line)+500]:
            # Extract URL from the job block
            block_start = i
            block_end = i + 1
            url = None
            status_line = None
            while block_end < len(lines) and not lines[block_end].startswith("### "):
                if lines[block_end].startswith("- **URL:**") or lines[block_end].startswith("- **Link:**"):
                    url_match = re.search(r'(https?://\S+)', lines[block_end])
                    if url_match:
                        url = url_match.group(1)
                if lines[block_end].startswith("- **Status:**"):
                    status_line = block_end
                    if "PENDING" not in lines[block_end]:
                        url = None  # not pending, skip
                        break
                block_end += 1
            
            if url:
                checked += 1
                alive, code, reason = check_url(url)
                if not alive:
                    title = line.replace("### ", "").strip()
                    dead_jobs.append((title, url, code, reason, block_start, block_end))
                    if checked % 10 == 0:
                        print(f"Checked {checked}... ({len(dead_jobs)} dead)", file=sys.stderr)
            i = block_end
        else:
            i += 1
    
    print(f"Checked {checked} URLs, found {len(dead_jobs)} dead/expired")
    
    if dead_jobs:
        for title, url, code, reason, _, _ in dead_jobs:
            print(f"  ❌ [{code}] {title} — {url}")
    
    if dead_jobs and not dry_run:
        # Remove dead jobs from queue
        removed = 0
        # Work backwards to preserve indices
        for title, url, code, reason, start, end in reversed(dead_jobs):
            lines[start:end] = []
            removed += 1
        
        with open(QUEUE_PATH, "w") as f:
            f.write("\n".join(lines))
        
        # Update stats line
        pending_count = "\n".join(lines).count("PENDING")
        print(f"\nRemoved {removed} dead jobs. {pending_count} PENDING remain.")
    elif dry_run and dead_jobs:
        print(f"\n(dry run — would remove {len(dead_jobs)} jobs)")

if __name__ == "__main__":
    main()
