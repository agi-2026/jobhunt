#!/usr/bin/env python3
"""
Greenhouse API Search — No browser needed!

Fetches jobs from Greenhouse's public API, filters for AI/ML relevance,
checks dedup, and outputs ready-to-queue JSON.

Usage:
  python3 scripts/search-greenhouse-api.py <company-slug> [--add]

  company-slug: The Greenhouse board slug (e.g., "anthropic", "thinkingmachines", "scaleai")
  --add: Auto-add new relevant jobs to queue via add-to-queue.py

Examples:
  python3 scripts/search-greenhouse-api.py anthropic
  python3 scripts/search-greenhouse-api.py thinkingmachines --add
  python3 scripts/search-greenhouse-api.py scaleai --add

Output (without --add):
  FOUND 5 relevant jobs at Anthropic (of 451 total)
  [350] Anthropic — Research Engineer (San Francisco, CA) https://job-boards.greenhouse.io/anthropic/jobs/123
  [320] Anthropic — ML Engineer, Post-Training (San Francisco, CA) https://job-boards.greenhouse.io/anthropic/jobs/456
  ...

Output (with --add):
  ADDED [350] Anthropic — Research Engineer (5 new, 2 duplicate, 48 pending)
  DUPLICATE — Anthropic — ML Engineer already in queue
  ...
"""
import sys
import os
import json
import re
import subprocess
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_DEDUP = os.path.join(SCRIPT_DIR, 'check-dedup.py')
ADD_TO_QUEUE = os.path.join(SCRIPT_DIR, 'add-to-queue.py')

RELEVANT_RE = re.compile(
    r'\b(ai|ml|machine.?learning|deep.?learning|research|scientist|'
    r'founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|'
    r'pre.?train|inference|data.?scientist|applied.?ai|generative|genai|'
    r'multimodal|rlhf|alignment|safety|robotics|autonomous)\b', re.I
)

# Company info for scoring
COMPANY_INFO = {
    'anthropic': {'info': 'Top AI lab ($380B valuation)', 'score': 100, 'h1b': 'Confirmed'},
    'thinkingmachines': {'info': 'Frontier AI lab, Mira Murati ($2B raised)', 'score': 100, 'h1b': 'Likely'},
    'scaleai': {'info': 'Data/AI platform ($13.8B valuation)', 'score': 90, 'h1b': 'Confirmed'},
    'gleanwork': {'info': 'Work AI ($4.6B valuation)', 'score': 90, 'h1b': 'Likely'},
    'blackforestlabs': {'info': 'Stable Diffusion creators, FLUX', 'score': 80, 'h1b': 'Unknown'},
    'deepmind': {'info': 'Google DeepMind, top AI lab', 'score': 100, 'h1b': 'Confirmed'},
    'recursionpharmaceuticals': {'info': 'AI biotech ($6B mcap)', 'score': 80, 'h1b': 'Likely'},
}

def fetch_jobs(slug):
    """Fetch all jobs from Greenhouse API."""
    url = f'https://api.greenhouse.io/v1/boards/{slug}/jobs?content=true'
    req = Request(url, headers={'User-Agent': 'JobSearchAgent/1.0'})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get('jobs', [])
    except HTTPError as e:
        print(f'ERROR: HTTP {e.code} for {slug} — board may not exist')
        sys.exit(1)
    except URLError as e:
        print(f'ERROR: Network error — {e.reason}')
        sys.exit(1)

def is_relevant(job):
    """Check if job title/content matches AI/ML keywords."""
    text = job.get('title', '')
    # Also check department metadata if available
    for m in (job.get('metadata') or []):
        if m.get('value'):
            text += ' ' + str(m['value'])
    return bool(RELEVANT_RE.search(text))

def recency_score(job):
    """Score based on how recently the job was published."""
    published = job.get('first_published') or job.get('updated_at', '')
    if not published:
        return 30  # unknown
    try:
        # Parse ISO date like "2026-02-12T17:50:57-05:00"
        pub_date = datetime.fromisoformat(published)
        now = datetime.now(pub_date.tzinfo)
        days = (now - pub_date).days
        if days <= 0: return 100
        if days <= 3: return 70
        if days <= 7: return 50
        if days <= 14: return 30
        return 10
    except (ValueError, TypeError):
        return 30

def match_score(title):
    """Score based on title match to Howard's preferences."""
    title_lower = title.lower()
    exact = ['research scientist', 'research engineer', 'founding engineer', 'ai team lead']
    strong = ['ml engineer', 'machine learning engineer', 'ai engineer', 'applied scientist',
              'post-training', 'pre-training', 'rlhf', 'alignment']
    partial = ['software engineer', 'data scientist', 'inference engineer']

    for kw in exact:
        if kw in title_lower:
            return 100
    for kw in strong:
        if kw in title_lower:
            return 80
    for kw in partial:
        if kw in title_lower:
            return 60
    return 40  # adjacent

def score_job(job, slug):
    """Calculate total score for a job."""
    r = recency_score(job)
    s = 30  # salary usually not in listing
    c = COMPANY_INFO.get(slug, {}).get('score', 70)
    m = match_score(job.get('title', ''))
    return r + s + c + m, f'recency={r} salary={s} company={c} match={m}'

def check_dedup(url):
    """Check if URL is already known via check-dedup.py."""
    try:
        result = subprocess.run(
            ['python3', CHECK_DEDUP, url],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip().startswith('DUPLICATE')
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def add_to_queue(job_json):
    """Add job to queue via add-to-queue.py."""
    try:
        result = subprocess.run(
            ['python3', ADD_TO_QUEUE, json.dumps(job_json)],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f'ERROR: {e}'

def main():
    if len(sys.argv) < 2:
        print('Usage: python3 search-greenhouse-api.py <company-slug> [--add]')
        print('Example: python3 search-greenhouse-api.py anthropic --add')
        sys.exit(1)

    slug = sys.argv[1].strip().lower()
    auto_add = '--add' in sys.argv

    # Fetch all jobs
    all_jobs = fetch_jobs(slug)
    if not all_jobs:
        print(f'No jobs found for {slug}')
        sys.exit(0)

    # Filter relevant
    relevant = [j for j in all_jobs if is_relevant(j)]

    company_name = all_jobs[0].get('company_name', slug) if all_jobs else slug
    info = COMPANY_INFO.get(slug, {})

    print(f'FOUND {len(relevant)} relevant jobs at {company_name} (of {len(all_jobs)} total)')

    new_count = 0
    dup_count = 0

    for job in relevant:
        url = job.get('absolute_url', '')
        title = job.get('title', '')
        location = job.get('location', {}).get('name', 'Unknown')
        total, breakdown = score_job(job, slug)

        # Check dedup
        if check_dedup(url):
            dup_count += 1
            if not auto_add:
                print(f'  DUPLICATE [{total}] {company_name} — {title}')
            continue

        new_count += 1

        if auto_add:
            entry = {
                'score': total,
                'company': company_name,
                'title': title,
                'url': url,
                'location': location,
                'salary': '',
                'companyInfo': info.get('info', ''),
                'h1b': info.get('h1b', 'Unknown'),
                'source': 'Greenhouse API',
                'scoreBreakdown': breakdown,
                'whyMatch': f'Relevant AI/ML role at {company_name}',
                'autoApply': True
            }
            result = add_to_queue(entry)
            print(f'  {result}')
        else:
            print(f'  [{total}] {company_name} — {title} ({location}) {url}')

    print(f'\nSummary: {new_count} new, {dup_count} duplicate (of {len(relevant)} relevant)')

if __name__ == '__main__':
    main()
