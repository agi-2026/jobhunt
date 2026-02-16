#!/usr/bin/env python3
"""
Update a job's stage in job-tracker.md and recalculate pipeline counts.

Usage:
  python3 scripts/update-tracker-stage.py "<url_or_company>" "<new_stage>" ["<notes>"]

Stages: Discovered, Applied, Confirmed, Response, Phone Screen, Technical Interview, Onsite/Final, Offer, Rejected

Examples:
  python3 scripts/update-tracker-stage.py "https://jobs.ashbyhq.com/anthropic/123" "Phone Screen" "Scheduled for Feb 20"
  python3 scripts/update-tracker-stage.py "Anthropic" "Phone Screen" "Recruiter email received"

Output:
  UPDATED Anthropic — Research Engineer: Applied → Phone Screen
  NOT_FOUND — no matching entry for "some-url"
"""
import sys
import os
import re
from datetime import datetime

TRACKER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'job-tracker.md')

VALID_STAGES = [
    'Discovered', 'Applied', 'Confirmed', 'Response',
    'Phone Screen', 'Technical Interview', 'Onsite/Final',
    'Offer', 'Rejected'
]

def update_stage(search_term, new_stage, notes=''):
    if new_stage not in VALID_STAGES:
        print(f"ERROR: Invalid stage '{new_stage}'. Valid: {', '.join(VALID_STAGES)}")
        sys.exit(1)

    with open(TRACKER_PATH, 'r') as f:
        content = f.read()

    lines = content.split('\n')
    search_lower = search_term.lower().strip()
    found = False
    old_stage = ''
    company = ''
    title = ''
    in_target_entry = False
    stage_updated = False
    timeline_section = False

    for i, line in enumerate(lines):
        # Match entry headers
        entry_match = re.match(r'^###\s+(.+?)\s*—\s*(.+)$', line.strip())
        if entry_match:
            in_target_entry = False
            timeline_section = False
            c = entry_match.group(1).strip()
            t = entry_match.group(2).strip()
            # Check if this matches our search term
            if (search_lower in line.lower() or
                search_lower in c.lower() or
                search_lower in t.lower()):
                in_target_entry = True
                company = c
                title = t
                found = True
            continue

        if in_target_entry and not stage_updated:
            # Update stage line
            if line.strip().startswith('- **Stage:**'):
                old_stage = line.split('**Stage:**')[1].strip()
                lines[i] = f'- **Stage:** {new_stage}'
                stage_updated = True
                continue

            # Add timeline entry
            if line.strip().startswith('- **Timeline:**'):
                timeline_section = True
                continue

            if timeline_section and (line.strip().startswith('- ') or line.strip() == ''):
                if line.strip() == '' or not line.strip().startswith('  - '):
                    # Insert timeline entry before this line
                    now = datetime.now().strftime('%Y-%m-%d')
                    timeline_entry = f'  - {now}: {new_stage}' + (f' — {notes}' if notes else '')
                    lines.insert(i, timeline_entry)
                    timeline_section = False

            # Update notes if provided
            if notes and line.strip().startswith('- **Notes:**'):
                existing = line.split('**Notes:**')[1].strip()
                lines[i] = f'- **Notes:** {existing} | {datetime.now().strftime("%m/%d")}: {notes}'

    if not found:
        print(f"NOT_FOUND — no matching entry for \"{search_term}\"")
        sys.exit(0)

    if not stage_updated:
        print(f"NOT_FOUND — entry found but no Stage field for \"{search_term}\"")
        sys.exit(0)

    # Recalculate pipeline counts
    content_new = '\n'.join(lines)
    stage_counts = {s: 0 for s in VALID_STAGES}
    for line in lines:
        if line.strip().startswith('- **Stage:**'):
            stage_val = line.split('**Stage:**')[1].strip()
            if stage_val in stage_counts:
                stage_counts[stage_val] += 1

    # Update pipeline table
    for stage_name, count in stage_counts.items():
        content_new = re.sub(
            rf'\|\s*{re.escape(stage_name)}\s*\|\s*\d+\s*\|',
            f'| {stage_name} | {count} |',
            content_new
        )

    # Update "Last updated" timestamp
    content_new = re.sub(
        r'Last updated: \d{4}-\d{2}-\d{2}',
        f'Last updated: {datetime.now().strftime("%Y-%m-%d")}',
        content_new
    )

    with open(TRACKER_PATH, 'w') as f:
        f.write(content_new)

    print(f"UPDATED {company} — {title}: {old_stage} → {new_stage}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 update-tracker-stage.py \"<url_or_company>\" \"<new_stage>\" [\"<notes>\"]")
        sys.exit(1)

    search_term = sys.argv[1]
    new_stage = sys.argv[2]
    notes = sys.argv[3] if len(sys.argv) > 3 else ''

    update_stage(search_term, new_stage, notes)

if __name__ == '__main__':
    main()
