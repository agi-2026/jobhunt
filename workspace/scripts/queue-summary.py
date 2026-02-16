#!/usr/bin/env python3
"""
Output a compact summary of the job queue for agents to minimize context window usage.

Usage:
  python3 scripts/queue-summary.py                  # Top 10 PENDING jobs (1-line each)
  python3 scripts/queue-summary.py --top 5           # Top 5
  python3 scripts/queue-summary.py --actionable      # Top 10, skip NO-AUTO entries
  python3 scripts/queue-summary.py --section pending  # Specific section
  python3 scripts/queue-summary.py --stats            # Just stats

Output (compact, ~50 chars per job):
  QUEUE: 42 pending | 0 in_progress
  [335] OpenAI — RE ChatGPT Agent | SF | $295K-$530K | openai.com/... | ⚠️NO-AUTO
  [305] OpenAI — RE Agent Robustness | SF | $295K | openai.com/... | ⚠️NO-AUTO
  [290] Anthropic — RE Alignment | SF/NYC | $300K-$405K | jobs.ashbyhq.com/...
  ...
"""
import sys
import os
import re

QUEUE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'job-queue.md')

def parse_queue_compact():
    with open(QUEUE_PATH, 'r') as f:
        content = f.read()

    sections = {'pending': [], 'in_progress': [], 'completed': [], 'skipped': [], 'no_auto': []}
    current_section = None
    current_job = None
    stats = {'pending': 0, 'in_progress': 0}

    for line in content.split('\n'):
        stripped = line.strip()

        # Stats line
        m = re.match(r'.*Pending:\s*(\d+)\s*\|\s*In Progress:\s*(\d+)', stripped)
        if m:
            stats['pending'] = int(m.group(1))
            stats['in_progress'] = int(m.group(2))

        # Section headers
        if stripped.startswith('## ') and 'DO NOT AUTO-APPLY' in stripped:
            current_section = 'no_auto'
            continue
        elif stripped == '## IN PROGRESS':
            current_section = 'in_progress'
            continue
        elif stripped.startswith('## PENDING'):
            current_section = 'pending'
            continue
        elif stripped.startswith('## COMPLETED'):
            current_section = 'completed'
            continue
        elif stripped == '## SKIPPED':
            current_section = 'skipped'
            continue

        if current_section in (None, 'no_auto'):
            # Still capture DO NOT AUTO-APPLY jobs
            if current_section == 'no_auto':
                score_match = re.match(r'^###\s+\[(\d+)\]\s+(.+?)\s*—\s*(.+)$', stripped)
                if score_match:
                    if current_job:
                        sections['pending'].append(current_job)
                    current_job = {
                        'score': int(score_match.group(1)),
                        'company': score_match.group(2).strip(),
                        'title': score_match.group(3).strip(),
                        'url': '', 'location': '', 'salary': '', 'no_auto': True
                    }
                elif current_job:
                    if stripped.startswith('- **URL:**'):
                        current_job['url'] = stripped.split('**URL:**')[1].strip()
                    elif stripped.startswith('- **Location:**'):
                        current_job['location'] = stripped.split('**Location:**')[1].strip()
                    elif stripped.startswith('- **Salary:**'):
                        current_job['salary'] = stripped.split('**Salary:**')[1].strip()
            continue

        if current_section not in sections:
            continue

        score_match = re.match(r'^###\s+\[(\d+)\]\s+(.+?)\s*—\s*(.+)$', stripped)
        if score_match:
            if current_job:
                sections[current_job.get('_section', current_section)].append(current_job)
            current_job = {
                '_section': current_section,
                'score': int(score_match.group(1)),
                'company': score_match.group(2).strip(),
                'title': score_match.group(3).strip(),
                'url': '', 'location': '', 'salary': '', 'no_auto': False
            }
        elif current_job:
            if stripped.startswith('- **URL:**'):
                current_job['url'] = stripped.split('**URL:**')[1].strip()
            elif stripped.startswith('- **Location:**'):
                current_job['location'] = stripped.split('**Location:**')[1].strip()
            elif stripped.startswith('- **Salary:**'):
                current_job['salary'] = stripped.split('**Salary:**')[1].strip()
            elif 'DO NOT AUTO-APPLY' in stripped or 'OPENAI LIMIT' in stripped or 'Auto-Apply: NO' in stripped:
                current_job['no_auto'] = True

    if current_job:
        sections[current_job.get('_section', current_section)].append(current_job)

    # Clean internal keys
    for section in sections.values():
        for job in section:
            job.pop('_section', None)

    return sections, stats

def shorten_url(url, max_len=40):
    url = url.replace('https://', '').replace('http://', '').replace('www.', '')
    if len(url) > max_len:
        return url[:max_len-3] + '...'
    return url

def format_job_line(job):
    parts = [f"[{job['score']}] {job['company']} — {job['title']}"]
    if job.get('location'):
        loc = job['location'].split(',')[0].strip()  # Just city
        parts.append(loc)
    if job.get('salary'):
        parts.append(job['salary'][:20])
    if job.get('url'):
        parts.append(shorten_url(job['url']))
    if job.get('no_auto'):
        parts.append('⚠️NO-AUTO')
    return ' | '.join(parts)

def main():
    args = sys.argv[1:]
    top_n = 10
    section = 'pending'
    stats_only = False
    actionable_only = False

    i = 0
    while i < len(args):
        if args[i] == '--top' and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
        elif args[i] == '--section' and i + 1 < len(args):
            section = args[i + 1]
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

    if actionable_only:
        jobs = [j for j in jobs if not j.get('no_auto')]

    for job in jobs[:top_n]:
        print(format_job_line(job))

    remaining = len(jobs) - top_n
    if remaining > 0:
        print(f"... +{remaining} more")

if __name__ == '__main__':
    main()
