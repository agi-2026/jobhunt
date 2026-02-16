#!/usr/bin/env python3
"""Pre-flight URL validator. Uses ATS-specific APIs for reliable dead-link detection.
Falls back to HTTP GET + HTML scraping for unknown ATS types.

Usage: python3 scripts/preflight-check.py "<url>"
Output: ALIVE <reason> or DEAD <reason>
"""

import sys
import re
import json
import urllib.request
import urllib.error
import ssl

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

API_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
}

DEAD_INDICATORS = [
    "<title>404", "<title>not found", "<title>page not found",
    "this job is no longer available", "this position has been filled",
    "this job has been closed", "no longer accepting applications",
    "job not found", "position not found", "this role has been filled",
    "this posting has expired", "the position you are looking for",
    "this job posting is no longer active", "oops! we can't find that page",
    "this requisition is no longer active",
    "sorry, we couldn't find anything here",
    "this page isn't available",
]

REDIRECT_PATTERNS = [
    r"careers\..*\.com/?$",
    r"/careers/?$",
    r"/jobs/?$",
    r"boards\.greenhouse\.io/[^/]+/?$",
]


def api_get(url, timeout=10):
    """Make API GET request. Returns (status_code, json_or_none)."""
    try:
        req = urllib.request.Request(url, headers=API_HEADERS)
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


def check_greenhouse_api(url):
    """Check Greenhouse job via API: boards-api.greenhouse.io/v1/boards/{slug}/jobs/{id}"""
    m = re.match(r"https?://(?:job-boards|boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if not m:
        return None  # not a parseable Greenhouse URL, fall back
    company, job_id = m.group(1), m.group(2)
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs/{job_id}"
    status, data = api_get(api_url)
    if status == 200 and data:
        return "ALIVE", f"Greenhouse API: job active ({data.get('title', '?')})"
    elif status == 404:
        return "DEAD", f"Greenhouse API 404: {company}/jobs/{job_id}"
    return None  # uncertain, fall back


def check_lever_api(url):
    """Check Lever job via API: api.lever.co/v0/postings/{company}/{id}"""
    m = re.match(r"https?://jobs\.lever\.co/([^/]+)/([^/?#]+)", url)
    if not m:
        return None
    company, job_id = m.group(1), m.group(2)
    api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
    status, data = api_get(api_url)
    if status == 200 and data:
        return "ALIVE", f"Lever API: job active ({data.get('text', '?')})"
    elif status == 404:
        return "DEAD", f"Lever API 404: {company}/{job_id}"
    return None


def check_ashby_api(url):
    """Check Ashby job via API: fetch board listing, check if job ID exists.
    Uses streaming scan to avoid loading multi-MB responses fully into memory."""
    m = re.match(r"https?://jobs\.ashbyhq\.com/([^/]+)/([^/?#]+)", url)
    if not m:
        return None
    company, job_id = m.group(1), m.group(2)
    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"

    # Stream-scan: just check if the job ID string appears in the response
    # This avoids parsing multi-MB JSON (OpenAI board is 8MB+)
    try:
        req = urllib.request.Request(api_url, headers=API_HEADERS)
        resp = urllib.request.urlopen(req, timeout=20, context=CTX)
        if resp.status != 200:
            return None

        # Read in chunks, search for the job ID string
        found = False
        total_read = 0
        max_read = 15_000_000  # 15MB safety limit
        while total_read < max_read:
            chunk = resp.read(65536)
            if not chunk:
                break
            total_read += len(chunk)
            if job_id.encode() in chunk:
                found = True
                break

        if found:
            return "ALIVE", f"Ashby API: job ID found in {company} board"
        else:
            return "DEAD", f"Ashby API: job {job_id[:12]}... not in {company} board"

    except Exception:
        return None  # fall back to HTML check


def check_url_html(url, timeout=10):
    """Fallback: HTTP GET + HTML body check."""
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        resp = urllib.request.urlopen(req, timeout=timeout, context=CTX)
        final_url = resp.url
        body = resp.read(50000).decode("utf-8", errors="ignore").lower()

        for indicator in DEAD_INDICATORS:
            if indicator in body:
                return "DEAD", f"Page contains: {indicator}"

        for pattern in REDIRECT_PATTERNS:
            if re.search(pattern, final_url):
                return "DEAD", f"Redirected to generic page: {final_url}"

        return "ALIVE", "OK"

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "DEAD", "HTTP 404"
        elif e.code == 410:
            return "DEAD", "HTTP 410 Gone"
        elif e.code in (403, 429):
            return "ALIVE", f"HTTP {e.code} (assuming alive, needs browser)"
        else:
            return "ALIVE", f"HTTP {e.code} (uncertain, try browser)"
    except urllib.error.URLError as e:
        return "ALIVE", f"URL Error: {str(e.reason)[:60]} (try browser)"
    except Exception as e:
        return "ALIVE", f"Error: {str(e)[:60]} (try browser)"


def check_url(url, timeout=10):
    """Check URL: try ATS API first, fall back to HTML check."""
    # Try ATS-specific API checks (fast, reliable, no JS needed)
    if "greenhouse.io" in url:
        result = check_greenhouse_api(url)
        if result:
            return result
    elif "lever.co" in url:
        result = check_lever_api(url)
        if result:
            return result
    elif "ashbyhq.com" in url:
        result = check_ashby_api(url)
        if result:
            return result

    # Fallback: HTML scraping
    return check_url_html(url, timeout)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/preflight-check.py '<url>'")
        sys.exit(1)

    url = sys.argv[1].strip()
    status, reason = check_url(url)
    print(f"{status} {reason}")


if __name__ == "__main__":
    main()
