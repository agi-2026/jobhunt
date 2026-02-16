#!/usr/bin/env python3
"""Batch URL validator for job queue. Checks each PENDING job URL via HTTP GET.
Marks jobs as DEAD if they return 404, redirect to generic careers page, or are otherwise invalid.
Output: JSON list of {url, company, title, status, reason}
"""

import re
import sys
import json
import urllib.request
import urllib.error
import ssl
import time

QUEUE_PATH = "/Users/howard/.openclaw/workspace/job-queue.md"

# Keywords that indicate a generic careers/404 page (not a specific job)
DEAD_INDICATORS = [
    "<title>404", "<title>not found", "<title>page not found",
    "this job is no longer available", "this position has been filled",
    "this job has been closed", "no longer accepting applications",
    "job not found", "position not found", "this role has been filled",
    "this posting has expired", "the position you are looking for",
    "this job posting is no longer active", "oops! we can't find that page",
    "this requisition is no longer active",
]

# If redirected to these patterns, the specific job is gone
REDIRECT_PATTERNS = [
    r"careers\..*\.com/?$",  # redirected to generic careers page
    r"/careers/?$",
    r"/jobs/?$",
    r"boards\.greenhouse\.io/[^/]+/?$",  # greenhouse board root (no job ID)
]

def parse_queue():
    """Extract PENDING jobs from queue markdown."""
    with open(QUEUE_PATH, "r") as f:
        content = f.read()
    
    jobs = []
    current = {}
    in_pending = False
    
    for line in content.split("\n"):
        if "## PENDING" in line or "## Pending" in line:
            in_pending = True
            continue
        if line.startswith("## ") and in_pending:
            break  # hit next section
        
        if not in_pending:
            continue
            
        if line.startswith("### "):
            if current.get("url"):
                jobs.append(current)
            # Parse: ### Company — Title [Score]
            m = re.match(r"### (.+?) — (.+?)(?:\s*\[(\d+)\])?$", line.strip())
            if m:
                current = {"company": m.group(1).strip(), "title": m.group(2).strip(), "score": m.group(3) or "0"}
            else:
                current = {"company": line.replace("### ", "").strip(), "title": "Unknown", "score": "0"}
        elif "**URL:**" in line:
            m = re.search(r"https?://\S+", line)
            if m:
                current["url"] = m.group(0).rstrip(")")
        elif "Auto-Apply: NO" in line or "NO-AUTO" in line:
            current["no_auto"] = True
    
    if current.get("url"):
        jobs.append(current)
    
    return jobs

def check_url(url, timeout=15):
    """Check if URL points to a live job posting. Returns (status, reason)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        final_url = resp.url
        body = resp.read(50000).decode("utf-8", errors="ignore").lower()
        
        # Check for dead indicators in page content
        for indicator in DEAD_INDICATORS:
            if indicator in body:
                return "DEAD", f"Page contains: {indicator}"
        
        # Check if redirected to generic page
        for pattern in REDIRECT_PATTERNS:
            if re.search(pattern, final_url):
                return "DEAD", f"Redirected to generic page: {final_url}"
        
        return "LIVE", "OK"
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "DEAD", "HTTP 404"
        elif e.code == 410:
            return "DEAD", "HTTP 410 Gone"
        elif e.code == 403:
            return "UNCERTAIN", f"HTTP 403 Forbidden (may need browser)"
        elif e.code == 429:
            return "UNCERTAIN", "HTTP 429 Rate limited"
        else:
            return "UNCERTAIN", f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return "UNCERTAIN", f"URL Error: {str(e.reason)[:60]}"
    except Exception as e:
        return "UNCERTAIN", f"Error: {str(e)[:60]}"

def main():
    jobs = parse_queue()
    print(f"Found {len(jobs)} jobs in queue", file=sys.stderr)
    
    results = {"live": [], "dead": [], "uncertain": [], "no_auto": []}
    
    for i, job in enumerate(jobs):
        url = job.get("url", "")
        company = job.get("company", "?")
        title = job.get("title", "?")
        score = job.get("score", "0")
        
        if job.get("no_auto"):
            results["no_auto"].append({"company": company, "title": title, "url": url, "score": score})
            print(f"[{i+1}/{len(jobs)}] SKIP (NO-AUTO): {company} — {title}", file=sys.stderr)
            continue
        
        status, reason = check_url(url)
        entry = {"company": company, "title": title, "url": url, "score": score, "reason": reason}
        
        if status == "DEAD":
            results["dead"].append(entry)
            print(f"[{i+1}/{len(jobs)}] DEAD: {company} — {title} ({reason})", file=sys.stderr)
        elif status == "LIVE":
            results["live"].append(entry)
            print(f"[{i+1}/{len(jobs)}] LIVE: {company} — {title}", file=sys.stderr)
        else:
            results["uncertain"].append(entry)
            print(f"[{i+1}/{len(jobs)}] ???: {company} — {title} ({reason})", file=sys.stderr)
        
        time.sleep(0.5)  # rate limit
    
    # Summary
    print(f"\n=== RESULTS ===", file=sys.stderr)
    print(f"LIVE: {len(results['live'])}", file=sys.stderr)
    print(f"DEAD: {len(results['dead'])}", file=sys.stderr)
    print(f"UNCERTAIN: {len(results['uncertain'])}", file=sys.stderr)
    print(f"NO-AUTO: {len(results['no_auto'])}", file=sys.stderr)
    
    # Output JSON
    json.dump(results, sys.stdout, indent=2)

if __name__ == "__main__":
    main()
