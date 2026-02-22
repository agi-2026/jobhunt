#!/usr/bin/env python3
"""
Lever API Search — No browser needed!

Fetches jobs from Lever's public posting API, filters for AI/ML relevance,
checks dedup, and outputs ready-to-queue JSON.

Usage:
  python3 scripts/search-lever-api.py <company-slug> [--add]
  python3 scripts/search-lever-api.py --all [--add]

  company-slug: The Lever board slug (e.g., "mistral", "palantir")
  --all: Search all known Lever companies
  --add: Auto-add new relevant jobs to queue via add-to-queue.py

Examples:
  python3 scripts/search-lever-api.py mistral --add
  python3 scripts/search-lever-api.py --all --add
"""
import sys
import os
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
CHECK_DEDUP = os.path.join(SCRIPT_DIR, 'check-dedup.py')
ADD_TO_QUEUE = os.path.join(SCRIPT_DIR, 'add-to-queue.py')

API_BASE = 'https://api.lever.co/v0/postings'

RELEVANT_RE = re.compile(
    r'\b(ai|ml|machine.?learning|deep.?learning|research|scientist|'
    r'founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|'
    r'pre.?train|inference|data.?scientist|applied.?ai|generative|genai|'
    r'multimodal|rlhf|alignment|safety|robotics|autonomous)\b', re.I
)

# Known Lever companies with metadata
COMPANY_INFO = {
    'mistral': {'name': 'Mistral AI', 'info': 'Frontier AI lab ($6.2B valuation)', 'score': 100, 'h1b': 'Likely'},
    'palantir': {'name': 'Palantir', 'info': 'Data analytics ($50B+ mcap)', 'score': 80, 'h1b': 'Confirmed'},
    'zoox': {'name': 'Zoox (Amazon)', 'info': 'Autonomous vehicles, Amazon subsidiary', 'score': 80, 'h1b': 'Confirmed'},
    # Added 2026-02-16
    'hive': {'name': 'Hive', 'info': 'Cloud AI platform ($2B+, General Catalyst)', 'score': 80, 'h1b': 'Likely'},
    # 'laminiai': removed — slug not found on Lever
    'genbio': {'name': 'GenBio AI', 'info': 'Foundation models for biology', 'score': 70, 'h1b': 'Likely'},
    'trellis': {'name': 'Trellis', 'info': 'AI document processing (YC-backed)', 'score': 70, 'h1b': 'Likely'},
    # Added 2026-02-16 (batch ATS detection — 8 companies)
    'shieldai': {'name': 'Shield AI', 'info': 'Autonomous defense ($4B+, a16z)', 'score': 85, 'h1b': 'Likely'},
    'kumo': {'name': 'Kumo', 'info': 'Graph neural network AI ($110M, Sequoia)', 'score': 80, 'h1b': 'Likely'},
    'vergesense': {'name': 'VergeSense', 'info': 'Workplace analytics AI ($67M)', 'score': 65, 'h1b': 'Unknown'},
    'osaro': {'name': 'Osaro', 'info': 'Robotic AI perception ($40M)', 'score': 75, 'h1b': 'Likely'},
    'deepgenomics': {'name': 'Deep Genomics', 'info': 'AI therapeutics ($180M)', 'score': 75, 'h1b': 'Likely'},
    'rigetti': {'name': 'Rigetti Computing', 'info': 'Quantum computing ($2B raised)', 'score': 75, 'h1b': 'Likely'},
    'weride': {'name': 'WeRide', 'info': 'Autonomous vehicles ($5B mcap)', 'score': 80, 'h1b': 'Likely'},
    'curai': {'name': 'Curai Health', 'info': 'AI primary care ($43M, Khosla)', 'score': 70, 'h1b': 'Likely'},
    # VC portfolio companies (a16z + Sequoia, detected 2026-02-16)
    # 'shieldai' duplicate removed — already above
    # Added 2026-02-17 (batch Lever expansion — 20 companies)
    'field-ai': {'name': 'Field AI', 'info': 'Robotics + foundation models, autonomous systems', 'score': 85, 'h1b': 'Likely'},
    'collate': {'name': 'Collate', 'info': 'AI doc generation for life sciences (YC, Redpoint, $30M+)', 'score': 80, 'h1b': 'Likely'},
    'connectly': {'name': 'Connectly', 'info': 'AI conversational commerce, Series B (Meta/Google team)', 'score': 75, 'h1b': 'Likely'},
    'asapp-2': {'name': 'ASAPP', 'info': 'Real-time voice AI platform, ASR/TTS', 'score': 80, 'h1b': 'Likely'},
    'woven-by-toyota': {'name': 'Woven by Toyota', 'info': 'Autonomous driving, world foundation models', 'score': 85, 'h1b': 'Confirmed'},
    'voleon': {'name': 'The Voleon Group', 'info': 'AI/ML for quantitative finance', 'score': 80, 'h1b': 'Likely'},
    'artera': {'name': 'Artera', 'info': 'Medical AI, deep learning biomarkers for cancer', 'score': 75, 'h1b': 'Likely'},
    'glass-health-inc': {'name': 'Glass Health', 'info': 'AI clinical decision support (YC, $6.5M)', 'score': 75, 'h1b': 'Likely'},
    'AIFund': {'name': 'AI Fund', 'info': "Andrew Ng's venture studio, multi-portfolio AI", 'score': 80, 'h1b': 'Likely'},
    'Regard': {'name': 'Regard', 'info': 'Generative AI for clinical healthcare', 'score': 75, 'h1b': 'Likely'},
    'matchgroup': {'name': 'Match Group', 'info': 'AI-first dating (Tinder/Hinge), recommendation ML', 'score': 75, 'h1b': 'Confirmed'},
    'RadicalAI': {'name': 'Radical AI', 'info': 'AI for materials science, generative models', 'score': 80, 'h1b': 'Likely'},
    'npowermedicine': {'name': 'N-Power Medicine', 'info': 'AI-driven clinical trials', 'score': 70, 'h1b': 'Likely'},
    'imo-online': {'name': 'IMO Health', 'info': 'AI healthcare decision-making', 'score': 70, 'h1b': 'Likely'},
    'appzen': {'name': 'AppZen', 'info': 'Deep learning NLP/document AI for finance', 'score': 70, 'h1b': 'Likely'},
    'pryon': {'name': 'Pryon', 'info': 'Generative + agentic AI, enterprise knowledge', 'score': 75, 'h1b': 'Likely'},
    'quizlet-2': {'name': 'Quizlet', 'info': 'AI-powered learning, RL/personalization', 'score': 70, 'h1b': 'Likely'},
    'apolloresearch': {'name': 'Apollo Research', 'info': 'AI safety evals, frontier model research', 'score': 80, 'h1b': 'Likely'},
    'dexterity': {'name': 'Dexterity', 'info': 'CV + ML for robotic manipulation', 'score': 80, 'h1b': 'Likely'},
    'rivr': {'name': 'RIVR', 'info': 'Wheeled-legged robotics, imitation learning', 'score': 70, 'h1b': 'Likely'},
    # Added 2026-02-21 (batch expansion)
    'levelai': {'name': 'Level AI', 'info': 'NLP/ML for contact center intelligence, conversational AI', 'score': 75, 'h1b': 'Likely'},
    'wisdomai': {'name': 'WisdomAI', 'info': 'LLM-based code generation and document understanding', 'score': 80, 'h1b': 'Likely'},
    'Hume': {'name': 'Hume AI', 'info': 'Empathic AI, speech-language models, RL from human feedback ($50M+)', 'score': 80, 'h1b': 'Likely'},
    'valence': {'name': 'Valence', 'info': 'AI coaching platform for enterprises (Series B)', 'score': 65, 'h1b': 'Likely'},
}

def fetch_jobs(slug):
    """Fetch all jobs from Lever API."""
    url = f'{API_BASE}/{slug}'
    req = Request(url, headers={'User-Agent': 'JobSearchAgent/1.0'})
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            if isinstance(data, list):
                return data
            # Error response is a dict
            if isinstance(data, dict) and not data.get('ok', True):
                print(f'ERROR: {data.get("error", "unknown")} for {slug}')
                return []
            return []
    except HTTPError as e:
        if e.code == 404:
            print(f'ERROR: {slug} not found on Lever')
        else:
            print(f'ERROR: HTTP {e.code} for {slug}')
        return []
    except URLError as e:
        print(f'ERROR: Network error — {e.reason}')
        return []

def is_relevant(job):
    """Check if job title/team matches AI/ML keywords."""
    text = ' '.join([
        job.get('text', ''),
        job.get('categories', {}).get('team', ''),
    ])
    return bool(RELEVANT_RE.search(text))

def recency_score(job):
    """Score based on how recently the job was created."""
    created = job.get('createdAt')
    if not created:
        return 30
    try:
        pub_date = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        days = (now - pub_date).days
        if days <= 0: return 100
        if days <= 3: return 70
        if days <= 7: return 50
        if days <= 14: return 30
        return 10
    except (ValueError, TypeError, OSError):
        return 30

def match_score(title):
    """Score based on title match to preferences."""
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
    return 40

def score_job(job, slug):
    """Calculate total score for a job."""
    r = recency_score(job)
    s = 30
    c = COMPANY_INFO.get(slug, {}).get('score', 70)
    m = match_score(job.get('text', ''))
    return r + s + c + m, f'recency={r} salary={s} company={c} match={m}'

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

def is_us_or_remote(job):
    """Filter for US locations or remote roles."""
    location = job.get('categories', {}).get('location', '').lower()
    all_locations = job.get('categories', {}).get('allLocations', [])
    workplace = job.get('workplaceType', '').lower()
    country = (job.get('country') or '').upper()

    if workplace == 'remote' or 'remote' in location:
        return True
    if country == 'US':
        return True
    us_keywords = ['united states', 'us', 'usa', 'san francisco', 'new york', 'nyc',
                   'bay area', 'seattle', 'austin', 'boston', 'chicago', 'los angeles',
                   'palo alto', 'mountain view', 'menlo park', 'sunnyvale']
    if any(kw in location for kw in us_keywords):
        return True
    for loc in all_locations:
        if any(kw in loc.lower() for kw in us_keywords):
            return True
    return False

def search_company(slug, auto_add=False):
    """Search a single Lever company. Returns (new_count, dup_count)."""
    all_jobs = fetch_jobs(slug)
    if not all_jobs:
        print(f'No jobs found for {slug}')
        return 0, 0

    info = COMPANY_INFO.get(slug, {})
    company_name = info.get('name', slug)

    relevant = [j for j in all_jobs if is_relevant(j) and is_us_or_remote(j)]

    print(f'FOUND {len(relevant)} relevant US/remote jobs at {company_name} (of {len(all_jobs)} total)')

    if not relevant:
        return 0, 0

    # Batch score with Claude for semantic relevance
    from claude_scorer import batch_score_jobs, RELEVANCE_THRESHOLD
    claude_input = [{'title': j.get('text', ''), 'company': company_name,
                     'team': j.get('categories', {}).get('team', '')}
                    for j in relevant]
    claude_scores = batch_score_jobs(claude_input)

    new_count = 0
    dup_count = 0
    filtered_count = 0

    for job, cscore in zip(relevant, claude_scores):
        url = job.get('hostedUrl', '')
        title = job.get('text', '')
        location = job.get('categories', {}).get('location', 'Unknown')
        workplace = job.get('workplaceType', '')
        if workplace == 'remote':
            location = f"{location} (Remote)" if location else "Remote"

        # Filter by Claude relevance
        if not cscore['relevant']:
            filtered_count += 1
            print(f'  FILTERED [{cscore["score"]}] {company_name} — {title} | {cscore["reason"]}')
            continue

        # Score using Claude match score
        r = recency_score(job)
        s = 30
        c = COMPANY_INFO.get(slug, {}).get('score', 70)
        m = cscore['score']
        total = r + s + c + m
        breakdown = f'recency={r} salary={s} company={c} match={m}(claude:{cscore["reason"]})'

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
                'source': 'Lever API',
                'scoreBreakdown': breakdown,
                'whyMatch': cscore['reason'],
                'autoApply': True
            }
            result = add_to_queue(entry)
            print(f'  {result}')
        else:
            print(f'  [{total}] {company_name} — {title} ({location}) {url}')

    if filtered_count:
        print(f'  (Claude filtered {filtered_count} irrelevant jobs)')

    return new_count, dup_count

def main():
    args = sys.argv[1:]
    auto_add = '--add' in args
    search_all = '--all' in args
    args = [a for a in args if not a.startswith('--')]

    if search_all:
        total_new = 0
        total_dup = 0
        for slug in COMPANY_INFO:
            new, dup = search_company(slug, auto_add)
            total_new += new
            total_dup += dup
            print()
        print(f'TOTAL: {total_new} new, {total_dup} duplicate across {len(COMPANY_INFO)} companies')
        new_count, dup_count = total_new, total_dup
        source = 'Lever API (all)'
    elif args:
        slug = args[0].strip().lower()
        new_count, dup_count = search_company(slug, auto_add)
        print(f'\nSummary: {new_count} new, {dup_count} duplicate')
        source = f'Lever:{slug}'
    else:
        print('Usage: python3 search-lever-api.py <company-slug> [--add]')
        print('       python3 search-lever-api.py --all [--add]')
        print(f'\nKnown companies: {", ".join(COMPANY_INFO.keys())}')
        sys.exit(1)

    # Log yield for dynamic scheduling
    if auto_add:
        try:
            subprocess.run(
                ['python3', os.path.join(SCRIPT_DIR, 'log-yield.py'),
                 str(new_count), str(dup_count), source],
                capture_output=True, timeout=5
            )
        except Exception:
            pass

if __name__ == '__main__':
    main()
