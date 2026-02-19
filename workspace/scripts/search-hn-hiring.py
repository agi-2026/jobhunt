#!/usr/bin/env python3
"""
Hacker News "Who is Hiring?" Scraper — Uses Algolia API.

Fetches the latest monthly "Who is Hiring?" thread and extracts AI/ML job posts.

Usage:
  python3 scripts/search-hn-hiring.py [--add]
  python3 scripts/search-hn-hiring.py --month 2026-02 [--add]

Output:
  FOUND 12 AI/ML jobs in HN "Who is Hiring?" (February 2026)
  [280] Acme AI — ML Engineer (San Francisco) https://news.ycombinator.com/item?id=12345
  ...
"""
import sys
import os
import json
import re
import subprocess
import html
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CHECK_DEDUP = os.path.join(SCRIPT_DIR, 'check-dedup.py')
ADD_TO_QUEUE = os.path.join(SCRIPT_DIR, 'add-to-queue.py')

AI_RE = re.compile(
    r'\b(ai|ml|machine.?learning|deep.?learning|research.?scientist|'
    r'llm|nlp|computer.?vision|reinforcement|rl|post.?train|pre.?train|'
    r'inference|applied.?ai|generative|genai|multimodal|rlhf|alignment|'
    r'founding.?engineer|robotics|autonomous)\b', re.I
)

TITLE_RE = re.compile(
    r'^(.+?)\s*[\|–—-]\s*(.+?)(?:\s*[\|–—-]\s*(.+?))?(?:\s*[\|–—-]\s*(.+?))?$'
)

SALARY_RE = re.compile(r'\$[\d,]+[kK]?\s*[-–]\s*\$?[\d,]+[kK]?|\$[\d,]+[kK]?\+', re.I)
LOCATION_RE = re.compile(r'\b(remote|onsite|hybrid|san francisco|sf|nyc|new york|bay area|seattle|austin|boston|chicago|los angeles|la)\b', re.I)
H1B_RE = re.compile(r'\bh-?1b\b|\bvisa.?sponsor', re.I)
EXCLUDE_RE = re.compile(r'\b(intern|internship|contractor|contract|part[\s-]?time)\b', re.IGNORECASE)

def fetch_latest_thread():
    """Find the latest 'Who is Hiring?' thread via Algolia API."""
    url = 'https://hn.algolia.com/api/v1/search?query=%22Who%20is%20Hiring%22&tags=story,ask_hn&hitsPerPage=5'
    req = Request(url, headers={'User-Agent': 'JobSearchAgent/1.0'})
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    # Find the most recent "Ask HN: Who is hiring?" thread
    for hit in data.get('hits', []):
        title = hit.get('title', '')
        if 'who is hiring' in title.lower() and 'ask hn' in title.lower():
            return hit['objectID'], title
    return None, None

def fetch_comments(thread_id, max_comments=500):
    """Fetch top-level comments from the thread."""
    url = f'https://hn.algolia.com/api/v1/search?tags=comment,story_{thread_id}&hitsPerPage={max_comments}'
    req = Request(url, headers={'User-Agent': 'JobSearchAgent/1.0'})
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data.get('hits', [])

def parse_posting(comment):
    """Extract company, title, location, salary from a HN hiring comment."""
    text = comment.get('comment_text', '')
    if not text:
        return None

    # Clean HTML
    text_clean = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()

    # Check AI/ML relevance
    if not AI_RE.search(text_clean):
        return None

    # First line usually has: Company | Role | Location | Remote
    first_line = text_clean.split('.')[0] if '.' in text_clean[:200] else text_clean[:200]

    # Try to parse structured format: "Company | Role | Location | ..."
    parts = re.split(r'\s*[\|–—]\s*', first_line)

    company = parts[0].strip()[:80] if parts else 'Unknown'
    title = parts[1].strip()[:80] if len(parts) > 1 else 'AI/ML Role'
    location = parts[2].strip()[:80] if len(parts) > 2 else ''

    # Skip internships, contractors, and part-time
    if EXCLUDE_RE.search(title) or EXCLUDE_RE.search(first_line):
        return None

    # Fallback location detection
    if not location:
        loc_match = LOCATION_RE.search(text_clean[:300])
        if loc_match:
            location = loc_match.group(0)

    # Salary
    sal_match = SALARY_RE.search(text_clean)
    salary = sal_match.group(0) if sal_match else ''

    # H-1B
    h1b = 'Mentioned' if H1B_RE.search(text_clean) else 'Unknown'

    hn_url = f'https://news.ycombinator.com/item?id={comment["objectID"]}'

    return {
        'company': company,
        'title': title,
        'location': location,
        'salary': salary,
        'h1b': h1b,
        'url': hn_url,
        'text_preview': text_clean[:300]
    }

def score_hn_job(job):
    """Score an HN job posting."""
    r = 100  # HN threads are monthly, always recent
    s = 30   # salary usually unclear from text
    if job.get('salary'):
        sal = job['salary'].replace(',', '').replace('k', '000').replace('K', '000')
        nums = re.findall(r'\d+', sal)
        if nums and int(nums[-1]) >= 200000:
            s = 80
        elif nums and int(nums[-1]) >= 150000:
            s = 60
    c = 70  # HN companies are usually startups (Series A-B)
    m = 60  # partial match (can't verify title precisely)

    title_lower = job.get('title', '').lower()
    if any(kw in title_lower for kw in ['research scientist', 'research engineer', 'founding engineer']):
        m = 100
    elif any(kw in title_lower for kw in ['ml engineer', 'ai engineer', 'machine learning']):
        m = 80

    total = r + s + c + m
    return total, f'recency={r} salary={s} company={c} match={m}'

def check_dedup(url):
    try:
        result = subprocess.run(
            ['python3', CHECK_DEDUP, url],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip().startswith('DUPLICATE')
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def add_to_queue(job_json):
    try:
        result = subprocess.run(
            ['python3', ADD_TO_QUEUE, json.dumps(job_json)],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f'ERROR: {e}'

def main():
    auto_add = '--add' in sys.argv

    thread_id, thread_title = fetch_latest_thread()
    if not thread_id:
        print('ERROR: Could not find latest "Who is Hiring?" thread')
        sys.exit(1)

    print(f'Thread: {thread_title} (id: {thread_id})')

    comments = fetch_comments(thread_id)
    print(f'Fetched {len(comments)} comments')

    jobs = []
    for c in comments:
        job = parse_posting(c)
        if job:
            jobs.append(job)

    print(f'FOUND {len(jobs)} AI/ML relevant postings\n')

    new_count = 0
    dup_count = 0

    for job in jobs:
        total, breakdown = score_hn_job(job)

        if check_dedup(job['url']):
            dup_count += 1
            continue

        new_count += 1

        if auto_add:
            entry = {
                'score': total,
                'company': job['company'],
                'title': job['title'],
                'url': job['url'],
                'location': job['location'] or 'Unknown',
                'salary': job['salary'],
                'companyInfo': 'HN Who is Hiring poster',
                'h1b': job['h1b'],
                'source': 'HN Who is Hiring',
                'scoreBreakdown': breakdown,
                'whyMatch': f'AI/ML role from HN hiring thread',
                'autoApply': False  # HN jobs need manual application
            }
            result = add_to_queue(entry)
            print(f'  {result}')
        else:
            print(f'  [{total}] {job["company"]} — {job["title"]} ({job["location"]}) {job["url"]}')
            if job['salary']:
                print(f'       Salary: {job["salary"]}')

    print(f'\nSummary: {new_count} new, {dup_count} duplicate')

    # Log yield for dynamic scheduling
    if auto_add:
        try:
            subprocess.run(
                ['python3', os.path.join(SCRIPT_DIR, 'log-yield.py'),
                 str(new_count), str(dup_count), 'HN Hiring'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

if __name__ == '__main__':
    main()
