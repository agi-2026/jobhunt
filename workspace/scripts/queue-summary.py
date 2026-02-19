#!/usr/bin/env python3
"""
Output a compact summary of the job queue for agents to minimize context window usage.

Usage:
  python3 scripts/queue-summary.py                  # Top 10 PENDING jobs (1-line each)
  python3 scripts/queue-summary.py --top 5           # Top 5
  python3 scripts/queue-summary.py --actionable      # Top 10, skip NO-AUTO entries (full URLs)
  python3 scripts/queue-summary.py --ats ashby        # Filter by ATS type (ashby|greenhouse|lever|other)
  python3 scripts/queue-summary.py --section pending  # Specific section
  python3 scripts/queue-summary.py --stats            # Just stats
  python3 scripts/queue-summary.py --full-url          # Don't truncate URLs
  python3 scripts/queue-summary.py --short-url         # Force URL truncation

Output (compact, ~50 chars per job):
  QUEUE: 42 pending | 0 in_progress
  [335] OpenAI — RE ChatGPT Agent | SF | $295K-$530K | openai.com/... | ⚠️NO-AUTO
  [305] OpenAI — RE Agent Robustness | SF | $295K | openai.com/... | ⚠️NO-AUTO
  [290] Anthropic — RE Alignment | SF/NYC | $300K-$405K | jobs.ashbyhq.com/...
  ...
"""
import sys
import os
from queue_utils import filter_jobs, read_queue_sections

QUEUE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'job-queue.md')
LOCK_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), '.queue.lock')

# Companies that should never appear in --actionable output (Howard applies manually)
NO_AUTO_COMPANIES = {'openai', 'databricks', 'pinterest'}

def parse_queue_compact():
    return read_queue_sections(QUEUE_PATH, LOCK_PATH, no_auto_companies=NO_AUTO_COMPANIES)

def shorten_url(url, max_len=40):
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    if len(url) > max_len:
        return url[:max_len-3] + '...'
    return url

def format_job_line(job, full_url=False):
    parts = [f"[{job['score']}] {job['company']} — {job['title']}"]
    if job.get('location'):
        loc = job['location'].split(',')[0].strip()  # Just city
        parts.append(loc)
    if job.get('salary'):
        parts.append(job['salary'][:20])
    if job.get('url'):
        parts.append(job['url'] if full_url else shorten_url(job['url']))
    if job.get('no_auto'):
        parts.append('⚠️NO-AUTO')
    return ' | '.join(parts)

def main():
    args = sys.argv[1:]
    top_n = 10
    section = 'pending'
    stats_only = False
    actionable_only = False
    ats_filter = None
    full_url = False

    i = 0
    while i < len(args):
        if args[i] == '--top' and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
        elif args[i] == '--section' and i + 1 < len(args):
            section = args[i + 1]
            i += 2
        elif args[i] == '--ats' and i + 1 < len(args):
            ats_filter = args[i + 1].lower()
            i += 2
        elif args[i] == '--stats':
            stats_only = True
            i += 1
        elif args[i] == '--actionable':
            actionable_only = True
            i += 1
        elif args[i] == '--all':
            top_n = 999
            i += 1
        elif args[i] == '--full-url':
            full_url = True
            i += 1
        elif args[i] == '--short-url':
            full_url = False
            i += 1
        else:
            i += 1

    sections, stats = parse_queue_compact()

    pending_count = len(sections['pending'])
    ip_count = len(sections['in_progress'])

    print(f"QUEUE: {pending_count} pending | {ip_count} in_progress")

    if stats_only:
        return

    jobs = sections.get(section, [])
    # Sort by score descending
    jobs.sort(key=lambda j: j['score'], reverse=True)

    jobs = filter_jobs(jobs, actionable_only=actionable_only, ats_filter=ats_filter)
    # Actionable mode is used by application agents; they need exact URLs.
    if actionable_only:
        full_url = True

    for job in jobs[:top_n]:
        print(format_job_line(job, full_url=full_url))

    remaining = len(jobs) - top_n
    if remaining > 0:
        print(f"... +{remaining} more")

if __name__ == '__main__':
    main()
