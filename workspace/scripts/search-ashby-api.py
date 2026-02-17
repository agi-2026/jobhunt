#!/usr/bin/env python3
"""
Ashby API Search — No browser needed!

Fetches jobs from Ashby's public posting API, filters for AI/ML relevance,
checks dedup, and outputs ready-to-queue JSON.

Usage:
  python3 scripts/search-ashby-api.py <company-slug> [--add]
  python3 scripts/search-ashby-api.py --all [--add]

  company-slug: The Ashby board slug (e.g., "cohere", "magic.dev", "openai")
  --all: Search all known Ashby companies
  --add: Auto-add new relevant jobs to queue via add-to-queue.py

Examples:
  python3 scripts/search-ashby-api.py cohere
  python3 scripts/search-ashby-api.py magic.dev --add
  python3 scripts/search-ashby-api.py --all --add
"""
import sys
import os
import json
import re
import subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_DEDUP = os.path.join(SCRIPT_DIR, 'check-dedup.py')
ADD_TO_QUEUE = os.path.join(SCRIPT_DIR, 'add-to-queue.py')

API_BASE = 'https://api.ashbyhq.com/posting-api/job-board'

RELEVANT_RE = re.compile(
    r'\b(ai|ml|machine.?learning|deep.?learning|research|scientist|'
    r'founding|llm|nlp|computer.?vision|reinforcement|rl|post.?train|'
    r'pre.?train|inference|data.?scientist|applied.?ai|generative|genai|'
    r'multimodal|rlhf|alignment|safety|robotics|autonomous)\b', re.I
)

# Known Ashby companies with metadata for scoring
COMPANY_INFO = {
    # OpenAI removed — 5-app/180-day limit, Howard applies manually
    'cohere': {'name': 'Cohere', 'info': 'Frontier LLM lab ($6.8B valuation)', 'score': 90, 'h1b': 'Likely'},
    'magic.dev': {'name': 'Magic AI', 'info': 'AGI/code ($465M raised, Sequoia/a16z)', 'score': 90, 'h1b': 'Likely'},
    'sesame': {'name': 'Sesame AI', 'info': 'AI voice ($307M, Oculus founders)', 'score': 80, 'h1b': 'Likely'},
    'moonvalley-ai': {'name': 'Moonvalley AI', 'info': 'AI video ($84M, YC W24)', 'score': 80, 'h1b': 'Likely'},
    'liquid-ai': {'name': 'Liquid AI', 'info': 'MIT spinout, LFMs ($250M+)', 'score': 80, 'h1b': 'Likely'},
    'fastino-ai': {'name': 'Fastino.ai', 'info': 'Consumer GPU LLMs, Khosla-backed', 'score': 70, 'h1b': 'Unknown'},
    'basis-ai': {'name': 'Basis AI', 'info': 'AI agents for accounting, Khosla $34M', 'score': 70, 'h1b': 'Unknown'},
    'anyscale': {'name': 'Anyscale', 'info': 'Ray framework, AI infra', 'score': 80, 'h1b': 'Likely'},
    # Added 2026-02-16
    'harvey': {'name': 'Harvey', 'info': 'Legal AI ($8B valuation, Sequoia/a16z)', 'score': 90, 'h1b': 'Likely'},
    'writer': {'name': 'Writer', 'info': 'Enterprise generative AI ($1.9B)', 'score': 80, 'h1b': 'Likely'},
    'exa': {'name': 'Exa', 'info': 'AI-native search ($700M, Benchmark/YC)', 'score': 80, 'h1b': 'Likely'},
    'chaidiscovery': {'name': 'Chai Discovery', 'info': 'AI drug discovery ($1.3B, OpenAI-backed)', 'score': 80, 'h1b': 'Likely'},
    'character': {'name': 'Character.AI', 'info': 'Conversational AI (~$5B, Google-backed)', 'score': 90, 'h1b': 'Likely'},
    'livekit': {'name': 'LiveKit', 'info': 'Real-time AI infra ($1B, powers OpenAI voice)', 'score': 80, 'h1b': 'Likely'},
    'decagon': {'name': 'Decagon', 'info': 'AI customer agents ($4.5B, Accel/a16z)', 'score': 80, 'h1b': 'Likely'},
    # Added 2026-02-16 (batch ATS detection — 59 companies)
    'cognition': {'name': 'Cognition AI', 'info': 'Devin AI coding agent ($2B)', 'score': 95, 'h1b': 'Likely'},
    'perplexity': {'name': 'Perplexity AI', 'info': 'AI search engine ($9B, Bezos/NVIDIA)', 'score': 95, 'h1b': 'Likely'},
    'ssi': {'name': 'Safe Superintelligence', 'info': 'Ilya Sutskever, safety-focused AGI ($5B)', 'score': 100, 'h1b': 'Likely'},
    'mercor': {'name': 'Mercor', 'info': 'AI hiring platform ($2B, Benchmark)', 'score': 80, 'h1b': 'Likely'},
    'abridge': {'name': 'Abridge', 'info': 'AI medical documentation ($850M)', 'score': 80, 'h1b': 'Likely'},
    'baseten': {'name': 'Baseten', 'info': 'ML model inference infra ($220M)', 'score': 80, 'h1b': 'Likely'},
    'crusoe': {'name': 'Crusoe', 'info': 'AI cloud/data centers ($3.4B)', 'score': 85, 'h1b': 'Likely'},
    'coactive': {'name': 'Coactive AI', 'info': 'Unstructured data AI ($63M, a16z)', 'score': 75, 'h1b': 'Likely'},
    'figure': {'name': 'Figure AI', 'info': 'Humanoid robots ($2.6B, Bezos/NVIDIA)', 'score': 90, 'h1b': 'Likely'},
    'elevenlabs': {'name': 'ElevenLabs', 'info': 'AI voice/audio ($3.3B)', 'score': 90, 'h1b': 'Likely'},
    'langchain': {'name': 'LangChain', 'info': 'LLM app framework ($2B, Sequoia)', 'score': 85, 'h1b': 'Likely'},
    'notion': {'name': 'Notion', 'info': 'AI-powered productivity ($10B)', 'score': 85, 'h1b': 'Likely'},
    'lambda': {'name': 'Lambda', 'info': 'GPU cloud for AI training ($1.5B)', 'score': 85, 'h1b': 'Likely'},
    'openevidence': {'name': 'OpenEvidence', 'info': 'AI medical evidence (Harvard/MIT)', 'score': 75, 'h1b': 'Likely'},
    'photoroom': {'name': 'Photoroom', 'info': 'AI photo editing ($500M+)', 'score': 75, 'h1b': 'Unknown'},
    'pika': {'name': 'Pika', 'info': 'AI video generation ($800M, Spark)', 'score': 90, 'h1b': 'Likely'},
    'sierra': {'name': 'Sierra', 'info': 'AI customer service ($4.5B, Bret Taylor)', 'score': 90, 'h1b': 'Likely'},
    'speak': {'name': 'Speak', 'info': 'AI language learning ($1B, Founders Fund)', 'score': 80, 'h1b': 'Likely'},
    'suno': {'name': 'Suno', 'info': 'AI music generation ($500M, Lightspeed)', 'score': 85, 'h1b': 'Likely'},
    'worldlabs': {'name': 'World Labs', 'info': 'Spatial AI ($1.3B, Fei-Fei Li)', 'score': 90, 'h1b': 'Likely'},
    'deepl': {'name': 'DeepL', 'info': 'AI translation ($2B, IVP)', 'score': 80, 'h1b': 'Likely'},
    'rilla': {'name': 'Rilla', 'info': 'AI sales coaching ($30M, Lightspeed)', 'score': 70, 'h1b': 'Likely'},
    'omnea': {'name': 'Omnea', 'info': 'AI procurement automation', 'score': 70, 'h1b': 'Unknown'},
    'synthesia': {'name': 'Synthesia', 'info': 'AI video avatars ($2.1B, Accel/NVIDIA)', 'score': 85, 'h1b': 'Likely'},
    'adaptive': {'name': 'Adaptive Security', 'info': 'AI cybersecurity ($100M, a16z)', 'score': 75, 'h1b': 'Likely'},
    'traba': {'name': 'Traba', 'info': 'AI staffing marketplace ($150M, Khosla)', 'score': 75, 'h1b': 'Likely'},
    'avoca': {'name': 'Avoca', 'info': 'AI voice agents for SMBs', 'score': 75, 'h1b': 'Likely'},
    'tennr': {'name': 'Tennr', 'info': 'AI healthcare automation ($40M, a16z)', 'score': 75, 'h1b': 'Likely'},
    'ambiencehealthcare': {'name': 'Ambience Healthcare', 'info': 'AI medical scribe ($750M, Kleiner)', 'score': 80, 'h1b': 'Likely'},
    'harmonic': {'name': 'Harmonic', 'info': 'AI reasoning/math ($75M, Sequoia)', 'score': 80, 'h1b': 'Likely'},
    'openrouter': {'name': 'OpenRouter', 'info': 'AI model routing/API marketplace', 'score': 80, 'h1b': 'Likely'},
    'graphite': {'name': 'Graphite', 'info': 'AI code review ($52M, Thrive)', 'score': 80, 'h1b': 'Likely'},
    'radai': {'name': 'Rad AI', 'info': 'AI radiology automation ($225M)', 'score': 75, 'h1b': 'Likely'},
    'physicalintelligence': {'name': 'Physical Intelligence', 'info': 'Robot foundation models ($2.4B, Bezos/Thiel)', 'score': 95, 'h1b': 'Likely'},
    'infinitus': {'name': 'Infinitus', 'info': 'AI healthcare phone automation', 'score': 70, 'h1b': 'Likely'},
    'nooks': {'name': 'Nooks', 'info': 'AI sales dialer ($100M, a16z)', 'score': 75, 'h1b': 'Likely'},
    'sahara': {'name': 'Sahara AI', 'info': 'Decentralized AI ($43M, Binance)', 'score': 75, 'h1b': 'Likely'},
    'slingshotai': {'name': 'Slingshot AI', 'info': 'AI automation', 'score': 65, 'h1b': 'Unknown'},
    'sema4.ai': {'name': 'Sema4.ai', 'info': 'AI automation platform (fka Robocorp)', 'score': 70, 'h1b': 'Likely'},
    'quilter': {'name': 'Quilter', 'info': 'AI PCB design ($36M, Founders Fund)', 'score': 75, 'h1b': 'Likely'},
    'allium': {'name': 'Allium', 'info': 'Blockchain data & AI', 'score': 70, 'h1b': 'Unknown'},
    'fieldguide': {'name': 'Fieldguide', 'info': 'AI audit & advisory ($51M, Bessemer)', 'score': 70, 'h1b': 'Likely'},
    'air': {'name': 'Air Space Intelligence', 'info': 'AI flight optimization', 'score': 75, 'h1b': 'Likely'},
    'rasa': {'name': 'Rasa', 'info': 'Conversational AI platform ($75M)', 'score': 75, 'h1b': 'Likely'},
    'ema': {'name': 'Ema', 'info': 'Universal AI employee ($58M, Accel)', 'score': 80, 'h1b': 'Likely'},
    'tavus': {'name': 'Tavus', 'info': 'AI video personalization ($48M)', 'score': 75, 'h1b': 'Likely'},
    'memora': {'name': 'Memora Health', 'info': 'AI patient engagement ($40M)', 'score': 70, 'h1b': 'Likely'},
    'replicate': {'name': 'Replicate', 'info': 'ML model hosting ($100M, a16z)', 'score': 80, 'h1b': 'Likely'},
    'deepgram': {'name': 'Deepgram', 'info': 'AI speech recognition ($85M, Madrona)', 'score': 80, 'h1b': 'Likely'},
    'amprobotics': {'name': 'AMP Robotics', 'info': 'AI recycling robots ($200M)', 'score': 70, 'h1b': 'Likely'},
    'fathom': {'name': 'Fathom', 'info': 'AI meeting notes ($17M)', 'score': 65, 'h1b': 'Unknown'},
    'tectonai': {'name': 'Tecton.AI', 'info': 'ML feature platform ($161M, a16z)', 'score': 80, 'h1b': 'Likely'},
    'built-robotics': {'name': 'Built Robotics', 'info': 'Autonomous construction ($120M)', 'score': 75, 'h1b': 'Likely'},
    'hyperscience': {'name': 'HyperScience', 'info': 'AI document processing ($300M)', 'score': 70, 'h1b': 'Likely'},
    'shift': {'name': 'Shift Technology', 'info': 'AI insurance automation ($320M)', 'score': 70, 'h1b': 'Likely'},
    'akasa': {'name': 'AKASA', 'info': 'AI healthcare revenue cycle ($205M)', 'score': 70, 'h1b': 'Likely'},
    'cape': {'name': 'Cape Analytics', 'info': 'AI property analytics ($104M)', 'score': 70, 'h1b': 'Likely'},
    'uipath': {'name': 'UiPath', 'info': 'Robotic process automation ($10B mcap)', 'score': 80, 'h1b': 'Confirmed'},
    'snowflake': {'name': 'Snowflake', 'info': 'Data cloud/AI ($56B mcap)', 'score': 85, 'h1b': 'Confirmed'},
    # YC AI companies (2024-2026 batches)
    'asimov': {'name': 'Asimov', 'info': 'Robot training data marketplace (YC W26)', 'score': 75, 'h1b': 'Likely'},
    'wafer': {'name': 'Wafer', 'info': 'AI that makes AI fast (YC S25)', 'score': 75, 'h1b': 'Likely'},
    'hud': {'name': 'hud', 'info': 'RL environments and evals platform (YC W25)', 'score': 75, 'h1b': 'Likely'},
    'afterquery': {'name': 'AfterQuery', 'info': 'AI capabilities research lab (YC W25)', 'score': 80, 'h1b': 'Likely'},
    'mem0': {'name': 'Mem0', 'info': 'Memory layer for AI apps (YC S24)', 'score': 80, 'h1b': 'Likely'},
    'efference': {'name': 'Efference', 'info': 'Robot visual cortex (YC F25)', 'score': 75, 'h1b': 'Likely'},
    # VC portfolio companies (a16z + Sequoia, detected 2026-02-16)
    'adaptive': {'name': 'Adaptive Security', 'info': 'AI-powered attack protection (a16z, $81M Series B)', 'score': 70, 'h1b': 'Likely'},
    'akasa': {'name': 'AKASA', 'info': 'Healthcare revenue cycle AI (a16z)', 'score': 65, 'h1b': 'Likely'},
    'braintrust': {'name': 'Braintrust', 'info': 'AI evaluation platform (a16z)', 'score': 75, 'h1b': 'Likely'},
    'coactive': {'name': 'Coactive', 'info': 'Visual data AI platform (a16z)', 'score': 75, 'h1b': 'Likely'},
    'cluely': {'name': 'Cluely', 'info': 'Performance AI tools (a16z, $15M)', 'score': 70, 'h1b': 'Likely'},
    'ambient.ai': {'name': 'Ambient.ai', 'info': 'Computer vision for security (a16z)', 'score': 75, 'h1b': 'Likely'},
    'graphite': {'name': 'Graphite', 'info': 'AI code review platform (a16z, $52M Series B)', 'score': 80, 'h1b': 'Likely'},
    'hedra': {'name': 'Hedra', 'info': 'Omnimodal character models/video AI (a16z, $32M Series A)', 'score': 80, 'h1b': 'Likely'},
    'openrouter': {'name': 'OpenRouter', 'info': 'LLM API routing platform (a16z+Sequoia, $40M Series A)', 'score': 80, 'h1b': 'Likely'},
    'rillet': {'name': 'Rillet', 'info': 'AI-powered accounting (a16z+Sequoia, $70M Series B)', 'score': 65, 'h1b': 'Likely'},
    'profound': {'name': 'Profound', 'info': 'AI search optimization for brands (Sequoia, $35M Series B)', 'score': 65, 'h1b': 'Likely'},
    'tennr': {'name': 'Tennr', 'info': 'AI medical document automation (a16z, $101M Series C)', 'score': 70, 'h1b': 'Likely'},
    'openevidence': {'name': 'OpenEvidence', 'info': 'Clinical decision AI (Sequoia, $210M Series B)', 'score': 70, 'h1b': 'Likely'},
    'abridge': {'name': 'Abridge', 'info': 'Clinical workflow AI (a16z, $316M Series E)', 'score': 75, 'h1b': 'Likely'},
    'semgrep': {'name': 'Semgrep', 'info': 'Code security analysis (Sequoia)', 'score': 70, 'h1b': 'Likely'},
    'vanta': {'name': 'Vanta', 'info': 'Security compliance automation (Sequoia)', 'score': 75, 'h1b': 'Confirmed'},
    'sardine': {'name': 'Sardine', 'info': 'Fraud prevention AI (a16z, $70M Series C)', 'score': 65, 'h1b': 'Likely'},
    'kalshi': {'name': 'Kalshi', 'info': 'Prediction market exchange (Sequoia)', 'score': 70, 'h1b': 'Likely'},
    'saronic': {'name': 'Saronic', 'info': 'Autonomous maritime vehicles (a16z, $600M Series C)', 'score': 70, 'h1b': 'Likely'},
    'character': {'name': 'Character.AI', 'info': 'Chatbot/character platform ($1B+, a16z)', 'score': 90, 'h1b': 'Likely'},
}

def fetch_jobs(slug):
    """Fetch all jobs from Ashby posting API."""
    url = f'{API_BASE}/{slug}'
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://jobs.ashbyhq.com/',
    })
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get('jobs', [])
    except HTTPError as e:
        print(f'ERROR: HTTP {e.code} for {slug} — board may not exist')
        return []
    except URLError as e:
        print(f'ERROR: Network error — {e.reason}')
        return []

def is_relevant(job):
    """Check if job title/department matches AI/ML keywords."""
    text = ' '.join([
        job.get('title', ''),
        job.get('department', ''),
        job.get('team', ''),
    ])
    return bool(RELEVANT_RE.search(text))

def recency_score(job):
    """Score based on how recently the job was published."""
    published = job.get('publishedAt', '')
    if not published:
        return 30
    try:
        pub_date = datetime.fromisoformat(published.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        days = (now - pub_date).days
        if days <= 0: return 100
        if days <= 3: return 70
        if days <= 7: return 50
        if days <= 14: return 30
        return 10
    except (ValueError, TypeError):
        return 30

def match_score(title):
    """Score based on title match to preferences."""
    title_lower = title.lower()
    exact = ['research scientist', 'research engineer', 'founding engineer', 'ai team lead']
    strong = ['ml engineer', 'machine learning engineer', 'ai engineer', 'applied scientist',
              'post-training', 'pre-training', 'rlhf', 'alignment', 'member of technical staff']
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
    s = 30  # salary usually not in listing
    c = COMPANY_INFO.get(slug, {}).get('score', 70)
    m = match_score(job.get('title', ''))
    return r + s + c + m, f'recency={r} salary={s} company={c} match={m}'

def check_dedup(url):
    """Check if URL is already known."""
    try:
        result = subprocess.run(
            ['python3', CHECK_DEDUP, url],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip().startswith('DUPLICATE')
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def add_to_queue(job_json):
    """Add job to queue."""
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
    location = job.get('location', '').lower()
    address = (job.get('address') or {}).get('postalAddress', {})
    country = address.get('addressCountry', '').lower()
    is_remote = job.get('isRemote', False)

    # Non-US countries — skip even if remote (visa/timezone issues)
    non_us = ['korea', 'south korea', 'singapore', 'canada', 'uk', 'united kingdom',
              'germany', 'france', 'japan', 'india', 'brazil', 'australia', 'china',
              'israel', 'netherlands', 'ireland', 'sweden', 'spain', 'italy']
    if country in non_us or any(c in location for c in non_us):
        # But allow if explicitly says "US Remote" or has US in secondary
        secondary = [str(s).lower() if isinstance(s, str) else str(s.get('location', '')).lower() for s in job.get('secondaryLocations', [])]
        if not any('us' in s or 'united states' in s for s in secondary):
            return False

    if country in ('united states', 'us', 'usa'):
        return True
    us_keywords = ['united states', 'san francisco', 'new york', 'nyc',
                   'bay area', 'seattle', 'austin', 'boston', 'chicago', 'los angeles',
                   'palo alto', 'mountain view', 'menlo park', 'sunnyvale']
    if any(kw in location for kw in us_keywords):
        return True
    # Remote with no explicit non-US country — include
    if is_remote and not country:
        return True
    return False

def search_company(slug, auto_add=False):
    """Search a single Ashby company. Returns (new_count, dup_count)."""
    all_jobs = fetch_jobs(slug)
    if not all_jobs:
        print(f'No jobs found for {slug}')
        return 0, 0

    info = COMPANY_INFO.get(slug, {})
    company_name = info.get('name', slug)

    # Filter: relevant + US/remote + listed
    relevant = [j for j in all_jobs if is_relevant(j) and j.get('isListed', True) and is_us_or_remote(j)]

    print(f'FOUND {len(relevant)} relevant US/remote jobs at {company_name} (of {len(all_jobs)} total)')

    new_count = 0
    dup_count = 0

    for job in relevant:
        url = job.get('jobUrl', '')
        title = job.get('title', '')
        location = job.get('location', 'Unknown')
        if job.get('isRemote'):
            location = f"{location} (Remote)" if location else "Remote"
        total, breakdown = score_job(job, slug)

        if check_dedup(url):
            dup_count += 1
            if not auto_add:
                print(f'  DUPLICATE [{total}] {company_name} — {title}')
            continue

        new_count += 1

        if auto_add:
            auto_apply = info.get('autoApply', True)
            entry = {
                'score': total,
                'company': company_name,
                'title': title,
                'url': url,
                'location': location,
                'salary': '',
                'companyInfo': info.get('info', ''),
                'h1b': info.get('h1b', 'Unknown'),
                'source': 'Ashby API',
                'scoreBreakdown': breakdown,
                'whyMatch': f'Relevant AI/ML role at {company_name}',
                'autoApply': auto_apply
            }
            result = add_to_queue(entry)
            print(f'  {result}')
        else:
            print(f'  [{total}] {company_name} — {title} ({location}) {url}')

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
        source = 'Ashby API (all)'
    elif args:
        slug = args[0].strip().lower()
        new_count, dup_count = search_company(slug, auto_add)
        print(f'\nSummary: {new_count} new, {dup_count} duplicate')
        source = f'Ashby:{slug}'
    else:
        print('Usage: python3 search-ashby-api.py <company-slug> [--add]')
        print('       python3 search-ashby-api.py --all [--add]')
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
