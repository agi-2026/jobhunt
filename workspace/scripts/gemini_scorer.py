#!/usr/bin/env python3
"""
Gemini-based job relevance scorer.

Batch-scores job titles for relevance to Howard's AI/ML profile using
Gemini 2.5 Flash. Replaces keyword-based match_score() with semantic scoring.

Usage as module:
    from gemini_scorer import batch_score_jobs
    scores = batch_score_jobs([
        {'title': 'ML Engineer', 'company': 'Anthropic', 'department': 'Research'},
        {'title': 'Mechanical Engineer', 'company': 'Figure AI', 'department': 'Hardware'},
    ])
    # Returns: [{'score': 92, 'dominated_by_irrelevant': False}, {'score': 8, 'dominated_by_irrelevant': True}]

Usage standalone (for testing):
    python3 scripts/gemini_scorer.py "ML Engineer @ Anthropic" "Mechanical Engineer @ Figure"
"""
import sys
import os
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

GEMINI_API_KEY = 'api-key-goes-here'  # <-- REPLACE WITH YOUR API KEY
GEMINI_MODEL = 'gemini-3.0-flash'
GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}'

# Threshold: jobs scoring below this are filtered out
RELEVANCE_THRESHOLD = 30

SCORING_PROMPT = """You are a job relevance scorer for Howard Cheng — a 24-year-old with an MS in Computer Science from UChicago, focused on AI/ML research and engineering. He was a Staff Researcher at Lenovo working on LLMs, computer vision, and multimodal AI. He needs H-1B sponsorship.

Score each job 0-100 for how well it fits his profile:

- 90-100: Perfect (AI/ML research scientist, LLM/foundation model engineer, founding AI engineer, applied ML researcher)
- 70-89: Strong (ML engineer, AI engineer, applied scientist, data scientist with ML focus, ML infra/platform)
- 50-69: Moderate (software engineer at AI company on ML-adjacent work like data pipelines, model serving, AI product)
- 30-49: Weak (generic software engineer, backend/frontend with no ML component, DevOps)
- 0-29: Irrelevant (mechanical engineer, electrical engineer, hardware, civil, chemical, biomedical, non-technical, sales, marketing, recruiting, operations, finance, legal, HR, facilities, supply chain, manufacturing)

IMPORTANT: "Software Engineer" with NO AI/ML qualifier at an AI company scores 40-55 (could be relevant infra). "Mechanical Engineer" or "Hardware Engineer" ALWAYS scores 0-15 regardless of company. Focus on the JOB ROLE, not the company.

Jobs to score (format: [index] Company | Title | Department/Team):
{jobs_text}

Respond with ONLY a JSON array of objects, one per job, in the same order:
[{{"s": <score>, "r": "<3-5 word reason>"}}, ...]

Example: [{{"s": 95, "r": "core ML research"}}, {{"s": 12, "r": "mechanical not CS"}}, {{"s": 55, "r": "generic SWE at AI co"}}]"""


def batch_score_jobs(jobs, chunk_size=25):
    """
    Score a list of jobs using Gemini.

    Args:
        jobs: list of dicts with keys: title, company, department (optional), team (optional)
        chunk_size: max jobs per API call

    Returns:
        list of dicts with keys: score (int 0-100), reason (str), relevant (bool)
        Falls back to keyword scoring on API error.
    """
    if not jobs:
        return []

    all_scores = []
    for i in range(0, len(jobs), chunk_size):
        chunk = jobs[i:i + chunk_size]
        scores = _score_chunk(chunk)
        all_scores.extend(scores)

    return all_scores


def _score_chunk(jobs):
    """Score a chunk of jobs via a single Gemini API call."""
    # Build job list text
    lines = []
    for idx, job in enumerate(jobs):
        company = job.get('company', 'Unknown')
        title = job.get('title', 'Unknown')
        dept = job.get('department', '') or job.get('team', '') or ''
        line = f"[{idx}] {company} | {title}"
        if dept:
            line += f" | {dept}"
        lines.append(line)

    jobs_text = '\n'.join(lines)
    prompt = SCORING_PROMPT.format(jobs_text=jobs_text)

    try:
        result = _call_gemini(prompt)
        scores = _parse_scores(result, len(jobs))
        return scores
    except Exception as e:
        print(f'GEMINI SCORER ERROR: {e} — falling back to keyword scoring', file=sys.stderr)
        return [_fallback_score(job) for job in jobs]


def _call_gemini(prompt):
    """Make a single Gemini API call."""
    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': 0.1,
            'maxOutputTokens': 8192,
            'responseMimeType': 'application/json',
        }
    }

    data = json.dumps(payload).encode('utf-8')
    req = Request(GEMINI_URL, data=data, headers={
        'Content-Type': 'application/json',
    })

    with urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    # Extract text from response
    candidates = result.get('candidates', [])
    if not candidates:
        raise ValueError('No candidates in Gemini response')

    text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
    return text


def _parse_scores(text, expected_count):
    """Parse Gemini's JSON response into score dicts."""
    # Clean up response — strip markdown code fences if present
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
        else:
            raise ValueError(f'Cannot parse Gemini response as JSON: {text[:200]}')

    if not isinstance(parsed, list):
        raise ValueError(f'Expected JSON array, got {type(parsed)}')

    scores = []
    for i, item in enumerate(parsed):
        if isinstance(item, dict):
            s = int(item.get('s', item.get('score', 40)))
            r = str(item.get('r', item.get('reason', '')))
        elif isinstance(item, (int, float)):
            s = int(item)
            r = ''
        else:
            s = 40
            r = 'unparseable'
        scores.append({
            'score': max(0, min(100, s)),
            'reason': r,
            'relevant': s >= RELEVANCE_THRESHOLD,
        })

    # Pad with fallback scores if Gemini returned fewer than expected
    while len(scores) < expected_count:
        scores.append({'score': 40, 'reason': 'missing from response', 'relevant': True})

    return scores[:expected_count]


def _fallback_score(job):
    """Keyword-based fallback when Gemini is unavailable."""
    title = job.get('title', '').lower()
    exact = ['research scientist', 'research engineer', 'founding engineer', 'ai team lead']
    strong = ['ml engineer', 'machine learning engineer', 'ai engineer', 'applied scientist',
              'post-training', 'pre-training', 'rlhf', 'alignment', 'member of technical staff']
    partial = ['software engineer', 'data scientist', 'inference engineer']

    for kw in exact:
        if kw in title:
            return {'score': 95, 'reason': f'exact: {kw}', 'relevant': True}
    for kw in strong:
        if kw in title:
            return {'score': 80, 'reason': f'strong: {kw}', 'relevant': True}
    for kw in partial:
        if kw in title:
            return {'score': 55, 'reason': f'partial: {kw}', 'relevant': True}
    return {'score': 40, 'reason': 'default', 'relevant': True}


# ---- CLI for testing ----
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 gemini_scorer.py "Title @ Company" ...')
        print('       python3 gemini_scorer.py --test')
        sys.exit(1)

    if sys.argv[1] == '--test':
        test_jobs = [
            {'title': 'Research Scientist, LLM Post-Training', 'company': 'Anthropic', 'department': 'Research'},
            {'title': 'ML Engineer', 'company': 'Cohere', 'department': 'Engineering'},
            {'title': 'Mechanical Engineer', 'company': 'Figure AI', 'department': 'Hardware'},
            {'title': 'Software Engineer', 'company': 'Notion', 'department': 'Engineering'},
            {'title': 'Hardware Design Engineer', 'company': 'Physical Intelligence', 'department': 'Hardware'},
            {'title': 'Founding AI Engineer', 'company': 'Exa', 'department': ''},
            {'title': 'Sales Engineer', 'company': 'Cohere', 'department': 'Sales'},
            {'title': 'Software Engineer, ML Infrastructure', 'company': 'Character.AI', 'department': 'Infra'},
            {'title': 'Electrical Engineer', 'company': 'Crusoe', 'department': 'Data Center'},
            {'title': 'Applied Scientist, Computer Vision', 'company': 'ElevenLabs', 'department': 'Research'},
        ]
        scores = batch_score_jobs(test_jobs)
        for job, score in zip(test_jobs, scores):
            status = 'PASS' if score['relevant'] else 'FAIL'
            print(f"  [{score['score']:3d}] {status} | {job['company']} — {job['title']} | {score['reason']}")
    else:
        jobs = []
        for arg in sys.argv[1:]:
            if ' @ ' in arg:
                title, company = arg.rsplit(' @ ', 1)
                jobs.append({'title': title.strip(), 'company': company.strip()})
            else:
                jobs.append({'title': arg, 'company': 'Unknown'})
        scores = batch_score_jobs(jobs)
        for job, score in zip(jobs, scores):
            status = 'PASS' if score['relevant'] else 'FAIL'
            print(f"  [{score['score']:3d}] {status} | {job.get('company', '?')} — {job['title']} | {score['reason']}")
