#!/usr/bin/env python3
"""
Re-score pending queue jobs with Claude to find and remove irrelevant ones.

Usage:
  python3 scripts/rescore-queue.py              # Dry run — show what would be removed
  python3 scripts/rescore-queue.py --remove      # Actually remove irrelevant jobs
"""
import sys
import os
import subprocess
import json
import re

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from claude_scorer import batch_score_jobs, RELEVANCE_THRESHOLD

REMOVE_SCRIPT = os.path.join(SCRIPT_DIR, 'remove-from-queue.py')


def get_queue_jobs():
    """Get all actionable pending jobs from queue-summary."""
    result = subprocess.run(
        ['python3', os.path.join(SCRIPT_DIR, 'queue-summary.py'),
         '--actionable', '--top', '500', '--full-url'],
        capture_output=True, text=True, timeout=30
    )
    jobs = []
    for line in result.stdout.strip().split('\n'):
        m = re.match(r'^\[(\d+)\]\s+(.+?)\s+—\s+(.+)$', line)
        if not m:
            continue
        score = int(m.group(1))
        company = m.group(2).strip()
        rest = m.group(3).strip()
        parts = [p.strip() for p in rest.split(' | ')]
        url = ''
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].startswith('http'):
                url = parts[i]
                parts = parts[:i]
                break
        if not url:
            continue
        title = parts[0] if parts else ''
        jobs.append({
            'score': score,
            'company': company,
            'title': title,
            'url': url,
        })
    return jobs


def main():
    remove = '--remove' in sys.argv

    print('Loading queue...')
    jobs = get_queue_jobs()
    print(f'Found {len(jobs)} actionable pending jobs')

    if not jobs:
        print('No jobs to re-score')
        return

    print(f'Scoring {len(jobs)} jobs with Claude...')
    claude_input = [{'title': j['title'], 'company': j['company']} for j in jobs]
    scores = batch_score_jobs(claude_input)

    irrelevant = []
    for job, gscore in zip(jobs, scores):
        if not gscore['relevant']:
            irrelevant.append((job, gscore))

    print(f'\n=== IRRELEVANT JOBS ({len(irrelevant)} of {len(jobs)}) ===')
    for job, gscore in sorted(irrelevant, key=lambda x: x[1]['score']):
        action = 'REMOVING' if remove else 'WOULD REMOVE'
        print(f"  [{gscore['score']:3d}] {action}: {job['company']} — {job['title']} | {gscore['reason']}")

        if remove:
            try:
                result = subprocess.run(
                    ['python3', REMOVE_SCRIPT, job['url'], '--reason', f"Claude:{gscore['reason']}"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode != 0:
                    print(f'    ERROR removing: {result.stderr.strip()}')
            except Exception as e:
                print(f'    ERROR: {e}')

    print(f'\nTotal: {len(irrelevant)} irrelevant of {len(jobs)} pending')
    if not remove and irrelevant:
        print('Run with --remove to actually remove these jobs')


if __name__ == '__main__':
    main()
