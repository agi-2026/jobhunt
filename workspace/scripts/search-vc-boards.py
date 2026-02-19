#!/usr/bin/env python3
"""
Search VC portfolio job boards (Getro/Consider/YC) and add relevant jobs to queue.

Usage:
  python3 scripts/search-vc-boards.py --all [--add]
  python3 scripts/search-vc-boards.py --board sequoia [--add]
"""

import argparse
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CHECK_DEDUP = os.path.join(SCRIPT_DIR, "check-dedup.py")
ADD_TO_QUEUE = os.path.join(SCRIPT_DIR, "add-to-queue.py")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) JobHunt/1.0"

VC_BOARDS = {
    # Explicit user-provided board URLs
    "generalcatalyst": {
        "name": "General Catalyst Jobs",
        "url": "https://jobs.generalcatalyst.com/jobs?filter=eyJqb2JfZnVuY3Rpb25zIjpbIkRhdGEgU2NpZW5jZSIsIlNvZnR3YXJlIEVuZ2luZWVyaW5nIl0sInNlbmlvcml0eSI6WyJtaWRfc2VuaW9yIiwic2VuaW9yIiwiYXNzb2NpYXRlIiwiZW50cnlfbGV2ZWwiXSwiY29tcGVuc2F0aW9uX2N1cnJlbmN5IjoiVVNEIiwiY29tcGVuc2F0aW9uX3BlcmlvZCI6InllYXIiLCJjb21wZW5zYXRpb25fYW1vdW50X21pbl9jZW50cyI6IjIwMDAwMDAwIiwiY29tcGVuc2F0aW9uX29mZmVyc19lcXVpdHkiOmZhbHNlfQ%3D%3D",
        "engine": "getro",
        "score": 80,
    },
    "khosla": {
        "name": "Khosla Ventures Jobs",
        "url": "https://jobs.khoslaventures.com/jobs?filter=eyJqb2JfZnVuY3Rpb25zIjpbIlNvZnR3YXJlIEVuZ2luZWVyaW5nIiwiRGF0YSBTY2llbmNlIl0sInNlbmlvcml0eSI6WyJlbnRyeV9sZXZlbCIsImFzc29jaWF0ZSIsIm1pZF9zZW5pb3IiLCJzZW5pb3IiXSwiY29tcGVuc2F0aW9uX2N1cnJlbmN5IjoiVVNEIiwiY29tcGVuc2F0aW9uX3BlcmlvZCI6InllYXIiLCJjb21wZW5zYXRpb25fYW1vdW50X21pbl9jZW50cyI6IjIwMDAwMDAwIiwiY29tcGVuc2F0aW9uX29mZmVyc19lcXVpdHkiOmZhbHNlfQ%3D%3D",
        "engine": "getro",
        "score": 80,
    },
    "sequoia": {
        "name": "Sequoia Jobs",
        "url": "https://jobs.sequoiacap.com/jobs?locations=United+States&skills=Artificial+Intelligence&postedSince=P1D",
        "engine": "consider",
        "score": 85,
    },
    "greylock": {
        "name": "Greylock Jobs",
        "url": "https://jobs.greylock.com/jobs?jobTypes=Engineer&jobTypes=Software+Engineer&skills=Artificial+Intelligence&skills=Machine+Learning&salaryCurrency=US+Dollar&salaryPeriod=Year&salaryMin=199000&salaryMax=500000",
        "engine": "consider",
        "score": 85,
    },
    "kleinerperkins": {
        "name": "Kleiner Perkins Jobs",
        "url": "https://jobs.kleinerperkins.com/jobs",
        "engine": "consider",
        "score": 80,
    },
    "bitkraft": {
        "name": "BITKRAFT Jobs",
        "url": "https://careers.bitkraft.vc/jobs",
        "engine": "getro",
        "score": 65,
    },
    "accel": {
        "name": "Accel Jobs",
        "url": "https://jobs.accel.com/jobs",
        "engine": "getro",
        "score": 80,
    },
    "contrary": {
        "name": "Contrary Jobs",
        "url": "https://jobs.contrary.com/jobs",
        "engine": "consider",
        "score": 70,
    },
    "battery": {
        "name": "Battery Ventures Jobs",
        "url": "https://jobs.battery.com/jobs",
        "engine": "consider",
        "score": 75,
    },
    "nea": {
        "name": "NEA Jobs",
        "url": "https://careers.nea.com/jobs",
        "engine": "consider",
        "score": 75,
    },
    "lightspeed": {
        "name": "Lightspeed Jobs",
        "url": "https://jobs.lsvp.com/jobs",
        "engine": "consider",
        "score": 80,
    },
    "bvp": {
        "name": "Bessemer Jobs",
        "url": "https://jobs.bvp.com/jobs",
        "engine": "consider",
        "score": 80,
    },
    "indexventures": {
        "name": "Index Ventures AI/ML Jobs",
        "url": "https://www.indexventures.com/startup-jobs/aiml/1",
        "engine": "index",
        "score": 75,
    },
    # Explicitly include a16z + YC as requested
    "a16z": {
        "name": "a16z Portfolio Jobs",
        "url": "https://portfoliojobs.a16z.com/jobs",
        "engine": "consider",
        "score": 90,
    },
    "yc": {
        "name": "Y Combinator Work at a Startup",
        "url": "https://www.workatastartup.com/jobs",
        "engine": "waas",
        "score": 85,
    },
}

RELEVANT_RE = re.compile(
    r"\b(ai|ml|machine.?learning|deep.?learning|research|scientist|engineer|"
    r"founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|"
    r"inference|data.?scientist|applied.?ai|generative|genai|multimodal|rlhf|alignment|safety|robotics)\b",
    re.I,
)

US_RE = re.compile(
    r"\b(united states|us|usa|remote|san francisco|new york|nyc|bay area|seattle|austin|boston|chicago|los angeles|palo alto|mountain view)\b",
    re.I,
)


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    with urllib.request.urlopen(req, timeout=40) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def post_json(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def extract_next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">([\s\S]*?)</script>', html)
    if not m:
        return None
    return json.loads(m.group(1))


def extract_server_initial_data(html):
    m = re.search(r"window\.serverInitialData\s*=\s*(\{[\s\S]*?\});\s*\n", html)
    if not m:
        return None
    return json.loads(m.group(1))


def jobs_from_getro(html):
    data = extract_next_data(html)
    if not data:
        return []
    found = (
        data.get("props", {})
        .get("pageProps", {})
        .get("initialState", {})
        .get("jobs", {})
        .get("found", [])
    )
    jobs = []
    for j in found:
        org = j.get("organization") or {}
        jobs.append(
            {
                "title": j.get("title", ""),
                "company": org.get("name", "").strip() or "Unknown",
                "location": ", ".join(j.get("locations") or []),
                "url": j.get("url", ""),
                "salary_min_usd": _to_usd_salary_from_getro(j),
                "published_at": j.get("createdAt", ""),
            }
        )
    return jobs


def _to_usd_salary_from_getro(j):
    cur = (j.get("compensationCurrency") or "").upper()
    min_cents = j.get("compensationConvertedAmountMinCents")
    if isinstance(min_cents, (int, float)):
        return int(min_cents / 100)
    if cur == "USD":
        raw = j.get("compensationAmountMinCents")
        if isinstance(raw, (int, float)):
            return int(raw / 100)
    return None


def jobs_from_consider(board_url):
    html = fetch_text(board_url)
    sid = extract_server_initial_data(html)
    if not sid:
        return []
    board = sid.get("board")
    if not board:
        return []

    host = urllib.parse.urlsplit(board_url).netloc
    endpoint = f"https://{host}/api-boards/search-jobs"
    payload = {"meta": {"size": 120}, "board": board, "query": {}, "grouped": False}
    data = post_json(endpoint, payload)

    jobs = []
    for j in data.get("jobs", []):
        salary = j.get("salary") or {}
        sal_min = salary.get("minValue")
        sal_currency = (salary.get("currency") or {}).get("value", "")
        salary_min_usd = int(sal_min) if isinstance(sal_min, (int, float)) and sal_currency == "USD" else None

        jobs.append(
            {
                "title": j.get("title", ""),
                "company": j.get("companyName", "").strip() or "Unknown",
                "location": ", ".join(j.get("locations") or []),
                "url": j.get("url", ""),
                "salary_min_usd": salary_min_usd,
                "published_at": j.get("createdAt", ""),
            }
        )
    return jobs


def jobs_from_waas(html):
    jobs = []
    # YC jobs have signup_job_id links; extract title from anchor text and infer company from nearby heading text.
    for m in re.finditer(r'<a[^>]*href="([^"]*signup_job_id=\d+[^"]*)"[^>]*>([\s\S]*?)</a>', html, re.I):
        href, inner = m.group(1), m.group(2)
        text = re.sub(r"<[^>]+>", " ", inner)
        title = re.sub(r"\s+", " ", text).strip()
        if not title:
            continue
        url = urllib.parse.urljoin("https://www.workatastartup.com", href)
        jobs.append(
            {
                "title": title[:220],
                "company": "YC Startup",
                "location": "US/Remote (unverified)",
                "url": url,
                "salary_min_usd": None,
                "published_at": "",
            }
        )
    return jobs


def jobs_from_index(html):
    # Index Ventures page is mostly client-rendered; fall back to any explicit startup job links found.
    jobs = []
    for m in re.finditer(r'href="([^"]*startup-jobs[^"]*)"', html, re.I):
        url = urllib.parse.urljoin("https://www.indexventures.com", m.group(1))
        jobs.append(
            {
                "title": "AI/ML Startup Jobs (Index Ventures)",
                "company": "Index Ventures Portfolio",
                "location": "US/Remote (filtered page)",
                "url": url,
                "salary_min_usd": None,
                "published_at": "",
            }
        )
        break
    return jobs


def is_relevant(job):
    text = f"{job.get('title','')} {job.get('company','')}"
    return bool(RELEVANT_RE.search(text))


def is_us_or_remote(job):
    return bool(US_RE.search(job.get("location", "")))


def salary_ok(job):
    sal = job.get("salary_min_usd")
    # Keep unknown salary; enforce floor only when known.
    if sal is None:
        return True
    return sal >= 150000


def recency_score(published_at):
    if not published_at:
        return 30
    try:
        dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).days
        if days <= 0:
            return 100
        if days <= 3:
            return 70
        if days <= 7:
            return 50
        if days <= 14:
            return 30
        return 10
    except Exception:
        return 30


def match_score(title):
    t = (title or "").lower()
    exact = ["research engineer", "research scientist", "founding engineer", "applied scientist"]
    strong = ["ml engineer", "machine learning engineer", "ai engineer", "software engineer", "data scientist"]
    for kw in exact:
        if kw in t:
            return 100
    for kw in strong:
        if kw in t:
            return 80
    return 50


def check_dedup(url):
    try:
        res = subprocess.run(["python3", CHECK_DEDUP, url], capture_output=True, text=True, timeout=7)
        return res.stdout.strip().startswith("DUPLICATE")
    except Exception:
        return False


def add_to_queue(entry):
    res = subprocess.run(["python3", ADD_TO_QUEUE, json.dumps(entry)], capture_output=True, text=True, timeout=10)
    return res.stdout.strip() or res.stderr.strip()


def run_board(slug, auto_add=False):
    cfg = VC_BOARDS[slug]
    name, url, engine, company_score = cfg["name"], cfg["url"], cfg["engine"], cfg["score"]
    try:
        html = fetch_text(url)
    except Exception as e:
        print(f"ERROR: {name} fetch failed: {e}")
        return 0, 0

    try:
        if engine == "getro":
            jobs = jobs_from_getro(html)
        elif engine == "consider":
            jobs = jobs_from_consider(url)
        elif engine == "waas":
            jobs = jobs_from_waas(html)
        elif engine == "index":
            jobs = jobs_from_index(html)
        else:
            jobs = []
    except Exception as e:
        print(f"ERROR: {name} parse failed: {e}")
        return 0, 0

    jobs = [j for j in jobs if j.get("url")]
    jobs = [j for j in jobs if is_relevant(j) and is_us_or_remote(j) and salary_ok(j)]

    print(f"FOUND {len(jobs)} relevant US/remote jobs on {name}")

    new_count = 0
    dup_count = 0
    for j in jobs:
        if check_dedup(j["url"]):
            dup_count += 1
            continue

        new_count += 1
        total = recency_score(j.get("published_at")) + 30 + company_score + match_score(j.get("title"))
        salary = f"${int(j['salary_min_usd']/1000)}K+" if isinstance(j.get("salary_min_usd"), int) else ""

        if auto_add:
            entry = {
                "score": total,
                "company": j.get("company", "Unknown"),
                "title": j.get("title", ""),
                "url": j.get("url", ""),
                "location": j.get("location", ""),
                "salary": salary,
                "companyInfo": name,
                "h1b": "Unknown",
                "source": f"{name} ({engine})",
                "scoreBreakdown": f"recency={recency_score(j.get('published_at'))} salary=30 company={company_score} match={match_score(j.get('title'))}",
                "whyMatch": f"Relevant AI/ML role from {name}",
                "autoApply": True,
            }
            out = add_to_queue(entry)
            if out:
                print(f"  {out}")
        else:
            print(f"  [{total}] {j.get('company')} — {j.get('title')} ({j.get('location')})")

    return new_count, dup_count


def main():
    ap = argparse.ArgumentParser(description="Search VC job boards and add relevant jobs")
    ap.add_argument("--all", action="store_true", help="Run all configured VC boards")
    ap.add_argument("--board", choices=sorted(VC_BOARDS.keys()), help="Run one board")
    ap.add_argument("--add", action="store_true", help="Add new jobs to queue")
    args = ap.parse_args()

    if not args.all and not args.board:
        ap.error("Specify --all or --board")

    boards = sorted(VC_BOARDS.keys()) if args.all else [args.board]
    total_new = 0
    total_dup = 0
    for slug in boards:
        new_count, dup_count = run_board(slug, auto_add=args.add)
        total_new += new_count
        total_dup += dup_count
        print()

    print(f"TOTAL: {total_new} new, {total_dup} duplicate across {len(boards)} VC boards")


if __name__ == "__main__":
    main()

