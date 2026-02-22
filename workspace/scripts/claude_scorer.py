#!/usr/bin/env python3
"""
Claude-based job relevance scorer.

Batch-scores job titles for relevance to Howard's AI/ML profile using
Claude Sonnet 4.6 via OAuth (Claude Max subscription). Drop-in replacement
for the old gemini_scorer.py.

Usage as module:
    from claude_scorer import batch_score_jobs
    scores = batch_score_jobs([
        {'title': 'ML Engineer', 'company': 'Anthropic', 'department': 'Research'},
        {'title': 'Mechanical Engineer', 'company': 'Figure AI', 'department': 'Hardware'},
    ])
    # Returns: [{'score': 92, 'reason': '...', 'relevant': True}, ...]

Usage standalone (for testing):
    python3 scripts/claude_scorer.py "ML Engineer @ Anthropic" "Mechanical Engineer @ Figure"
    python3 scripts/claude_scorer.py --test
"""
import sys
import os
import json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

# Threshold: jobs scoring below this are filtered out
RELEVANCE_THRESHOLD = 30


def _get_auth():
    """
    Returns (url, headers, model, backend) for the best available Claude backend.

    Priority:
      1. ANTHROPIC_API_KEY env var / .env file → api.anthropic.com (sk-ant-api03-...)
      2. OAuth access token from ~/.openclaw/agents/main/agent/auth-profiles.json
         → api.anthropic.com with anthropic-beta: oauth-2025-04-20 header
         → claude-sonnet-4-6 (Claude Max subscription, zero additional cost)
    """
    script_dir = os.path.dirname(os.path.realpath(__file__))

    # 1. ANTHROPIC_API_KEY (standard API key, sk-ant-api03-...)
    for key_src in [os.environ.get('ANTHROPIC_API_KEY', ''), *_read_env_file(script_dir, 'ANTHROPIC_API_KEY')]:
        if key_src and not key_src.startswith('REPLACE'):
            return (
                'https://api.anthropic.com/v1/messages',
                {'Content-Type': 'application/json', 'x-api-key': key_src, 'anthropic-version': '2023-06-01'},
                'claude-sonnet-4-6',
                'anthropic',
            )

    # 2. OAuth access token from auth-profiles.json (Claude Max subscription)
    #    Uses anthropic-beta: oauth-2025-04-20 to enable OAuth on the messages API
    profiles_path = os.path.expanduser('~/.openclaw/agents/main/agent/auth-profiles.json')
    if os.path.exists(profiles_path):
        try:
            with open(profiles_path) as f:
                data = json.load(f)
            anthr_profile = (data.get('profiles') or {}).get('anthropic:default', {})
            oauth_token = anthr_profile.get('access', '')
            if oauth_token and oauth_token.startswith('sk-ant-oat'):
                return (
                    'https://api.anthropic.com/v1/messages',
                    {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {oauth_token}',
                        'anthropic-version': '2023-06-01',
                        'anthropic-beta': 'oauth-2025-04-20',
                    },
                    'claude-sonnet-4-6',
                    'anthropic',
                )
        except Exception:
            pass

    raise RuntimeError(
        'No Claude auth found. Set ANTHROPIC_API_KEY in workspace/.env, '
        'or ensure ~/.openclaw/agents/main/agent/auth-profiles.json has anthropic:default OAuth profile.'
    )


def _read_env_file(script_dir, key_name):
    """Read a key from workspace/.env or repo root .env. Returns list of values found."""
    values = []
    for rel in [os.path.join('..', '.env'), os.path.join('..', '..', '.env')]:
        env_path = os.path.join(script_dir, rel)
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f'{key_name}='):
                        v = line.split('=', 1)[1].strip().strip("'\"")
                        if v:
                            values.append(v)
    return values


# Load auth once at import time
try:
    _API_URL, _HEADERS, _MODEL, _BACKEND = _get_auth()
except RuntimeError as _e:
    _API_URL, _HEADERS, _MODEL, _BACKEND = None, None, None, None
    print(f'CLAUDE SCORER WARN: {_e}', file=sys.stderr)


SCORING_PROMPT = """You are a job relevance scorer for Howard Cheng — a 24-year-old with an MS CS from UChicago. His core expertise is building agentic AI systems and post-training LLMs (RLHF, SFT, evals, instruction tuning). He was a Staff Researcher at Lenovo (LLMs, multimodal AI). He targets senior-level roles (~3-5 yrs exp required). He will NOT take generic software engineering roles.

SCORE 0-100 based SOLELY on how well the job title + team fits his profile:

90-100  PERFECT — His primary targets:
  • ML Engineer / Machine Learning Engineer
  • AI Engineer / LLM Engineer / Agent Engineer
  • Research Engineer (AI/ML context)
  • Applied Research Engineer / Applied Research Scientist
  • Research Scientist (AI/ML/LLM context)
  • Forward Deployed Engineer (AI/ML) / Forward Deployed Research Engineer
  • Founding Engineer/ML/AI Engineer (startup founding roles)
  • Post-Training Engineer / RLHF / Alignment / Evals Engineer
  • Member of Technical Staff (MTS) at AI-first company
  • AI Safety Engineer / Red Team Engineer (technical)

70-89  GOOD — Acceptable with caveats:
  • Software Engineer with EXPLICIT AI/Agents/LLM qualifier (e.g. "SWE - AI Agents", "SWE - LLM", "SWE, Model Training") → 75-85
  • ML Infrastructure / ML Platform Engineer (building systems *for* model training/serving, not generic cloud infra) → 70-80
  • Applied Scientist (with ML/modeling focus, NOT analytics/BI) → 70-80
  • Data Scientist with deep ML/modeling focus (NOT dashboards/SQL) → 65-72
  • AI Outcome Engineer / Outcome Engineer (AI-focused, deploys and implements AI systems for customers — FDE-adjacent, lucrative) → 65-75
  • Strategic Projects Lead (Coding) / Strategic Lead (Engineering) — explicit coding/engineering qualifier makes this IC, not PM → 62-72

30-69  WEAK — Low priority, only if nothing better:
  • Generic Software Engineer at AI company with no qualifier → 45-55
  • Backend/Systems Engineer at AI company (could be model serving adjacent) → 35-50
  • Platform/Infrastructure Engineer without AI qualifier → 35-48
  • Data Scientist without clear ML modeling focus → 30-45
  • ML/AI Engineer at robotics company doing ML work (NOT robot control, planning, or SLAM) → 35-50

0-29  AUTO-SKIP — Do NOT queue these:
  • Full Stack Engineer / Frontend Engineer (regardless of company) → 5-20
  • Data Engineer (ETL, pipelines, Spark, dbt — not ML) → 10-22
  • Solutions Engineer / Sales Engineer / Field Engineer → 5-18
  • GTM Engineer / Revenue Engineer → 0-12
  • DevOps / SRE / Cloud Engineer / Site Reliability Engineer without ML focus → 5-20
  • Infrastructure Engineer / Platform Engineer (generic cloud/Kubernetes/networking) → 5-20
  • Fleet Safety / Robotics Safety (non-ML engineering domain) → 5-15
  • Robotics Engineer / Robotics SWE / Robot Perception / Motion Planning / SLAM / Sensor Fusion → 0-12
  • Autonomous Vehicle Engineer / AV Engineer (sensor fusion, routing, planning — not ML-first) → 0-12
  • GPU Kernel Engineer / CUDA Kernel Developer / Triton Kernel / Compiler Engineer (XLA, MLIR, hardware drivers, kernel coding) → 0-15
  • Systems Engineer focused on low-level performance / hardware abstraction / kernel-level optimization → 0-15
  • Product Manager / Program Manager → 0-15
  • Recruiter / HR / Operations / Finance / Legal / Marketing → 0-8
  • Hardware / Mechanical / Electrical / Civil / Chemical Engineer → 0-10
  • Director / VP / Head of (management, not IC) → 0-20
  • Any role clearly requiring 10+ years or C-suite level → 0-20

TITLE PENALTIES (apply before final score):
  • Title contains "Senior Staff" → subtract 12 (over-leveled, implies 8+ yrs)
  • Title contains "Principal" → subtract 8 (over-leveled, implies 7+ yrs)
  • Title explicitly says "6+ Years", "7+ Years", "8+ Years" in the title → subtract 25
  • Title is "Founding" at tiny seed co AND role is IC engineering → no penalty (founding engineer at startup is fine)

IMPORTANT RULES:
  • Judge by JOB ROLE first, company second. A "Mechanical Engineer" at OpenAI is still 0-10.
  • "Full-Stack Engineer", "Full Stack Engineer", "Fullstack Engineer" = ALWAYS 0-20, even with an AI qualifier in parentheses (e.g., "Senior Full-stack Engineer (Agentic AI)" is still 0-20). The actual work is web UI + API, not ML.
  • "Software Engineer" with NO qualifier at AI company = 45-55 (might be ML-adjacent, can't tell)
  • "Software Engineer, AI Agents" or "SWE - LLM" = 75-85 (explicit AI qualifier saves it)
  • Do NOT reward a company name alone. Score the work the person does.
  • Physical robotics (motion planning, SLAM, sensor fusion, robot arm control) = always 0-12, even at top AI/robotics companies (Figure AI, Physical Intelligence, Boston Dynamics, Waymo). The work domain is mechanical robotics, not Howard's background.
  • Low-level GPU/systems work (CUDA kernels, Triton, XLA/MLIR compilers, hardware drivers, kernel optimization) = always 0-15. Howard uses PyTorch/JAX as an ML practitioner, not as a systems/kernel programmer.
  • "ML Performance" / "Performance Engineering" / "Inference Engineering" roles at GPU infrastructure companies (e.g. Modal, CoreWeave, Anyscale, Crusoe) typically require CUDA profiling, SM occupancy tuning, TensorRT/Triton Server in C++/Go, and kernel-level GPU work — score 0-15. Only score higher if the role is clearly algorithmic (e.g. "LLM inference optimization" at a research lab without CUDA requirements).
  • CoreWeave roles: nearly all are GPU infra/cloud engineering. Apply extra scrutiny — even "AI/ML" titles at CoreWeave usually mean building serving infrastructure, not model work. Default to 10-25 unless the title explicitly says ML Research/Post-Training/Agents.
  • "Member of Technical Staff" with a systems/performance/infra qualifier (e.g. "MTS - ML Performance", "MTS - Kernel", "MTS - Infrastructure") = score the QUALIFIER, not the "MTS" label. MTS + systems qualifier → 0-20. MTS at AI-first company with no qualifier → 90+.
  • "ML Infrastructure" in title = 70-80 ONLY if it clearly means building ML training pipelines or model serving systems. If the role is about Kubernetes, cloud storage, networking, or cluster operations → treat as generic infra → 10-22.
  • "(Coding)" or "(Engineering)" suffix on an otherwise PM-sounding title (e.g. "Strategic Projects Lead (Coding)") means it is an IC engineering role — do NOT score it as a PM. Treat it like a senior IC engineer with coding responsibilities.
  • "Outcome Engineer" / "AI Outcome Engineer" = FDE-adjacent customer-facing AI deployment role. Score 65-75 — do NOT score as "unclear" or skip.

Jobs to score (format: [index] Company | Title | Department/Team):
{jobs_text}

Respond with ONLY a JSON array, one object per job, same order:
[{{"s": <score>, "r": "<3-5 word reason>"}}, ...]

Example: [{{"s": 95, "r": "core ML eng role"}}, {{"s": 8, "r": "mechanical hardware"}}, {{"s": 52, "r": "generic SWE AI co"}}, {{"s": 78, "r": "SWE with LLM qualifier"}}]"""


def batch_score_jobs(jobs, chunk_size=25):
    """
    Score a list of jobs using Claude Haiku.

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
    """Score a chunk of jobs via a single Claude API call."""
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
        result = _call_claude(prompt)
        scores = _parse_scores(result, len(jobs))
        return scores
    except Exception as e:
        print(f'CLAUDE SCORER ERROR: {e} — falling back to keyword scoring', file=sys.stderr)
        return [_fallback_score(job) for job in jobs]


def _call_claude(prompt):
    """Make a single Claude API call. Returns the text response."""
    if not _HEADERS:
        raise RuntimeError('No auth headers available')

    # Anthropic native format (api.anthropic.com)
    payload = {
        'model': _MODEL,
        'max_tokens': 8192,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    data = json.dumps(payload).encode('utf-8')
    req = Request(_API_URL, data=data, headers=_HEADERS)
    with urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
    content = result.get('content', [])
    if not content:
        raise ValueError('No content in Claude response')
    return content[0].get('text', '')


def _parse_scores(text, expected_count):
    """Parse Claude's JSON response into score dicts."""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
    if text.endswith('```'):
        text = text[:-3]
    text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find('[')
        end = text.rfind(']') + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
        else:
            raise ValueError(f'Cannot parse Claude response as JSON: {text[:200]}')

    if not isinstance(parsed, list):
        raise ValueError(f'Expected JSON array, got {type(parsed)}')

    scores = []
    for item in parsed:
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

    while len(scores) < expected_count:
        scores.append({'score': 40, 'reason': 'missing from response', 'relevant': True})

    return scores[:expected_count]


def _fallback_score(job):
    """Keyword-based fallback when Claude is unavailable."""
    title = job.get('title', '').lower()

    # Auto-skip tier (0-29)
    skip_kw = ['mechanical engineer', 'electrical engineer', 'hardware engineer',
               'solutions engineer', 'sales engineer', 'field engineer',
               'gtm engineer', 'revenue engineer', 'data engineer',
               'frontend engineer', 'full stack', 'fullstack', 'full-stack',
               'product manager', 'program manager', 'director', 'vp of',
               'head of', 'recruiter', 'fleet safety', 'civil engineer',
               # Robotics (physical/mechanical domain)
               'robotics engineer', 'robotics software engineer', 'robot perception',
               'motion planning', 'sensor fusion', 'slam engineer',
               'autonomous vehicle engineer', 'av engineer',
               # Low-level GPU / kernel / compiler work
               'gpu kernel', 'cuda kernel', 'triton kernel', 'kernel engineer',
               'compiler engineer', 'kernel developer', 'low-level systems',
               # Generic infra (non-ML)
               'site reliability', 'sre engineer', 'devops engineer',
               'cloud engineer', 'infrastructure engineer', 'platform engineer']
    for kw in skip_kw:
        if kw in title:
            return {'score': 15, 'reason': f'skip: {kw}', 'relevant': False}

    # Perfect tier (90-100)
    perfect_kw = ['ml engineer', 'machine learning engineer', 'ai engineer',
                  'llm engineer', 'agent engineer', 'research scientist',
                  'research engineer', 'applied research', 'forward deployed',
                  'post-training', 'rlhf', 'alignment engineer', 'evals engineer',
                  'member of technical staff', 'founding engineer', 'founding ml',
                  'founding ai', 'applied ml', 'ai safety engineer']
    for kw in perfect_kw:
        if kw in title:
            score = 92
            if 'senior staff' in title: score -= 12
            if 'principal' in title: score -= 8
            for yr in ['6+ year', '7+ year', '8+ year', '10+ year']:
                if yr in title: score -= 25
            return {'score': max(30, score), 'reason': f'core: {kw}', 'relevant': True}

    # Good tier (70-89)
    good_kw_explicit = ['software engineer, ai', 'software engineer - ai',
                        'swe, llm', 'swe - llm', 'engineer, agents', 'engineer - agents']
    for kw in good_kw_explicit:
        if kw in title:
            return {'score': 78, 'reason': 'swe with AI qualifier', 'relevant': True}

    strong_kw = ['applied scientist', 'ml infrastructure', 'ml platform',
                 'inference engineer', 'model engineer']
    for kw in strong_kw:
        if kw in title:
            return {'score': 74, 'reason': f'strong: {kw}', 'relevant': True}

    # Weak but not filtered (30-69)
    if 'software engineer' in title:
        return {'score': 48, 'reason': 'generic SWE', 'relevant': True}
    if 'data scientist' in title:
        return {'score': 38, 'reason': 'data scientist unclear', 'relevant': True}
    if 'backend engineer' in title or 'platform engineer' in title:
        return {'score': 42, 'reason': 'backend/platform', 'relevant': True}

    return {'score': 42, 'reason': 'unclassified', 'relevant': True}


# ---- CLI for testing ----
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python3 claude_scorer.py "Title @ Company" ...')
        print('       python3 claude_scorer.py --test')
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
