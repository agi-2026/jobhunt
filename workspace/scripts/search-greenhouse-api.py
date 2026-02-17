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
    # Added 2026-02-16
    'togetherai': {'info': 'Open-source AI, model training/inference ($1.25B)', 'score': 90, 'h1b': 'Likely'},
    'fireworksai': {'info': 'AI inference platform ($4B, PyTorch founders)', 'score': 90, 'h1b': 'Likely'},
    'goodfire': {'info': 'AI interpretability ($1.25B, Anthropic-backed)', 'score': 80, 'h1b': 'Likely'},
    'runwayml': {'info': 'Generative AI for video ($4B, Google/NVIDIA)', 'score': 90, 'h1b': 'Likely'},
    'cerebrassystems': {'info': 'AI chip/compute ($23B, preparing IPO)', 'score': 90, 'h1b': 'Likely'},
    # perplexityai, meshy: slugs not found on Greenhouse API
    # Added 2026-02-16 (batch ATS detection — 38 companies)
    'heygen': {'info': 'AI video avatars ($440M, Benchmark)', 'score': 85, 'h1b': 'Likely'},
    'inflectionai': {'info': 'AI personal assistant, Pi ($1.5B, Gates/NVIDIA)', 'score': 90, 'h1b': 'Likely'},
    'xai': {'info': 'Elon Musk AI lab, Grok ($50B+)', 'score': 95, 'h1b': 'Likely'},
    'hebbia': {'info': 'AI knowledge work ($700M, a16z)', 'score': 85, 'h1b': 'Likely'},
    'sambanovasystems': {'info': 'AI hardware/cloud ($5B+)', 'score': 85, 'h1b': 'Likely'},
    'snorkelai': {'info': 'Data-centric AI ($1B+, Greylock)', 'score': 85, 'h1b': 'Likely'},
    'stackblitz': {'info': 'Web dev AI (Bolt, WebContainers)', 'score': 75, 'h1b': 'Likely'},
    'vivodyne': {'info': 'AI-driven biology ($55M, Founders Fund)', 'score': 70, 'h1b': 'Likely'},
    'cresta': {'info': 'AI contact center ($225M, Greylock)', 'score': 80, 'h1b': 'Likely'},
    'thatch': {'info': 'Health insurance tech ($48M)', 'score': 65, 'h1b': 'Likely'},
    'instawork': {'info': 'Gig economy AI marketplace ($160M)', 'score': 70, 'h1b': 'Likely'},
    'assemblyai': {'info': 'Speech-to-text AI ($115M)', 'score': 80, 'h1b': 'Likely'},
    'mindsdb': {'info': 'AI in databases ($75M)', 'score': 70, 'h1b': 'Likely'},
    'polyai': {'info': 'Enterprise voice AI ($64M, Khosla)', 'score': 80, 'h1b': 'Likely'},
    'marqvision': {'info': 'AI brand protection ($42M)', 'score': 65, 'h1b': 'Unknown'},
    'vizai': {'info': 'AI medical imaging ($252M, Tiger Global)', 'score': 75, 'h1b': 'Likely'},
    'optimaldynamics': {'info': 'AI logistics optimization ($70M, Coatue)', 'score': 70, 'h1b': 'Likely'},
    'labelbox': {'info': 'AI data labeling ($188M, a16z)', 'score': 80, 'h1b': 'Likely'},
    'veriff': {'info': 'AI identity verification ($100M+)', 'score': 70, 'h1b': 'Unknown'},
    'saltsecurity': {'info': 'API security AI ($271M, Sequoia)', 'score': 70, 'h1b': 'Likely'},
    'moveworks': {'info': 'IT AI automation ($305M, Sapphire)', 'score': 80, 'h1b': 'Likely'},
    'neuralink': {'info': 'Brain-computer interface (Elon Musk)', 'score': 90, 'h1b': 'Likely'},
    'dialpad': {'info': 'AI communications ($230M)', 'score': 75, 'h1b': 'Likely'},
    'dynotherapeutics': {'info': 'AI drug discovery, Harvard spinout', 'score': 70, 'h1b': 'Likely'},
    'dominodatalab': {'info': 'MLOps platform ($553M, Sequoia)', 'score': 80, 'h1b': 'Likely'},
    'observeai': {'info': 'Contact center AI ($214M, Zoom)', 'score': 75, 'h1b': 'Likely'},
    'sisense': {'info': 'Analytics AI ($360M, Insight)', 'score': 70, 'h1b': 'Likely'},
    'atomwise': {'info': 'AI drug discovery ($174M)', 'score': 70, 'h1b': 'Likely'},
    'graphcore': {'info': 'AI accelerator chips ($700M, SoftBank)', 'score': 80, 'h1b': 'Likely'},
    'iris': {'info': 'Drone AI detect-and-avoid ($50M)', 'score': 70, 'h1b': 'Likely'},
    'pindropsecurity': {'info': 'Voice fraud AI ($213M, Citi)', 'score': 70, 'h1b': 'Likely'},
    'stripe': {'info': 'Payments/fintech ($65B, AI features)', 'score': 90, 'h1b': 'Confirmed'},
    'dropbox': {'info': 'Cloud storage, Dash AI ($8B mcap)', 'score': 80, 'h1b': 'Confirmed'},
    'pinterest': {'info': 'Visual discovery, AI search ($17B mcap)', 'score': 80, 'h1b': 'Confirmed'},
    'waymo': {'info': 'Autonomous vehicles (Alphabet)', 'score': 90, 'h1b': 'Confirmed'},
    'robinhood': {'info': 'Fintech, AI features ($20B+ mcap)', 'score': 80, 'h1b': 'Confirmed'},
    'duolingo': {'info': 'AI language learning ($12B mcap)', 'score': 80, 'h1b': 'Confirmed'},
    'linkedin': {'info': 'Professional network (Microsoft)', 'score': 80, 'h1b': 'Confirmed'},
    # VC portfolio companies (a16z + Sequoia, detected 2026-02-16)
    'descript': {'info': 'AI video/audio editing (a16z)', 'score': 80, 'h1b': 'Likely'},
    'fal': {'info': 'AI inference infrastructure (Sequoia)', 'score': 85, 'h1b': 'Likely'},
    'gensyn': {'info': 'Distributed ML compute (Sequoia)', 'score': 80, 'h1b': 'Likely'},
    'chainguard': {'info': 'Supply chain security (Sequoia)', 'score': 70, 'h1b': 'Likely'},
    'metronome': {'info': 'Product launch/pricing platform (Sequoia)', 'score': 65, 'h1b': 'Likely'},
    'gleanwork': {'info': 'Enterprise AI search ($150M Series F, Sequoia)', 'score': 90, 'h1b': 'Confirmed'},
    'hextechnologies': {'info': 'Data science/analytics workspace (a16z+Sequoia)', 'score': 75, 'h1b': 'Likely'},
    'blackforestlabs': {'info': 'Flux image generation models (a16z)', 'score': 95, 'h1b': 'Likely'},
    # Added 2026-02-17
    'vectranetworks': {'info': 'AI cybersecurity/threat detection ($200M+)', 'score': 70, 'h1b': 'Likely'},
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

def is_us_or_remote(job):
    """Filter for US locations or remote roles accessible from the US."""
    location = job.get('location', {}).get('name', '').lower()

    # Non-US locations — skip
    non_us = ['united kingdom', 'london', 'uk', 'germany', 'berlin', 'munich',
              'france', 'paris', 'japan', 'tokyo', 'india', 'bangalore', 'mumbai',
              'brazil', 'australia', 'sydney', 'china', 'shanghai', 'beijing',
              'israel', 'tel aviv', 'netherlands', 'amsterdam', 'ireland', 'dublin',
              'sweden', 'stockholm', 'spain', 'madrid', 'italy', 'milan',
              'singapore', 'canada', 'toronto', 'vancouver', 'korea', 'seoul',
              'dubai', 'uae', 'switzerland', 'zurich', 'poland', 'warsaw',
              'portugal', 'lisbon', 'czech', 'prague', 'argentina', 'mexico',
              'colombia', 'chile', 'south africa', 'nigeria', 'kenya',
              'taiwan', 'hong kong', 'vietnam', 'thailand', 'philippines',
              'indonesia', 'malaysia', 'new zealand', 'denmark', 'copenhagen',
              'norway', 'oslo', 'finland', 'helsinki', 'austria', 'vienna',
              'belgium', 'brussels', 'romania', 'bucharest', 'hungary', 'budapest']
    if any(kw in location for kw in non_us):
        return False

    # US keywords
    us_keywords = ['united states', 'san francisco', 'new york', 'nyc',
                   'bay area', 'seattle', 'austin', 'boston', 'chicago', 'los angeles',
                   'palo alto', 'mountain view', 'menlo park', 'sunnyvale',
                   'washington', 'denver', 'portland', 'atlanta', 'miami',
                   'philadelphia', 'phoenix', 'dallas', 'houston', 'san jose',
                   'san diego', 'pittsburgh', 'boulder', 'raleigh', 'durham',
                   'cambridge', 'somerville', 'brooklyn', 'manhattan',
                   ', ca', ', ny', ', wa', ', tx', ', ma', ', il', ', co',
                   ', pa', ', ga', ', fl', ', va', ', nc', ', or', ', az',
                   ', ut', ', md', ', oh', ', mn', ', mi', ', ct', ', nj',
                   'usa', 'u.s.']
    if any(kw in location for kw in us_keywords):
        return True

    # Remote with no explicit non-US indicator
    if 'remote' in location:
        return True

    # Empty or ambiguous location — include (some companies don't set location)
    if not location or location == 'unknown':
        return True

    return False

def search_company(slug, auto_add):
    """Search a single company and return (new_count, dup_count)."""
    all_jobs = fetch_jobs(slug)
    if not all_jobs:
        print(f'No jobs found for {slug}')
        return 0, 0

    relevant = [j for j in all_jobs if is_relevant(j) and is_us_or_remote(j)]
    company_name = all_jobs[0].get('company_name', slug) if all_jobs else slug
    info = COMPANY_INFO.get(slug, {})

    print(f'FOUND {len(relevant)} relevant US/remote jobs at {company_name} (of {len(all_jobs)} total)')

    new_count = 0
    dup_count = 0

    for job in relevant:
        url = job.get('absolute_url', '')
        title = job.get('title', '')
        location = job.get('location', {}).get('name', 'Unknown')
        total, breakdown = score_job(job, slug)

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

    if auto_add:
        try:
            subprocess.run(
                ['python3', os.path.join(SCRIPT_DIR, 'log-yield.py'),
                 str(new_count), str(dup_count), f'Greenhouse:{slug}'],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

    return new_count, dup_count


def main():
    auto_add = '--add' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]

    if '--all' in sys.argv:
        total_new = 0
        total_dup = 0
        for slug in COMPANY_INFO:
            new, dup = search_company(slug, auto_add)
            total_new += new
            total_dup += dup
        print(f'\nTOTAL: {total_new} new, {total_dup} duplicate across {len(COMPANY_INFO)} companies')
    elif args:
        slug = args[0].strip().lower()
        search_company(slug, auto_add)
    else:
        print('Usage: python3 search-greenhouse-api.py <company-slug> [--add]')
        print('       python3 search-greenhouse-api.py --all [--add]')
        sys.exit(1)

if __name__ == '__main__':
    main()
