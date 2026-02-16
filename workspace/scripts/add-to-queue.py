#!/usr/bin/env python3
"""
Add a job to the PENDING section of job-queue.md and maintain sort order.

Usage:
  python3 scripts/add-to-queue.py '<JSON>'

  JSON format:
  {
    "score": 350,
    "company": "Thinking Machines Lab",
    "title": "Research Engineer, RL Systems",
    "url": "https://...",
    "location": "San Francisco, CA",
    "salary": "$350K-$475K base",
    "companyInfo": "Frontier AI lab ($2B raised)",
    "h1b": "Confirmed",
    "source": "Greenhouse scraper",
    "scoreBreakdown": "recency=100 salary=100 company=90 match=60",
    "whyMatch": "Brief explanation of why this matches Howard",
    "autoApply": true
  }

Output:
  ADDED [350] Thinking Machines Lab — Research Engineer, RL Systems (43 pending)
  DUPLICATE — already in queue
  SKIPPED — auto-apply disabled for this company
"""
import sys
import os
import json
import re
from datetime import datetime

QUEUE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'job-queue.md')

SKIP_COMPANIES = {'openai', 'databricks'}

def parse_queue():
    """Parse queue into sections: preamble, do_not_apply, in_progress, pending entries."""
    with open(QUEUE_PATH, 'r') as f:
        content = f.read()

    # Split by entry headers
    lines = content.split('\n')

    preamble = []
    do_not_apply = []
    in_progress = []
    pending_entries = []  # list of (score, text_block)

    current_section = 'preamble'
    current_entry = []
    current_score = 0

    for line in lines:
        stripped = line.strip()

        if stripped.startswith('## ⛔ DO NOT AUTO-APPLY') or stripped.startswith('## DO NOT AUTO-APPLY'):
            current_section = 'do_not_apply'
            do_not_apply.append(line)
            continue
        elif stripped == '## IN PROGRESS':
            current_section = 'in_progress'
            in_progress.append(line)
            continue
        elif stripped.startswith('## PENDING'):
            current_section = 'pending'
            # Don't store the header — we'll regenerate it
            continue

        if current_section == 'preamble':
            preamble.append(line)
        elif current_section == 'do_not_apply':
            do_not_apply.append(line)
        elif current_section == 'in_progress':
            if stripped.startswith('### ['):
                current_section = 'in_progress_entry'
                in_progress.append(line)
            else:
                in_progress.append(line)
        elif current_section == 'in_progress_entry':
            in_progress.append(line)
        elif current_section == 'pending':
            if stripped.startswith('### ['):
                # Save previous entry
                if current_entry:
                    pending_entries.append((current_score, '\n'.join(current_entry)))
                current_entry = [line]
                # Extract score
                m = re.match(r'### \[(\d+)\]', stripped)
                current_score = int(m.group(1)) if m else 0
            else:
                current_entry.append(line)

    # Save last entry
    if current_entry:
        pending_entries.append((current_score, '\n'.join(current_entry)))

    return preamble, do_not_apply, in_progress, pending_entries

def build_entry(job):
    """Build a queue entry markdown block from job JSON."""
    score = job.get('score', 0)
    company = job.get('company', 'Unknown')
    title = job.get('title', 'Unknown')
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        f"### [{score}] {company} — {title}",
        f"- **Score Breakdown:** {job.get('scoreBreakdown', f'total={score}')}",
        f"- **URL:** {job.get('url', '')}",
        f"- **Location:** {job.get('location', 'Unknown')}",
    ]

    if job.get('salary'):
        lines.append(f"- **Salary:** {job['salary']}")
    if job.get('companyInfo'):
        lines.append(f"- **Company:** {job['companyInfo']}")
    if job.get('h1b'):
        lines.append(f"- **H-1B:** {job['h1b']}")

    lines.append(f"- **Source:** {job.get('source', 'Search Agent')}")
    lines.append(f"- **Discovered:** {now}")
    lines.append(f"- **Status:** PENDING")

    if not job.get('autoApply', True):
        company_lower = company.lower()
        if 'openai' in company_lower:
            lines.append(f"- **⚠️ OPENAI LIMIT:** DO NOT AUTO-APPLY. WhatsApp Howard first.")
        elif 'databricks' in company_lower:
            lines.append(f"- **⚠️ DATABRICKS:** Cross-origin iframe — Howard applies manually.")
        else:
            lines.append(f"- **Auto-Apply:** NO")

    if job.get('whyMatch'):
        lines.append(f"- **Why notable:** {job['whyMatch']}")

    return '\n'.join(lines)

def check_duplicate(url, company, title, pending_entries):
    """Check if job already exists in pending entries."""
    url_lower = url.lower()
    ct_lower = f"{company.lower()}|{title.lower()}"

    for _, block in pending_entries:
        if url_lower in block.lower():
            return True
        # Check company+title combo
        block_lower = block.lower()
        if company.lower() in block_lower and title.lower() in block_lower:
            return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 add-to-queue.py '<JSON>'")
        sys.exit(1)

    try:
        job = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON: {e}")
        sys.exit(1)

    company = job.get('company', '')
    title = job.get('title', '')
    url = job.get('url', '')
    score = job.get('score', 0)

    # Check skip companies
    if company.lower() in SKIP_COMPANIES and job.get('autoApply', True):
        job['autoApply'] = False

    # Parse current queue
    preamble, do_not_apply, in_progress, pending_entries = parse_queue()

    # Check duplicate
    if check_duplicate(url, company, title, pending_entries):
        print(f"DUPLICATE — {company} — {title} already in queue")
        sys.exit(0)

    # Build new entry
    new_entry = build_entry(job)
    pending_entries.append((score, new_entry))

    # Sort by score descending
    pending_entries.sort(key=lambda x: x[0], reverse=True)

    # Count pending
    pending_count = len(pending_entries)

    # Update stats in preamble
    preamble_text = '\n'.join(preamble)
    preamble_text = re.sub(
        r'Pending: \d+',
        f'Pending: {pending_count}',
        preamble_text
    )
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M CT')
    preamble_text = re.sub(
        r'Last Search: .*',
        f'Last Search: {now_str}',
        preamble_text
    )

    # Rebuild queue file
    output = preamble_text + '\n'
    output += '\n'.join(do_not_apply) + '\n'
    output += '\n'.join(in_progress) + '\n'
    output += '\n## PENDING (sorted by priority score, highest first)\n\n'

    for _, block in pending_entries:
        output += block + '\n\n'

    with open(QUEUE_PATH, 'w') as f:
        f.write(output)

    print(f"ADDED [{score}] {company} — {title} ({pending_count} pending)")

if __name__ == '__main__':
    main()
