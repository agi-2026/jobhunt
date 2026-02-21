#!/usr/bin/env python3
"""
Deep queue cleaner: fetches actual job descriptions via URL, scores with Claude on full
page content. Removes irrelevant jobs that slipped through title-only scoring.

Two passes:
  Pass 1 — Title pattern fast removal (no URL fetch needed, instant)
  Pass 2 — URL content review: fetch page, extract description, score with Claude

Usage:
  python3 scripts/queue-deep-clean.py --dry-run          # Preview removals
  python3 scripts/queue-deep-clean.py --remove           # Actually remove
  python3 scripts/queue-deep-clean.py --title-only --remove   # Fast pass only
  python3 scripts/queue-deep-clean.py --limit 200 --remove    # Cap jobs reviewed
  python3 scripts/queue-deep-clean.py --min-score 200 --remove # Only check score<200
"""

import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
WORKSPACE = os.path.dirname(SCRIPT_DIR)

# ─── Title pattern immediate-removal (no URL fetch needed) ───────────────────
# These are definitively not AI/ML engineering roles
TITLE_REJECT_PATTERNS = [
    # Infrastructure / Ops (non-ML)
    r'\bsite reliability\b', r'\bsre\b(?! team|\s*lead)', r'\bdevops\b', r'\bdev ops\b',
    r'\bplatform engineer\b(?!.*ml|.*ai|.*infra)', r'\bsecurity devops\b',
    r'\bsecurity engineer\b(?!.*ml|.*ai)',
    # Quality / Testing
    r'\bquality engineer\b', r'\bqa engineer\b', r'\bquality assurance\b',
    r'\bperformance quality\b', r'\bstaff quality\b',
    # Frontend / Design (non-AI)
    r'\bfront.?end (engineer|developer)\b(?!.*ai|.*ml)', r'\bfront-end design\b',
    r'\bui/ux\b', r'\bux design\b', r'\bdesigner\b(?!.*ai|.*ml)',
    r'\bbrand designer\b', r'\bfounding designer\b', r'\bfounding brand\b',
    # Sales / Solutions (non-technical)
    r'\bsolutions engineer\b(?!.*ai|.*ml)', r'\bsolutions architect\b(?!.*ai|.*ml)',
    r'\bsales engineer\b', r'\benterprise sales\b',
    r'\baccount manager\b', r'\bcustomer success\b',
    r'\bpre.?sales\b', r'\bpost.?sales\b',
    r'\bdeployment strategist\b',
    # Marketing / Partnerships / Community
    r'\bproduct marketing\b', r'\bmarketing manager\b', r'\bmarketing engineer\b(?!.*ai|.*ml)',
    r'\bfounding marketer\b', r'\bgrowth marketer\b',
    r'\bdeveloper advocate\b', r'\bdeveloper relations\b', r'\bdevrel\b',
    r'\bpartnerships\b(?!.*technical|.*ai)',
    r'\bcommunity manager\b',
    # Recruiting / HR / Operations
    r'\brecruiter\b', r'\btalent sourcer\b', r'\btalent acquisition\b',
    r'\boffice manager\b', r'\bexecutive assistant\b', r'\bfacilities\b',
    r'\bpeople operations\b', r'\bhr\b(?! team| system)',
    # Finance / Legal / Accounting
    r'\bfinancial analyst\b', r'\bfinancial planner\b',
    r'\baccounting\b(?!.*ai|.*ml)', r'\baccount executive\b',
    r'\blegal\b', r'\bcounsel\b', r'\bparalegal\b',
    # Hardware / Physical Engineering
    r'\bmechanical engineer\b', r'\belectrical engineer\b',
    r'\bhardware engineer\b', r'\bfirmware engineer\b',
    r'\bcivil engineer\b', r'\bchemical engineer\b',
    r'\bmanufacturing engineer\b', r'\bmanufacturing technician\b',
    r'\bsupply chain\b', r'\bbiocompatibility\b', r'\bneurosurgeon\b',
    r'\bflight software engineer\b',
    # Mobile / Native (non-ML)
    r'\bios engineer\b', r'\bandroid engineer\b', r'\bmobile engineer\b(?!.*ai|.*ml)',
    # Non-technical domain roles
    r'\bpublic safety\b', r'\blaw enforcement\b', r'\bstrategist\b(?!.*ai|.*ml|.*tech)',
    r'\bstrategy director\b', r'\bstrategy lead\b',
    r'\bproject manager\b(?!.*ai|.*ml|.*tech)', r'\bprogram manager\b(?!.*ai|.*ml)',
    # IT / Security Management (non-engineering)
    r'\bit manager\b', r'\bit director\b', r'\bsecurity manager\b',
    r'\bdatabase reliability\b',
    # Trust & Safety non-technical
    r'\btrust & safety specialist\b', r'\bcontent moderation\b',
    # Management roles at scale where IC is needed
    r'\bdirector of marketing\b', r'\bvp of\b',
]

# ─── HTML text extractor ──────────────────────────────────────────────────────
SKIP_TAGS = {'script', 'style', 'nav', 'header', 'footer', 'aside', 'noscript', 'iframe'}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._buf = []
        self._depth = 0
        self._skip_stack = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_stack.append(tag)

    def handle_endtag(self, tag):
        if self._skip_stack and self._skip_stack[-1] == tag:
            self._skip_stack.pop()

    def handle_data(self, data):
        if not self._skip_stack:
            text = data.strip()
            if len(text) > 2:
                self._buf.append(text)

    def get_text(self, max_chars=4000):
        joined = ' '.join(self._buf)
        # Collapse whitespace
        joined = re.sub(r'\s+', ' ', joined)
        return joined[:max_chars]


def fetch_text(url, timeout=8):
    """Fetch URL and return extracted text. Returns (text, error_str)."""
    try:
        req = Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) JobHunt/1.0',
            'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
        })
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000)  # Max 200KB
            charset = resp.headers.get_content_charset('utf-8')
            html = raw.decode(charset, errors='replace')
        extractor = _TextExtractor()
        extractor.feed(html)
        return extractor.get_text(), None
    except HTTPError as e:
        return '', f'HTTP {e.code}'
    except URLError as e:
        return '', f'URLError: {e.reason}'
    except Exception as e:
        return '', f'{type(e).__name__}: {e}'


# ─── Claude scoring for full job description ──────────────────────────────────
sys.path.insert(0, SCRIPT_DIR)
from claude_scorer import _get_auth

DESCRIPTION_PROMPT = """You are evaluating job postings for Howard Cheng:
- MS CS from UChicago, AI/ML specialist (LLMs, computer vision, multimodal AI, autonomous agents)
- Staff Researcher at Lenovo, shipped CES 2026 AI systems
- Needs H-1B sponsorship
- NOT interested in: DevOps/SRE, pure frontend, QA/testing, sales/solutions engineering, marketing, recruiting, HR, legal, finance, hardware, mechanical, electrical, firmware engineering

Score the job posting 0-100 for relevance to his profile:
- 80-100: Core AI/ML role (research scientist, ML engineer, AI engineer, LLM engineer, applied scientist)
- 60-79: Strong adjacent (ML infra, AI platform, applied AI engineer on ML systems)
- 40-59: Borderline (SWE at AI company on data pipelines or ML-adjacent product work)
- 20-39: Non-ML SWE/DevOps/Frontend at AI company, or vague tech role with no ML component
- 0-19: Completely irrelevant (marketing, sales, finance, QA, hardware, design, HR, legal, DevOps, SRE)

Jobs to evaluate (format: [index] Company | Title):
{jobs_text}

Full descriptions follow:
{descriptions_text}

Respond ONLY with a JSON array, one entry per job, same order:
[{{"s": <0-100>, "r": "<3-5 word reason>"}}, ...]"""

def _get_claude_headers():
    api_url, headers, model, _backend = _get_auth()
    return api_url, headers, model


def _claude_score_batch(jobs_with_text, api_url, headers, model):
    """Score a batch using Claude (Anthropic API). Returns list of {score, reason}."""
    jobs_text = '\n'.join(f"[{i}] {j['company']} | {j['title']}" for i, j in enumerate(jobs_with_text))
    descs = []
    for i, j in enumerate(jobs_with_text):
        desc = j.get('description', '').strip() or '(no description available)'
        descs.append(f"[{i}] {desc[:1500]}")
    descriptions_text = '\n\n'.join(descs)

    prompt = DESCRIPTION_PROMPT.format(jobs_text=jobs_text, descriptions_text=descriptions_text)
    payload = {
        'model': model,
        'max_tokens': 8192,
        'messages': [{'role': 'user', 'content': prompt}],
    }
    data = json.dumps(payload).encode('utf-8')
    req = Request(api_url, data=data, headers=headers)
    with urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())

    content = result.get('content', [])
    if not content:
        raise ValueError('No content in Claude response')
    text = content[0].get('text', '').strip()

    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
    if text.endswith('```'):
        text = text[:-3]
    parsed = json.loads(text.strip())
    if not isinstance(parsed, list):
        raise ValueError('Not a list')
    scores = []
    for item in parsed:
        if isinstance(item, dict):
            s = int(item.get('s', item.get('score', 40)))
            r = str(item.get('r', item.get('reason', '')))
        else:
            s, r = 40, '?'
        scores.append({'score': max(0, min(100, s)), 'reason': r})
    while len(scores) < len(jobs_with_text):
        scores.append({'score': 40, 'reason': 'missing'})
    return scores[:len(jobs_with_text)]


def _remove(url, reason, dry_run):
    if dry_run:
        return True
    try:
        result = subprocess.run(
            ['python3', os.path.join(SCRIPT_DIR, 'remove-from-queue.py'), url, reason],
            capture_output=True, text=True, timeout=10,
            cwd=os.path.dirname(WORKSPACE),
        )
        return result.returncode == 0
    except Exception as e:
        print(f'    REMOVE ERROR: {e}', file=sys.stderr)
        return False


def _parse_queue():
    """Parse queue-summary output into list of {score, company, title, url}."""
    result = subprocess.run(
        ['python3', os.path.join(SCRIPT_DIR, 'queue-summary.py'),
         '--actionable', '--top', '700', '--full-url'],
        capture_output=True, text=True, timeout=30,
        cwd=os.path.dirname(WORKSPACE),
    )
    jobs = []
    for line in result.stdout.splitlines():
        m = re.match(r'\[(\d+)\] (.+?) — (.+?) \| .+? \| (https?://\S+)', line.strip())
        if m:
            jobs.append({
                'score': int(m.group(1)),
                'company': m.group(2).strip(),
                'title': m.group(3).strip(),
                'url': m.group(4).strip(),
            })
    return jobs


def _title_reject(title):
    """Returns pattern string if title is a clear reject, else None."""
    t = title.lower()

    # Override: explicit ML/AI context that overrides platform/security patterns
    # Includes short "ai"/"ml" so "AI Platform Engineer" doesn't get falsely rejected
    has_ai_ml_in_title = bool(re.search(r'\b(ai|ml|machine learning|deep learning|llm|neural|inference|post.?training|pre.?training|rlhf|alignment)\b', t))

    for pat in TITLE_REJECT_PATTERNS:
        if not re.search(pat, t):
            continue
        # Exception: "AI/ML Platform Engineer" is legitimate AI infra work
        if 'platform engineer' in pat and has_ai_ml_in_title:
            continue
        # Exception: "AI Security" / "ML Security" could mean model red-teaming
        if 'security engineer' in pat and re.search(r'\bai\s+security\b|\bml\s+security\b', t):
            continue
        return pat
    return None


def main():
    parser = argparse.ArgumentParser(description='Deep queue cleaner')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, do not remove')
    parser.add_argument('--remove', action='store_true', help='Actually remove irrelevant jobs')
    parser.add_argument('--title-only', action='store_true', help='Only do title pattern pass')
    parser.add_argument('--limit', type=int, default=0, help='Max jobs to URL-review')
    parser.add_argument('--min-queue-score', type=int, default=0,
                        help='Only review jobs with queue score below this (0=all)')
    parser.add_argument('--score-threshold', '--gemini-threshold', type=int, default=38,
                        help='Remove if content score below this (default: 38)')
    parser.add_argument('--workers', type=int, default=12, help='URL fetch threads')
    parser.add_argument('--chunk-size', type=int, default=20, help='Claude batch size')
    args = parser.parse_args()

    dry_run = not args.remove

    print(f'\n{"DRY RUN — " if dry_run else ""}Queue Deep Cleaner')
    print(f'{"─"*55}')

    print('Parsing queue...')
    jobs = _parse_queue()
    print(f'Found {len(jobs)} pending jobs')

    removed_title = 0
    removed_content = 0
    dead_links = 0

    # ── Pass 1: Title pattern filter ─────────────────────────────────────────
    print(f'\n── Pass 1: Title pattern removal ──')
    survivors = []
    for j in jobs:
        pat = _title_reject(j['title'])
        if pat:
            action = 'WOULD REMOVE' if dry_run else 'REMOVING'
            print(f'  {action} [{j["score"]}] {j["company"]} — {j["title"]}')
            print(f'    reason: title matches /{pat}/')
            if _remove(j['url'], f'IRRELEVANT: title pattern match ({j["title"]})', dry_run):
                removed_title += 1
        else:
            survivors.append(j)

    print(f'\nPass 1 result: {removed_title} removed, {len(survivors)} remaining')

    if args.title_only:
        print(f'\nTitle-only mode. Done.')
        print(f'Total removed: {removed_title}')
        return

    # ── Pass 2: URL content review ────────────────────────────────────────────
    # Review jobs with lower queue scores (likely borderline/suspicious)
    review_threshold = args.min_queue_score or 250  # Review anything below 250
    to_review = [j for j in survivors if j['score'] < review_threshold]
    if args.limit > 0:
        to_review = to_review[:args.limit]

    print(f'\n── Pass 2: URL content review ({len(to_review)} jobs, score < {review_threshold}) ──')
    print(f'Fetching {len(to_review)} URLs with {args.workers} workers...')

    try:
        cl_url, cl_headers, cl_model = _get_claude_headers()
    except RuntimeError as e:
        print(f'ERROR: {e}', file=sys.stderr)
        sys.exit(1)

    # Parallel URL fetch
    t0 = time.time()
    fetched = {}  # url → (text, error)

    def _fetch_job(j):
        text, err = fetch_text(j['url'])
        return j['url'], text, err

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_fetch_job, j): j for j in to_review}
        done = 0
        for fut in concurrent.futures.as_completed(futures):
            url, text, err = fut.result()
            fetched[url] = (text, err)
            done += 1
            if done % 20 == 0 or done == len(to_review):
                elapsed = time.time() - t0
                print(f'  Fetched {done}/{len(to_review)} ({elapsed:.1f}s)')

    fetch_time = time.time() - t0
    print(f'URL fetch complete in {fetch_time:.1f}s')

    # Handle dead links
    dead_jobs = []
    live_jobs = []
    for j in to_review:
        text, err = fetched.get(j['url'], ('', 'not fetched'))
        if err and err.startswith('HTTP 4'):
            dead_jobs.append(j)
        elif len(text) < 100:  # Too little text = likely dead or blocked
            if err:
                dead_jobs.append(j)
            else:
                live_jobs.append((j, text))  # Might just be JS-heavy page
        else:
            live_jobs.append((j, text))

    print(f'\nDead/unreachable links: {len(dead_jobs)}')
    for j in dead_jobs:
        text, err = fetched.get(j['url'], ('', 'unknown'))
        action = 'WOULD REMOVE' if dry_run else 'REMOVING'
        print(f'  {action} [{j["score"]}] {j["company"]} — {j["title"]} ({err})')
        if _remove(j['url'], f'DEAD: URL fetch failed ({err})', dry_run):
            dead_links += 1

    # ── Claude full-description scoring ──────────────────────────────────────
    print(f'\nClaude content scoring {len(live_jobs)} live jobs...')
    chunk_size = args.chunk_size
    claude_scored = []

    for i in range(0, len(live_jobs), chunk_size):
        chunk = live_jobs[i:i + chunk_size]
        batch_input = [
            {'company': j['company'], 'title': j['title'], 'description': text}
            for j, text in chunk
        ]
        try:
            scores = _claude_score_batch(batch_input, cl_url, cl_headers, cl_model)
            for (j, _text), score in zip(chunk, scores):
                claude_scored.append((j, score))
        except Exception as e:
            print(f'  Claude batch {i//chunk_size+1} ERROR: {e}', file=sys.stderr)
            # Fallback: mark all as unknown (keep them)
            for j, _text in chunk:
                claude_scored.append((j, {'score': 50, 'reason': 'claude error - kept'}))

        batches_done = min(i + chunk_size, len(live_jobs))
        print(f'  Scored {batches_done}/{len(live_jobs)}')

    # ── Apply threshold and remove ───────────────────────────────────────────
    threshold = args.score_threshold
    print(f'\n── Content review results (threshold: {threshold}) ──')

    keep_count = 0
    for j, score in claude_scored:
        s = score['score']
        r = score['reason']
        if s < threshold:
            action = 'WOULD REMOVE' if dry_run else 'REMOVING'
            print(f'  {action} [{j["score"]}→{s}] {j["company"]} — {j["title"]} | {r}')
            if _remove(j['url'], f'IRRELEVANT: content score {s} ({r})', dry_run):
                removed_content += 1
        else:
            keep_count += 1

    # ── Summary ──────────────────────────────────────────────────────────────
    total_removed = removed_title + dead_links + removed_content
    remaining = len(jobs) - total_removed
    print(f'\n{"═"*55}')
    print(f'SUMMARY {"(DRY RUN)" if dry_run else ""}')
    print(f'{"─"*55}')
    print(f'  Started with:         {len(jobs)} jobs')
    print(f'  Title pattern:        {removed_title} removed')
    print(f'  Dead links:           {dead_links} removed')
    print(f'  Content irrelevant:   {removed_content} removed')
    print(f'  Total removed:        {total_removed}')
    print(f'  Remaining in queue:   {remaining}')
    if dry_run:
        print(f'\n  Run with --remove to actually remove these jobs.')


if __name__ == '__main__':
    main()
