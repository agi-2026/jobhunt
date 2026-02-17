#!/usr/bin/env python3
"""
ATS Detection Script — Probes Ashby, Greenhouse, and Lever APIs to detect
which ATS a company uses.

Usage:
  python3 scripts/detect-ats.py "Company Name 1" "Company Name 2" ...
  python3 scripts/detect-ats.py --file companies.txt
  python3 scripts/detect-ats.py --file companies.txt --json

Output:
  Company Name | ashby | slug | 45 jobs
  Company Name | greenhouse | slug | 120 jobs
  Company Name | NOT FOUND | - | -

With --json: outputs JSON array for programmatic use.
"""
import sys
import os
import json
import re
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Already tracked companies (skip these)
ALREADY_TRACKED = {
    # Ashby
    'cohere', 'magic.dev', 'sesame', 'moonvalley-ai', 'liquid-ai',
    'fastino-ai', 'basis-ai', 'anyscale', 'harvey', 'writer', 'exa',
    'chaidiscovery', 'character', 'livekit', 'decagon',
    # Greenhouse
    'anthropic', 'thinkingmachines', 'scaleai', 'gleanwork',
    'blackforestlabs', 'deepmind', 'recursionpharmaceuticals',
    'togetherai', 'fireworksai', 'goodfire', 'runwayml', 'cerebrassystems',
    # Lever
    'mistral', 'palantir', 'zoox', 'hive', 'genbio', 'trellis',
}

# Manual slug overrides for companies with non-obvious slugs
SLUG_OVERRIDES = {
    'eleven labs': {'ashby': ['elevenlabs'], 'greenhouse': ['elevenlabs'], 'lever': ['elevenlabs']},
    'elevan labs': {'ashby': ['elevenlabs'], 'greenhouse': ['elevenlabs'], 'lever': ['elevenlabs']},
    'safe superintelligence': {'ashby': ['safe-superintelligence', 'ssi'], 'greenhouse': ['safesuperintelligence', 'ssi'], 'lever': ['safesuperintelligence', 'ssi']},
    'safe superintelligence inc.': {'ashby': ['safe-superintelligence', 'ssi'], 'greenhouse': ['safesuperintelligence', 'ssi'], 'lever': ['safesuperintelligence', 'ssi']},
    'meta ai': {'greenhouse': ['meta', 'facebook'], 'lever': ['meta'], 'ashby': ['meta']},
    'meta': {'greenhouse': ['meta', 'facebook'], 'lever': ['meta'], 'ashby': ['meta']},
    'xai': {'ashby': ['xai', 'x-ai'], 'greenhouse': ['xai'], 'lever': ['xai']},
    'anysphere': {'ashby': ['anysphere'], 'greenhouse': ['anysphere'], 'lever': ['anysphere']},
    'figure ai': {'ashby': ['figureai', 'figure'], 'greenhouse': ['figureai', 'figure'], 'lever': ['figureai', 'figure']},
    'd-id': {'ashby': ['d-id', 'did'], 'greenhouse': ['d-id', 'did'], 'lever': ['d-id', 'did']},
    'ai2': {'ashby': ['ai2', 'allenai'], 'greenhouse': ['allenai', 'ai2'], 'lever': ['allenai', 'ai2']},
    'world labs': {'ashby': ['worldlabs', 'world-labs'], 'greenhouse': ['worldlabs'], 'lever': ['worldlabs']},
    'physical intelligence': {'ashby': ['physicalintelligence', 'physical-intelligence'], 'greenhouse': ['physicalintelligence'], 'lever': ['physicalintelligence']},
    'shield ai': {'ashby': ['shieldai', 'shield-ai'], 'greenhouse': ['shieldai'], 'lever': ['shieldai']},
    'vast data': {'ashby': ['vastdata', 'vast-data'], 'greenhouse': ['vastdata'], 'lever': ['vastdata']},
    'notion': {'ashby': ['notion'], 'greenhouse': ['notion', 'notionhq'], 'lever': ['notion', 'notionhq']},
    'stripe': {'ashby': ['stripe'], 'greenhouse': ['stripe'], 'lever': ['stripe']},
    'rippling': {'ashby': ['rippling'], 'greenhouse': ['rippling'], 'lever': ['rippling']},
    'doordash': {'ashby': ['doordash'], 'greenhouse': ['doordash'], 'lever': ['doordash']},
    'uber': {'ashby': ['uber'], 'greenhouse': ['uber'], 'lever': ['uber']},
    'robinhood': {'ashby': ['robinhood'], 'greenhouse': ['robinhood'], 'lever': ['robinhood']},
    'pinterest': {'ashby': ['pinterest'], 'greenhouse': ['pinterest'], 'lever': ['pinterest']},
    'snowflake': {'ashby': ['snowflake'], 'greenhouse': ['snowflake', 'snowflakecomputing'], 'lever': ['snowflake']},
    'duolingo': {'ashby': ['duolingo'], 'greenhouse': ['duolingo'], 'lever': ['duolingo']},
    'dropbox': {'ashby': ['dropbox'], 'greenhouse': ['dropbox'], 'lever': ['dropbox']},
    'adobe': {'ashby': ['adobe'], 'greenhouse': ['adobe'], 'lever': ['adobe']},
    'neuralink': {'ashby': ['neuralink'], 'greenhouse': ['neuralink'], 'lever': ['neuralink']},
    'nvidia': {'ashby': ['nvidia'], 'greenhouse': ['nvidia'], 'lever': ['nvidia']},
    'intuit': {'ashby': ['intuit'], 'greenhouse': ['intuit'], 'lever': ['intuit']},
    'cognition ai': {'ashby': ['cognition', 'cognition-ai'], 'greenhouse': ['cognitionai', 'cognition'], 'lever': ['cognition', 'cognitionai']},
    'cognition': {'ashby': ['cognition', 'cognition-ai'], 'greenhouse': ['cognitionai', 'cognition'], 'lever': ['cognition', 'cognitionai']},
    'sambanova': {'ashby': ['sambanova'], 'greenhouse': ['sambanova', 'sambanovasystems'], 'lever': ['sambanova']},
    'suno': {'ashby': ['suno'], 'greenhouse': ['suno', 'sunoai'], 'lever': ['suno']},
    'midjourney': {'ashby': ['midjourney'], 'greenhouse': ['midjourney'], 'lever': ['midjourney']},
    'skild ai': {'ashby': ['skildai', 'skild-ai', 'skild'], 'greenhouse': ['skildai'], 'lever': ['skildai']},
    'sierra': {'ashby': ['sierra', 'sierra-ai', 'sierraai'], 'greenhouse': ['sierraai', 'sierra'], 'lever': ['sierra', 'sierraai']},
    'hebbia': {'ashby': ['hebbia'], 'greenhouse': ['hebbia'], 'lever': ['hebbia']},
    'pika': {'ashby': ['pika'], 'greenhouse': ['pika', 'paboratories'], 'lever': ['pika']},
    'crusoe': {'ashby': ['crusoe', 'crusoeenergy'], 'greenhouse': ['crusoe', 'crusoeenergy'], 'lever': ['crusoe']},
    'captions': {'ashby': ['captions'], 'greenhouse': ['captions'], 'lever': ['captions']},
    'baseten': {'ashby': ['baseten'], 'greenhouse': ['baseten'], 'lever': ['baseten']},
    'lambda': {'ashby': ['lambda', 'lambdalabs'], 'greenhouse': ['lambda', 'lambdalabs'], 'lever': ['lambda', 'lambdalabs']},
    'snorkel ai': {'ashby': ['snorkelai', 'snorkel-ai'], 'greenhouse': ['snorkelai'], 'lever': ['snorkelai']},
    'hugging face': {'ashby': ['huggingface', 'hugging-face'], 'greenhouse': ['huggingface'], 'lever': ['huggingface']},
    'replicate': {'ashby': ['replicate'], 'greenhouse': ['replicate'], 'lever': ['replicate']},
    'assemblyai': {'ashby': ['assemblyai', 'assembly-ai'], 'greenhouse': ['assemblyai'], 'lever': ['assemblyai']},
    'labelbox': {'ashby': ['labelbox'], 'greenhouse': ['labelbox'], 'lever': ['labelbox']},
    'deepgram': {'ashby': ['deepgram'], 'greenhouse': ['deepgram'], 'lever': ['deepgram']},
    'moveworks': {'ashby': ['moveworks'], 'greenhouse': ['moveworks'], 'lever': ['moveworks']},
    'cresta': {'ashby': ['cresta'], 'greenhouse': ['cresta'], 'lever': ['cresta']},
    'aisera': {'ashby': ['aisera'], 'greenhouse': ['aisera'], 'lever': ['aisera']},
    'soundhound': {'ashby': ['soundhound'], 'greenhouse': ['soundhound', 'soundhoundinc'], 'lever': ['soundhound']},
    'uipath': {'ashby': ['uipath'], 'greenhouse': ['uipath'], 'lever': ['uipath']},
    'vectra ai': {'ashby': ['vectra', 'vectra-ai'], 'greenhouse': ['vectraai', 'vectra'], 'lever': ['vectraai']},
    'clay': {'ashby': ['clay'], 'greenhouse': ['clay'], 'lever': ['clay']},
    'openrouter': {'ashby': ['openrouter', 'open-router'], 'greenhouse': ['openrouter'], 'lever': ['openrouter']},
    'waymo': {'greenhouse': ['waymo'], 'ashby': ['waymo'], 'lever': ['waymo']},
    'bloomberg': {'greenhouse': ['bloomberg'], 'ashby': ['bloomberg'], 'lever': ['bloomberg']},
    'salesforce': {'greenhouse': ['salesforce'], 'ashby': ['salesforce'], 'lever': ['salesforce']},
    'ebay': {'greenhouse': ['ebay', 'ebaycareers'], 'ashby': ['ebay'], 'lever': ['ebay']},
    'tiktok': {'greenhouse': ['tiktok', 'bytedance'], 'ashby': ['tiktok'], 'lever': ['tiktok', 'bytedance']},
    'langchain': {'ashby': ['langchain'], 'greenhouse': ['langchain'], 'lever': ['langchain']},
    'sahara ai': {'ashby': ['saharaai', 'sahara-ai', 'sahara'], 'greenhouse': ['saharaai'], 'lever': ['saharaai']},
    'codeium': {'ashby': ['codeium'], 'greenhouse': ['codeium'], 'lever': ['codeium']},
    'rad ai': {'ashby': ['radai', 'rad-ai'], 'greenhouse': ['radai'], 'lever': ['radai']},
    'heyGen': {'ashby': ['heygen'], 'greenhouse': ['heygen'], 'lever': ['heygen']},
    'heygen': {'ashby': ['heygen'], 'greenhouse': ['heygen'], 'lever': ['heygen']},
    'ema': {'ashby': ['ema'], 'greenhouse': ['ema'], 'lever': ['ema']},
    'graphite': {'ashby': ['graphite'], 'greenhouse': ['graphite'], 'lever': ['graphite']},
    'nooks': {'ashby': ['nooks'], 'greenhouse': ['nooks'], 'lever': ['nooks']},
    'spot ai': {'ashby': ['spotai', 'spot-ai'], 'greenhouse': ['spotai'], 'lever': ['spotai']},
    'fathom': {'ashby': ['fathom'], 'greenhouse': ['fathom'], 'lever': ['fathom']},
    'abacus.ai': {'ashby': ['abacusai', 'abacus-ai'], 'greenhouse': ['abacusai'], 'lever': ['abacusai']},
    'observe.ai': {'ashby': ['observeai', 'observe-ai'], 'greenhouse': ['observeai'], 'lever': ['observeai']},
    'people.ai': {'ashby': ['peopleai', 'people-ai'], 'greenhouse': ['peopleai'], 'lever': ['peopleai']},
    'tecton.ai': {'ashby': ['tecton', 'tectonai'], 'greenhouse': ['tecton'], 'lever': ['tecton']},
    'domino data lab': {'ashby': ['dominodatalab'], 'greenhouse': ['dominodatalab'], 'lever': ['dominodatalab']},
    'abridge': {'ashby': ['abridge'], 'greenhouse': ['abridge'], 'lever': ['abridge']},
    'tavus': {'ashby': ['tavus'], 'greenhouse': ['tavus'], 'lever': ['tavus']},
    'kumo': {'ashby': ['kumo', 'kumoai'], 'greenhouse': ['kumo'], 'lever': ['kumo']},
    'dialpad': {'ashby': ['dialpad'], 'greenhouse': ['dialpad'], 'lever': ['dialpad']},
}


def generate_slugs(company_name):
    """Generate possible ATS slugs from a company name."""
    name = company_name.strip()
    lower = name.lower()

    # Check overrides first
    if lower in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[lower]

    # Remove common suffixes
    clean = re.sub(r'\s*(inc\.?|llc|ltd|corp\.?|co\.?|technologies|labs?)\s*$', '', lower, flags=re.I).strip()
    # Remove "AI" suffix but keep it as a variant
    no_ai = re.sub(r'\s+ai$', '', clean, flags=re.I).strip()

    variants = set()
    for base in [clean, no_ai]:
        # No spaces
        variants.add(base.replace(' ', ''))
        # Hyphenated
        variants.add(base.replace(' ', '-'))
        # First word only (for single-product companies)
        first_word = base.split()[0] if base.split() else base
        if len(first_word) > 2:
            variants.add(first_word)
        # With "ai" suffix
        if 'ai' not in base:
            variants.add(base.replace(' ', '') + 'ai')

    # Remove empty strings
    variants.discard('')

    return {
        'ashby': list(variants),
        'greenhouse': list(variants),
        'lever': list(variants),
    }


def probe_ashby(slug, timeout=8):
    """Check if a company exists on Ashby."""
    url = f'https://api.ashbyhq.com/posting-api/job-board/{slug}'
    req = Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Referer': 'https://jobs.ashbyhq.com/',
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            jobs = data.get('jobs', [])
            return len(jobs) if jobs else 0
    except (HTTPError, URLError, Exception):
        return -1


def probe_greenhouse(slug, timeout=8):
    """Check if a company exists on Greenhouse."""
    url = f'https://api.greenhouse.io/v1/boards/{slug}/jobs'
    req = Request(url, headers={'User-Agent': 'JobSearchAgent/1.0'})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            jobs = data.get('jobs', [])
            return len(jobs) if jobs else 0
    except (HTTPError, URLError, Exception):
        return -1


def probe_lever(slug, timeout=8):
    """Check if a company exists on Lever."""
    url = f'https://api.lever.co/v0/postings/{slug}'
    req = Request(url, headers={'User-Agent': 'JobSearchAgent/1.0'})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            if isinstance(data, list):
                return len(data)
            return 0
    except (HTTPError, URLError, Exception):
        return -1


def detect_company(company_name):
    """Detect which ATS a company uses. Returns dict with results."""
    slugs = generate_slugs(company_name)
    result = {
        'company': company_name,
        'ats': None,
        'slug': None,
        'job_count': 0,
        'already_tracked': False,
    }

    # Try each ATS with all slug variants
    for ats_type, probe_fn in [('ashby', probe_ashby), ('greenhouse', probe_greenhouse), ('lever', probe_lever)]:
        for slug in slugs.get(ats_type, []):
            if slug in ALREADY_TRACKED:
                result['ats'] = ats_type
                result['slug'] = slug
                result['already_tracked'] = True
                return result

            count = probe_fn(slug)
            if count >= 0:  # Found!
                result['ats'] = ats_type
                result['slug'] = slug
                result['job_count'] = count
                return result

    return result


def main():
    args = sys.argv[1:]
    json_output = '--json' in args
    args = [a for a in args if not a.startswith('--')]

    companies = []

    # Check for --file flag
    for i, a in enumerate(sys.argv[1:]):
        if a == '--file' and i + 1 < len(sys.argv) - 1:
            filepath = sys.argv[i + 2]
            with open(filepath) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Handle numbered lists like "1. Company Name"
                        line = re.sub(r'^\d+\.\s*', '', line)
                        companies.append(line)
            break
    else:
        companies = args

    if not companies:
        print("Usage: python3 detect-ats.py 'Company 1' 'Company 2' ...")
        print("       python3 detect-ats.py --file companies.txt [--json]")
        sys.exit(1)

    # Deduplicate (case-insensitive)
    seen = set()
    unique = []
    for c in companies:
        key = c.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    print(f"Probing {len(unique)} companies across Ashby/Greenhouse/Lever APIs...\n", file=sys.stderr)

    results = []
    found = {'ashby': [], 'greenhouse': [], 'lever': []}
    not_found = []
    already = []

    # Use thread pool for parallel probing
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(detect_company, c): c for c in unique}
        for i, future in enumerate(as_completed(futures)):
            r = future.result()
            results.append(r)
            company = r['company']

            if r['already_tracked']:
                already.append(r)
                print(f"  [{i+1}/{len(unique)}] {company} | {r['ats']} | {r['slug']} | ALREADY TRACKED", file=sys.stderr)
            elif r['ats']:
                found[r['ats']].append(r)
                print(f"  [{i+1}/{len(unique)}] {company} | {r['ats']} | {r['slug']} | {r['job_count']} jobs", file=sys.stderr)
            else:
                not_found.append(r)
                print(f"  [{i+1}/{len(unique)}] {company} | NOT FOUND", file=sys.stderr)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"RESULTS: {len(found['ashby'])} Ashby, {len(found['greenhouse'])} Greenhouse, {len(found['lever'])} Lever, {len(not_found)} not found, {len(already)} already tracked", file=sys.stderr)

    if json_output:
        output = {
            'ashby': [{'company': r['company'], 'slug': r['slug'], 'jobs': r['job_count']} for r in found['ashby']],
            'greenhouse': [{'company': r['company'], 'slug': r['slug'], 'jobs': r['job_count']} for r in found['greenhouse']],
            'lever': [{'company': r['company'], 'slug': r['slug'], 'jobs': r['job_count']} for r in found['lever']],
            'not_found': [r['company'] for r in not_found],
            'already_tracked': [{'company': r['company'], 'slug': r['slug'], 'ats': r['ats']} for r in already],
        }
        print(json.dumps(output, indent=2))
    else:
        if found['ashby']:
            print(f"\n## NEW ASHBY COMPANIES ({len(found['ashby'])})")
            for r in sorted(found['ashby'], key=lambda x: -x['job_count']):
                print(f"  '{r['slug']}': {{'name': '{r['company']}', 'info': '', 'score': 70, 'h1b': 'Unknown'}},  # {r['job_count']} jobs")

        if found['greenhouse']:
            print(f"\n## NEW GREENHOUSE COMPANIES ({len(found['greenhouse'])})")
            for r in sorted(found['greenhouse'], key=lambda x: -x['job_count']):
                print(f"  '{r['slug']}': {{'info': '', 'score': 70, 'h1b': 'Unknown'}},  # {r['job_count']} jobs")

        if found['lever']:
            print(f"\n## NEW LEVER COMPANIES ({len(found['lever'])})")
            for r in sorted(found['lever'], key=lambda x: -x['job_count']):
                print(f"  '{r['slug']}': {{'name': '{r['company']}', 'info': '', 'score': 70, 'h1b': 'Unknown'}},  # {r['job_count']} jobs")

        if not_found:
            print(f"\n## NOT FOUND ({len(not_found)}) — custom ATS or no public board")
            for r in sorted(not_found, key=lambda x: x['company']):
                print(f"  - {r['company']}")


if __name__ == '__main__':
    main()
