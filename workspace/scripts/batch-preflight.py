#!/usr/bin/env python3
"""Batch URL validator using ATS-specific APIs. Much more reliable than HTML scraping.

For Ashby: fetches full job board listing, checks if job ID exists
For Greenhouse: hits individual job API endpoint (200/404)
For Lever: hits individual posting API endpoint (200/404)

Usage:
  python3 scripts/batch-preflight.py --ats ashby      # check all Ashby URLs
  python3 scripts/batch-preflight.py --ats greenhouse  # check all Greenhouse URLs
  python3 scripts/batch-preflight.py --ats lever       # check all Lever URLs
  python3 scripts/batch-preflight.py --all             # check all ATS types
  python3 scripts/batch-preflight.py --all --remove    # check + remove dead from queue
"""

import sys
import os
import re
import json
import time
import argparse
import urllib.request
import urllib.error
import ssl
import subprocess

QUEUE_PATH = os.path.expanduser("~/.openclaw/workspace/job-queue.md")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

# SSL context for API calls
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
}


def api_get(url, timeout=10):
    """Make a GET request and return (status_code, body_json_or_none)."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
        body = resp.read(200000).decode("utf-8", errors="ignore")
        try:
            return resp.status, json.loads(body)
        except json.JSONDecodeError:
            return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return -1, None


def parse_url_ashby(url):
    """Extract (company, jobId) from Ashby URL."""
    m = re.match(r"https?://jobs\.ashbyhq\.com/([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def parse_url_greenhouse(url):
    """Extract (company, jobId) from Greenhouse URL."""
    m = re.match(r"https?://(?:job-boards|boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def parse_url_lever(url):
    """Extract (company, jobId) from Lever URL."""
    m = re.match(r"https?://jobs\.lever\.co/([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None


ATS_URL_PATTERNS = {
    "ashby": r"ashbyhq\.com",
    "greenhouse": r"greenhouse\.io",
    "lever": r"lever\.co",
}


def get_queue_jobs(ats_filter=None):
    """Get pending jobs directly from queue markdown (avoids URL truncation).
    Optionally filtered by ATS type."""
    try:
        with open(QUEUE_PATH, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print("ERROR: Queue file not found", file=sys.stderr)
        return []

    jobs = []
    current = {}
    in_pending = False

    for line in content.split("\n"):
        if line.startswith("## ") and ("PENDING" in line.upper() or "Pending" in line):
            in_pending = True
            continue
        if line.startswith("## ") and in_pending:
            break

        if not in_pending:
            continue

        if line.startswith("### "):
            if current.get("url"):
                jobs.append(current)
            m = re.match(r"### (.+?) — (.+?)(?:\s*\[(\d+)\])?$", line.strip())
            if m:
                current = {"company": m.group(1).strip(), "title": m.group(2).strip(),
                           "score": int(m.group(3) or 0)}
            else:
                current = {"company": line.replace("### ", "").strip(), "title": "Unknown", "score": 0}
        elif "**URL:**" in line:
            m = re.search(r"https?://\S+", line)
            if m:
                current["url"] = m.group(0).rstrip(")")
        elif "Auto-Apply: NO" in line or "NO-AUTO" in line:
            current["no_auto"] = True

    if current.get("url"):
        jobs.append(current)

    # Filter by ATS type
    if ats_filter and ats_filter in ATS_URL_PATTERNS:
        pattern = ATS_URL_PATTERNS[ats_filter]
        jobs = [j for j in jobs if re.search(pattern, j.get("url", ""))]

    # Exclude NO-AUTO
    jobs = [j for j in jobs if not j.get("no_auto")]

    # Sort by score descending
    jobs.sort(key=lambda j: j.get("score", 0), reverse=True)

    return jobs


# --- Ashby API Checker ---

_ashby_board_cache = {}  # company -> set of job IDs

def fetch_ashby_board(company_slug):
    """Fetch all active job IDs for an Ashby company.
    Uses streaming to extract IDs from large responses (OpenAI is 8MB+)."""
    if company_slug in _ashby_board_cache:
        return _ashby_board_cache[company_slug]

    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}"

    try:
        req = urllib.request.Request(api_url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20, context=CTX)
        if resp.status != 200:
            print(f"  WARNING: Ashby API returned {resp.status} for {company_slug}", file=sys.stderr)
            _ashby_board_cache[company_slug] = None
            return None

        # Stream-extract job IDs using regex on chunks
        # Ashby API format: {"id":"uuid-here",...} for each job
        job_ids = set()
        buffer = ""
        total_read = 0
        max_read = 15_000_000
        while total_read < max_read:
            chunk = resp.read(65536)
            if not chunk:
                break
            total_read += len(chunk)
            buffer += chunk.decode("utf-8", errors="ignore")
            # Extract all job IDs from buffer
            for m in re.finditer(r'"id"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', buffer):
                job_ids.add(m.group(1))
            # Keep last 200 chars for overlapping matches
            if len(buffer) > 1000:
                buffer = buffer[-200:]

        _ashby_board_cache[company_slug] = job_ids
        print(f"  Ashby board '{company_slug}': {len(job_ids)} IDs found ({total_read//1024}KB read)", file=sys.stderr)
        return job_ids

    except Exception as e:
        print(f"  WARNING: Ashby API error for {company_slug}: {e}", file=sys.stderr)
        _ashby_board_cache[company_slug] = None
        return None


def check_ashby(url):
    """Check if an Ashby job URL is still active via API."""
    company, job_id = parse_url_ashby(url)
    if not company or not job_id:
        return "UNCERTAIN", "Could not parse Ashby URL"

    active_jobs = fetch_ashby_board(company)
    if active_jobs is None:
        return "UNCERTAIN", f"Ashby API failed for {company}"

    if job_id in active_jobs:
        return "ALIVE", "Job found in Ashby board"
    else:
        return "DEAD", f"Job ID {job_id[:8]}... not in {company} board ({len(active_jobs)} active)"


# --- Greenhouse API Checker ---

def check_greenhouse(url):
    """Check if a Greenhouse job URL is still active via API."""
    company, job_id = parse_url_greenhouse(url)
    if not company or not job_id:
        return "UNCERTAIN", "Could not parse Greenhouse URL"

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
    status, data = api_get(api_url)

    if status == 200 and data:
        return "ALIVE", f"Job active: {data.get('title', 'Unknown')}"
    elif status == 404:
        return "DEAD", f"Greenhouse API 404 for {company}/jobs/{job_id}"
    else:
        return "UNCERTAIN", f"Greenhouse API returned {status}"


# --- Lever API Checker ---

def check_lever(url):
    """Check if a Lever job URL is still active via API."""
    company, job_id = parse_url_lever(url)
    if not company or not job_id:
        return "UNCERTAIN", "Could not parse Lever URL"

    api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
    status, data = api_get(api_url)

    if status == 200 and data:
        return "ALIVE", f"Job active: {data.get('text', 'Unknown')}"
    elif status == 404:
        return "DEAD", f"Lever API 404 for {company}/{job_id}"
    else:
        return "UNCERTAIN", f"Lever API returned {status}"


# --- ATS Router ---

def detect_ats(url):
    """Detect ATS type from URL."""
    if "ashbyhq.com" in url:
        return "ashby"
    elif "greenhouse.io" in url:
        return "greenhouse"
    elif "lever.co" in url:
        return "lever"
    return "other"


def check_url(url):
    """Route to the correct ATS checker."""
    ats = detect_ats(url)
    if ats == "ashby":
        return check_ashby(url)
    elif ats == "greenhouse":
        return check_greenhouse(url)
    elif ats == "lever":
        return check_lever(url)
    else:
        return "UNCERTAIN", f"Unknown ATS type for URL"


def remove_from_queue(url):
    """Remove a dead URL from the queue."""
    script = os.path.join(SCRIPTS_DIR, "remove-from-queue.py")
    try:
        subprocess.run(
            ["python3", script, url, "--reason", "dead-link"],
            capture_output=True, text=True, timeout=10
        )
    except Exception as e:
        print(f"  WARNING: Failed to remove {url}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Batch URL validator using ATS APIs")
    parser.add_argument("--ats", choices=["ashby", "greenhouse", "lever"], help="Filter by ATS type")
    parser.add_argument("--all", action="store_true", help="Check all ATS types")
    parser.add_argument("--remove", action="store_true", help="Remove dead URLs from queue")
    parser.add_argument("--top", type=int, default=50, help="Max URLs to check (default: 50)")
    args = parser.parse_args()

    if not args.ats and not args.all:
        parser.error("Must specify --ats <type> or --all")

    ats_types = ["ashby", "greenhouse", "lever"] if args.all else [args.ats]

    all_dead = []
    all_alive = []
    all_uncertain = []

    for ats in ats_types:
        print(f"\n=== Checking {ats.upper()} URLs ===", file=sys.stderr)
        jobs = get_queue_jobs(ats_filter=ats)
        print(f"  Found {len(jobs)} {ats} jobs in queue", file=sys.stderr)

        if not jobs:
            continue

        # Limit checks
        jobs = jobs[:args.top]

        for i, job in enumerate(jobs):
            url = job["url"]
            company = job["company"]
            title = job["title"]

            status, reason = check_url(url)

            if status == "DEAD":
                all_dead.append({**job, "reason": reason})
                print(f"  [{i+1}/{len(jobs)}] DEAD: {company} — {title} ({reason})", file=sys.stderr)
                if args.remove:
                    remove_from_queue(url)
                    print(f"    -> Removed from queue", file=sys.stderr)
            elif status == "ALIVE":
                all_alive.append(job)
                print(f"  [{i+1}/{len(jobs)}] ALIVE: {company} — {title}", file=sys.stderr)
            else:
                all_uncertain.append({**job, "reason": reason})
                print(f"  [{i+1}/{len(jobs)}] ???: {company} — {title} ({reason})", file=sys.stderr)

            # Rate limit: 200ms between Greenhouse/Lever API calls (Ashby is batched)
            if ats != "ashby":
                time.sleep(0.2)

    # Summary
    print(f"\n{'='*40}", file=sys.stderr)
    print(f"ALIVE: {len(all_alive)} | DEAD: {len(all_dead)} | UNCERTAIN: {len(all_uncertain)}", file=sys.stderr)
    if args.remove and all_dead:
        print(f"REMOVED: {len(all_dead)} dead URLs from queue", file=sys.stderr)

    # JSON output to stdout
    result = {
        "alive": len(all_alive),
        "dead": len(all_dead),
        "uncertain": len(all_uncertain),
        "removed": len(all_dead) if args.remove else 0,
        "dead_urls": [{"company": d["company"], "title": d["title"], "url": d["url"], "reason": d["reason"]} for d in all_dead],
    }
    json.dump(result, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
