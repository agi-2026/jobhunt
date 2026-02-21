#!/usr/bin/env python3
"""
Re-score AND re-rank all pending queue entries using the updated Claude scorer.

What this does:
  1. Parses every PENDING entry from job-queue.md
  2. Hard-removes entries where known salary < $200K (Howard won't take them)
  3. Hard-removes entries where title implies 6+ yrs required (overqualified)
  4. Re-scores remaining entries with claude_scorer (updated prompt)
  5. Hard-removes entries scoring < RELEVANCE_THRESHOLD (< 30)
  6. Updates the ### [score] header and match= in Score Breakdown in-place
     so queue-summary.py re-sorts correctly

Usage:
  python3 scripts/rescore-and-rerank-queue.py            # dry run
  python3 scripts/rescore-and-rerank-queue.py --apply    # actually update queue
  python3 scripts/rescore-and-rerank-queue.py --apply --remove-irrelevant
"""
import sys
import os
import re
import fcntl
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
WORKSPACE   = os.path.dirname(SCRIPT_DIR)
QUEUE_PATH  = os.path.join(WORKSPACE, 'job-queue.md')
LOCK_PATH   = os.path.join(WORKSPACE, '.queue.lock')
REMOVE_SCRIPT = os.path.join(SCRIPT_DIR, 'remove-from-queue.py')

sys.path.insert(0, SCRIPT_DIR)
from claude_scorer import batch_score_jobs, RELEVANCE_THRESHOLD


# ── Salary parsing ────────────────────────────────────────────────────────────

def parse_salary_min(salary_str):
    """Parse salary string like '$174K+', '$170K-$200K', '$295K+', 'Unlisted', 'N/A'.
    Returns minimum salary in $K, or None if unknown."""
    if not salary_str:
        return None
    s = salary_str.replace(',', '').upper()
    # Match patterns like $174K, $174K+, $170K-$200K
    m = re.search(r'\$(\d+(?:\.\d+)?)\s*K', s)
    if m:
        return float(m.group(1))
    # Match patterns like $174,000 or $174000
    m = re.search(r'\$(\d{3,})', s)
    if m:
        val = float(m.group(1))
        return val / 1000 if val > 1000 else val
    return None


def salary_below_threshold(salary_str, threshold_k=200):
    """Return True only if salary is explicitly known AND below threshold."""
    sal = parse_salary_min(salary_str)
    if sal is None:
        return False  # Unknown — don't skip
    return sal < threshold_k


# ── Experience-level title filter ─────────────────────────────────────────────

# Titles that strongly imply >5 yrs tenure required
OVERLEVELED_PATTERNS = [
    r'\b6\+\s*year',
    r'\b7\+\s*year',
    r'\b8\+\s*year',
    r'\b10\+\s*year',
    r'\bsenior\s+staff\b',
    r'\bprincipal\s+staff\b',
    r'\bdistinguished\b',
    r'\bstaff\s+principal\b',
    r'\bvp\b',
    r'\bvice\s+president\b',
    r'\bdirector\b',
    r'\bhead\s+of\b',
    r'\bchief\b',
    r'\bmanaging\s+director\b',
]
OVERLEVELED_RE = re.compile('|'.join(OVERLEVELED_PATTERNS), re.IGNORECASE)

def is_overleveled(title):
    """Return True if title implies >5 yrs tenure, except 'Founding' roles at startups."""
    # Founding roles at startups are fine even if senior-sounding
    if re.search(r'\bfounding\b', title, re.IGNORECASE):
        return False
    return bool(OVERLEVELED_RE.search(title))


# ── Queue parser ──────────────────────────────────────────────────────────────

def parse_queue_entries():
    """Parse job-queue.md. Returns list of dicts with parsed fields + raw_block."""
    with open(QUEUE_PATH, 'r') as f:
        content = f.read()

    entries = []
    # Split on section headers but keep them together with their content
    blocks = re.split(r'(?=^### )', content, flags=re.MULTILINE)

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        if not block.startswith('### '):
            # Preamble / section dividers — preserve as-is
            entries.append({'type': 'preamble', 'raw': block})
            continue

        # Parse fields
        status_m  = re.search(r'\*\*Status:\*\*\s*(\w+)', block)
        status    = status_m.group(1) if status_m else 'UNKNOWN'

        if status != 'PENDING':
            entries.append({'type': 'non_pending', 'raw': block, 'status': status})
            continue

        header_m  = re.search(r'^### \[(\d+)\] (.+)', block, re.MULTILINE)
        url_m     = re.search(r'\*\*URL:\*\*\s*(https?://\S+)', block)
        salary_m  = re.search(r'\*\*Salary:\*\*\s*(.+)', block)
        company_m = re.search(r'\*\*Company:\*\*\s*(.+)', block)
        breakdown_m = re.search(r'\*\*Score Breakdown:\*\*\s*(.+)', block)

        if not header_m or not url_m:
            entries.append({'type': 'non_pending', 'raw': block, 'status': status})
            continue

        header_score = int(header_m.group(1))
        header_title = header_m.group(2).strip()
        # Extract company — from header title "Company — Job Title | ..."
        company_from_header = ''
        title_from_header   = header_title
        if ' — ' in header_title:
            parts = header_title.split(' — ', 1)
            company_from_header = parts[0].strip()
            title_from_header   = parts[1].split(' | ')[0].strip()

        # Parse score breakdown components
        breakdown_str = breakdown_m.group(1).strip() if breakdown_m else ''
        recency_v = _extract_component(breakdown_str, 'recency') or 30
        salary_v  = _extract_component(breakdown_str, 'salary')  or 30
        company_v = _extract_component(breakdown_str, 'company') or 70
        # match= may have suffix like "match=78(claude:...)"
        match_v   = _extract_component(breakdown_str, 'match')   or 42

        entries.append({
            'type':          'pending',
            'raw':           block,
            'url':           url_m.group(1).strip(),
            'salary_str':    (salary_m.group(1).strip() if salary_m else ''),
            'company':       (company_m.group(1).strip() if company_m else company_from_header),
            'title':         title_from_header,
            'header_score':  header_score,
            'header_title':  header_title,
            'recency_v':     recency_v,
            'salary_v':      salary_v,
            'company_v':     company_v,
            'match_v':       match_v,
            'breakdown_str': breakdown_str,
        })

    return entries


def _extract_component(breakdown, name):
    """Extract integer value for a named component from score breakdown string."""
    m = re.search(rf'\b{name}=(-?\d+)', breakdown)
    return int(m.group(1)) if m else None


# ── Queue writer ──────────────────────────────────────────────────────────────

def update_entry_score(raw_block, new_match, new_total, reason):
    """Update ### [score] header and match= in Score Breakdown."""
    # Update the header score
    updated = re.sub(
        r'^(### )\[(\d+)\]',
        f'\\g<1>[{new_total}]',
        raw_block,
        count=1,
        flags=re.MULTILINE,
    )
    # Update match= in Score Breakdown (strip old claude: suffix too)
    updated = re.sub(
        r'(match=)-?\d+(?:\([^)]*\))?',
        f'\\g<1>{new_match}(claude:{reason})',
        updated,
        count=1,
    )
    # Update the full Score Breakdown total if it has recency/salary/company pattern
    def recompute_breakdown(m):
        line = m.group(0)
        r_m = re.search(r'recency=(\d+)', line)
        s_m = re.search(r'salary=(-?\d+)', line)
        c_m = re.search(r'company=(\d+)', line)
        if r_m and s_m and c_m:
            r = int(r_m.group(1))
            s = int(s_m.group(1))
            c = int(c_m.group(1))
            # match already updated above — extract it again
            mk_m = re.search(r'match=(-?\d+)', line)
            mk = int(mk_m.group(1)) if mk_m else new_match
            # No further change needed — header already updated
        return line

    return updated


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    apply_mode       = '--apply' in sys.argv
    remove_irrelevant = '--remove-irrelevant' in sys.argv

    print('Parsing queue...')
    entries = parse_queue_entries()
    pending = [e for e in entries if e['type'] == 'pending']
    print(f'Found {len(pending)} PENDING entries')

    # ── Pass 1: hard filters (salary + overleveled) ────────────────────────
    salary_removed  = []
    overlevel_removed = []
    to_score = []

    for e in pending:
        if salary_below_threshold(e['salary_str']):
            salary_removed.append(e)
        elif is_overleveled(e['title']):
            overlevel_removed.append(e)
        else:
            to_score.append(e)

    print(f'\n=== HARD FILTER: SALARY < $200K ({len(salary_removed)}) ===')
    for e in salary_removed:
        print(f"  REMOVE: {e['company']} — {e['title']} | {e['salary_str']}")

    print(f'\n=== HARD FILTER: OVERLEVELED TITLE ({len(overlevel_removed)}) ===')
    for e in overlevel_removed:
        print(f"  REMOVE: {e['company']} — {e['title']}")

    # ── Pass 2: Claude rescoring ────────────────────────────────────────────
    print(f'\nScoring {len(to_score)} remaining jobs with Claude...')
    claude_input = [{'title': e['title'], 'company': e['company']} for e in to_score]
    scores = batch_score_jobs(claude_input, chunk_size=25)

    irrelevant = []
    to_update  = []

    for e, cscore in zip(to_score, scores):
        new_match = cscore['score']
        reason    = cscore['reason']
        relevant  = cscore['relevant']

        new_total = e['recency_v'] + e['salary_v'] + e['company_v'] + new_match
        old_total = e['header_score']
        delta     = new_total - old_total

        if not relevant and remove_irrelevant:
            irrelevant.append((e, cscore))
        else:
            to_update.append((e, new_match, new_total, reason, delta))

    # Print irrelevant
    print(f'\n=== CLAUDE IRRELEVANT (score < {RELEVANCE_THRESHOLD}) — {len(irrelevant)} ===')
    for e, cscore in sorted(irrelevant, key=lambda x: x[1]['score']):
        action = 'REMOVING' if (apply_mode and remove_irrelevant) else 'WOULD REMOVE'
        print(f"  [{cscore['score']:3d}] {action}: {e['company']} — {e['title']} | {cscore['reason']}")

    # Print biggest re-ranks
    movers_up   = sorted([(e, nm, nt, r, d) for e,nm,nt,r,d in to_update if d >= 20], key=lambda x: -x[4])
    movers_down = sorted([(e, nm, nt, r, d) for e,nm,nt,r,d in to_update if d <= -20], key=lambda x: x[4])

    print(f'\n=== TOP SCORE INCREASES ({len(movers_up)} jobs moved up ≥20 pts) ===')
    for e, nm, nt, r, d in movers_up[:20]:
        print(f"  +{d:3d}  [{e['header_score']}→{nt}]  {e['company']} — {e['title']}  ({r})")

    print(f'\n=== TOP SCORE DECREASES ({len(movers_down)} jobs moved down ≥20 pts) ===')
    for e, nm, nt, r, d in movers_down[:20]:
        print(f"  {d:4d}  [{e['header_score']}→{nt}]  {e['company']} — {e['title']}  ({r})")

    if not apply_mode:
        total_removes = len(salary_removed) + len(overlevel_removed) + (len(irrelevant) if remove_irrelevant else 0)
        print(f'\nDRY RUN — {len(to_update)} entries would be rescored, {total_removes} removed')
        print('Run with --apply to update queue, --apply --remove-irrelevant to also remove low-score jobs')
        return

    # ── Apply changes ───────────────────────────────────────────────────────
    print('\nApplying changes...')

    # Remove salary/overlevel jobs via remove-from-queue.py
    def remove_url(url, reason_str):
        try:
            result = subprocess.run(
                ['python3', REMOVE_SCRIPT, url, '--reason', reason_str],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                print(f'  ERROR removing {url}: {result.stderr.strip()}')
        except Exception as ex:
            print(f'  ERROR: {ex}')

    for e in salary_removed:
        print(f"  REMOVING (salary<$200K): {e['company']} — {e['title']}")
        remove_url(e['url'], f"salary below $200K threshold: {e['salary_str']}")

    for e in overlevel_removed:
        print(f"  REMOVING (overleveled): {e['company']} — {e['title']}")
        remove_url(e['url'], f"title implies 6+ yrs required or management: {e['title']}")

    if remove_irrelevant:
        for e, cscore in irrelevant:
            print(f"  REMOVING (irrelevant [{cscore['score']}]): {e['company']} — {e['title']}")
            remove_url(e['url'], f"Claude score {cscore['score']}: {cscore['reason']}")

    # Re-read the queue file (removals above may have changed it)
    with open(QUEUE_PATH, 'r') as f:
        queue_content = f.read()

    # Update scores in-place for each entry
    updates_applied = 0
    for e, new_match, new_total, reason, delta in to_update:
        old_header = f"### [{e['header_score']}] {e['header_title']}"
        new_header = f"### [{new_total}] {e['header_title']}"

        # Only rewrite if score actually changed
        if new_total == e['header_score'] and new_match == e['match_v']:
            continue

        if old_header not in queue_content:
            # Header might have been removed by a prior removal — skip silently
            continue

        # Update header score
        queue_content = queue_content.replace(old_header, new_header, 1)

        # Update match= in Score Breakdown for this entry
        # Find the section and update match=
        section_start = queue_content.find(new_header)
        next_section  = queue_content.find('\n### ', section_start + 1)
        section       = queue_content[section_start:next_section] if next_section > 0 else queue_content[section_start:]

        updated_section = re.sub(
            r'(\*\*Score Breakdown:\*\*[^\n]*?\bmatch=)-?\d+(?:\([^)]*\))?',
            f'\\g<1>{new_match}(claude:{reason})',
            section,
            count=1,
        )

        if next_section > 0:
            queue_content = queue_content[:section_start] + updated_section + queue_content[next_section:]
        else:
            queue_content = queue_content[:section_start] + updated_section

        updates_applied += 1

    # Write back atomically with lock
    with open(LOCK_PATH, 'w') as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            with open(QUEUE_PATH, 'w') as f:
                f.write(queue_content)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)

    total_removes = len(salary_removed) + len(overlevel_removed) + (len(irrelevant) if remove_irrelevant else 0)
    print(f'\nDONE: {updates_applied} scores updated, {total_removes} entries removed')


if __name__ == '__main__':
    main()
