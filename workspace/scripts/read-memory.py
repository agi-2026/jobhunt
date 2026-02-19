#!/usr/bin/env python3
"""
Multi-layer memory reader for agents. Returns only relevant memory tier.

Usage:
  python3 scripts/read-memory.py hot              # Always-needed context (~2KB)
  python3 scripts/read-memory.py warm ats          # ATS patterns
  python3 scripts/read-memory.py warm companies    # Company-specific notes
  python3 scripts/read-memory.py warm failures     # Recent failure patterns
  python3 scripts/read-memory.py warm session       # Today's session log
  python3 scripts/read-memory.py stats              # Pipeline + daily stats from tracker

Hot tier (~2KB): Loaded every session — critical context
Warm tier: Loaded on-demand — specific knowledge areas
Cold tier: Archived — never loaded into agents (read via dashboard)
"""
import sys
import os
import re
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
MEMORY_DIR = os.path.join(WORKSPACE, 'memory')
TRACKER_PATH = os.path.join(WORKSPACE, 'job-tracker.md')
QUEUE_PATH = os.path.join(WORKSPACE, 'job-queue.md')

def read_file(path):
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return ''

def get_hot_memory():
    """Critical context that every agent session needs. ~2KB."""
    today = datetime.now().strftime('%Y-%m-%d')
    h1b_deadline = datetime(2026, 3, 15)
    days_left = (h1b_deadline - datetime.now()).days

    # Get pipeline counts from tracker
    tracker = read_file(TRACKER_PATH)
    pipeline = {}
    for m in re.finditer(r'\|\s*([\w\s/]+?)\s*\|\s*(\d+)\s*\|', tracker):
        stage = m.group(1).strip()
        if stage not in ('Stage', '---', 'Date', 'Name'):
            pipeline[stage] = int(m.group(2))

    # Get queue stats
    queue = read_file(QUEUE_PATH)
    pending_m = re.search(r'Pending:\s*(\d+)', queue)
    pending_count = int(pending_m.group(1)) if pending_m else 0

    # Get today's session highlights
    session_file = os.path.join(MEMORY_DIR, f'session-{today}.md')
    session = read_file(session_file)
    session_lines = [l for l in session.split('\n') if l.strip() and not l.startswith('#')]
    recent_actions = session_lines[-5:] if session_lines else ['No applications today yet']

    # Top 3 error patterns from recent sessions
    ats_patterns = read_file(os.path.join(MEMORY_DIR, 'ats-patterns.md'))
    critical_patterns = []
    for line in ats_patterns.split('\n'):
        if any(kw in line.lower() for kw in ['must', 'always', 'never', 'fix', 'bug', 'fail']):
            critical_patterns.append(line.strip())
    critical_patterns = critical_patterns[:5]

    output = f"""## HOT MEMORY — {today}
H-1B: {days_left} days left | OPT expires May 2026
Pipeline: {' | '.join(f'{k}:{v}' for k,v in pipeline.items() if v > 0)}
Queue: {pending_count} pending

### Today's Activity
{chr(10).join(recent_actions)}

### Critical Patterns
{chr(10).join(critical_patterns) if critical_patterns else 'No critical patterns logged yet'}

### Active Rules
- Greenhouse: Verify name/email after autofill, Disability→"I do not wish to answer"
- Ashby: Toggle buttons need simulateRealClick()
- SKIP: OpenAI (manual), Databricks (iframe), Workday (complex)
- Upload timeout: 60s minimum, use inputRef not click
"""
    return output

def get_warm_memory(topic):
    """On-demand knowledge areas."""
    if topic == 'ats':
        return read_file(os.path.join(MEMORY_DIR, 'ats-patterns.md'))
    elif topic == 'companies':
        return read_file(os.path.join(MEMORY_DIR, 'company-notes.md'))
    elif topic == 'failures':
        return read_file(os.path.join(MEMORY_DIR, 'failure-log.md'))
    elif topic == 'session':
        today = datetime.now().strftime('%Y-%m-%d')
        return read_file(os.path.join(MEMORY_DIR, f'session-{today}.md'))
    else:
        return f"Unknown warm topic: {topic}. Available: ats, companies, failures, session"

def get_stats():
    """Pipeline + daily stats from tracker, compact format."""
    tracker = read_file(TRACKER_PATH)

    # Extract pipeline table
    pipeline_lines = []
    in_pipeline = False
    for line in tracker.split('\n'):
        if '| Stage |' in line:
            in_pipeline = True
        if in_pipeline:
            pipeline_lines.append(line)
            if line.strip() == '' or (in_pipeline and '|' not in line and line.strip()):
                break

    # Extract daily stats table
    daily_lines = []
    in_daily = False
    for line in tracker.split('\n'):
        if '| Date |' in line:
            in_daily = True
        if in_daily:
            daily_lines.append(line)
            if line.strip() == '' or (in_daily and '|' not in line and line.strip()):
                break

    output = "## Pipeline\n" + '\n'.join(pipeline_lines)
    output += "\n\n## Daily Stats\n" + '\n'.join(daily_lines)
    return output

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 read-memory.py <hot|warm|stats> [topic]")
        print("  hot            - Critical context (~2KB)")
        print("  warm <topic>   - On-demand: ats, companies, failures, session")
        print("  stats          - Pipeline + daily stats")
        sys.exit(1)

    tier = sys.argv[1]

    if tier == 'hot':
        print(get_hot_memory())
    elif tier == 'warm':
        topic = sys.argv[2] if len(sys.argv) > 2 else 'ats'
        print(get_warm_memory(topic))
    elif tier == 'stats':
        print(get_stats())
    else:
        print(f"Unknown tier: {tier}")
        sys.exit(1)

if __name__ == '__main__':
    main()
