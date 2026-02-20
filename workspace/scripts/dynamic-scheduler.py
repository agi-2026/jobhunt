#!/usr/bin/env python3
"""
Dynamic Scheduler — Adjusts Search Agent frequency based on yield patterns.

Reads yield history from yield-log.json and adjusts the Search Agent's cron
schedule in jobs.json. Run this from Health Monitor or as a standalone cron.

Usage:
  python3 scripts/dynamic-scheduler.py              # Adjust and report
  python3 scripts/dynamic-scheduler.py --dry-run    # Show what would change
  python3 scripts/dynamic-scheduler.py --status     # Show current yield stats

Logic:
  - Search Agent is hard-throttled to every 2 hours (apply-priority mode).
  - Application Agent remains adaptive based on pending queue depth.

The scheduler also adjusts the Application Agent:
  - If queue has 10+ PENDING jobs → every 2 min
  - If queue has 3-9 PENDING jobs → every 3 min
  - If queue has 0-2 PENDING jobs → every 5 min
"""
import sys
import os
import json
from datetime import datetime, timezone, timedelta
import re

OPENCLAW_DIR = os.path.expanduser('~/.openclaw')
JOBS_JSON = os.path.join(OPENCLAW_DIR, 'cron', 'jobs.json')
WORKSPACE = os.path.join(OPENCLAW_DIR, 'workspace')
YIELD_LOG = os.path.join(WORKSPACE, 'yield-log.json')
QUEUE_PATH = os.path.join(WORKSPACE, 'job-queue.md')

SEARCH_AGENT_NAME = 'Search Agent'
APP_AGENT_NAME = 'Application Agent'

# Search Agent is intentionally hard-throttled so apply lanes are not starved.
SEARCH_SCHEDULES = {
    'throttled': {'expr': '0 */2 * * *', 'label': 'every 2 hours (apply-priority guardrail)'},
}

# Schedule tiers for Application Agent
APP_SCHEDULES = {
    'busy':    {'expr': '*/2 * * * *',  'label': 'every 2 min (10+ pending)'},
    'normal':  {'expr': '*/3 * * * *',  'label': 'every 3 min (normal)'},
    'light':   {'expr': '*/5 * * * *',  'label': 'every 5 min (light queue)'},
}


def load_yield_log():
    """Load yield history."""
    if not os.path.exists(YIELD_LOG):
        return []
    try:
        with open(YIELD_LOG, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def get_recent_yields(entries, hours=1):
    """Get yield entries from the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()
    return [e for e in entries if e.get('timestamp', '') >= cutoff_iso]


def compute_search_tier():
    """Determine the appropriate search schedule tier."""
    return 'throttled', 'Apply-priority mode: search fixed at every 2 hours'


def get_pending_count():
    """Count pending jobs in queue."""
    try:
        with open(QUEUE_PATH, 'r') as f:
            content = f.read()
        return len(re.findall(r'^### \[\d+\]', content, re.MULTILINE))
    except Exception:
        return 0


def compute_app_tier():
    """Determine the appropriate application agent schedule tier."""
    now = datetime.now()
    if now.hour >= 23 or now.hour < 7:
        return 'light', 'Night hours'

    pending = get_pending_count()
    if pending >= 10:
        return 'busy', f'{pending} pending jobs — speed up applications'
    elif pending >= 3:
        return 'normal', f'{pending} pending jobs — normal pace'
    else:
        return 'light', f'{pending} pending jobs — slow down'


def load_jobs_json():
    """Load jobs.json."""
    with open(JOBS_JSON, 'r') as f:
        return json.load(f)


def save_jobs_json(data):
    """Save jobs.json."""
    with open(JOBS_JSON, 'w') as f:
        json.dump(data, f, indent=2)


def find_job(data, name):
    """Find a job entry by name."""
    for job in data.get('jobs', []):
        if job.get('name') == name:
            return job
    return None


def update_schedule(data, agent_name, new_expr):
    """Update a job's cron expression. Returns True if changed."""
    job = find_job(data, agent_name)
    if not job:
        return False
    current = job.get('schedule', {}).get('expr', '')
    if current == new_expr:
        return False
    job['schedule']['expr'] = new_expr
    job['updatedAtMs'] = int(datetime.now(timezone.utc).timestamp() * 1000)
    return True


def main():
    dry_run = '--dry-run' in sys.argv
    status_only = '--status' in sys.argv

    # Compute tiers
    search_tier, search_reason = compute_search_tier()
    app_tier, app_reason = compute_app_tier()

    search_schedule = SEARCH_SCHEDULES[search_tier]
    app_schedule = APP_SCHEDULES[app_tier]

    if status_only:
        entries = load_yield_log()
        recent = get_recent_yields(entries, hours=1)
        total_today = get_recent_yields(entries, hours=24)

        print(f"=== DYNAMIC SCHEDULER STATUS ===")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M CT')}")
        print(f"\nYield History:")
        print(f"  Last hour: {len(recent)} runs, {sum(e.get('new_count', 0) for e in recent)} new jobs")
        print(f"  Last 24h: {len(total_today)} runs, {sum(e.get('new_count', 0) for e in total_today)} new jobs")
        print(f"\nSearch Agent: {search_schedule['label']} ({search_reason})")
        print(f"Application Agent: {app_schedule['label']} ({app_reason})")
        print(f"Pending queue: {get_pending_count()} jobs")

        # Show last 5 yield entries
        if entries:
            print(f"\nRecent yields:")
            for e in entries[-5:]:
                ts = e.get('timestamp', '?')[:16]
                new = e.get('new_count', 0)
                dup = e.get('dup_count', 0)
                src = e.get('source', '?')
                print(f"  {ts} — {new} new, {dup} dup ({src})")
        return

    # Load current config
    data = load_jobs_json()

    changes = []

    # Check Search Agent
    search_job = find_job(data, SEARCH_AGENT_NAME)
    if search_job:
        current_expr = search_job.get('schedule', {}).get('expr', '')
        if current_expr != search_schedule['expr']:
            changes.append(f"Search Agent: {current_expr} → {search_schedule['expr']} ({search_reason})")
            if not dry_run:
                update_schedule(data, SEARCH_AGENT_NAME, search_schedule['expr'])

    # Check Application Agent
    app_job = find_job(data, APP_AGENT_NAME)
    if app_job:
        current_expr = app_job.get('schedule', {}).get('expr', '')
        if current_expr != app_schedule['expr']:
            changes.append(f"Application Agent: {current_expr} → {app_schedule['expr']} ({app_reason})")
            if not dry_run:
                update_schedule(data, APP_AGENT_NAME, app_schedule['expr'])

    if changes:
        if dry_run:
            print("DRY RUN — would make these changes:")
        else:
            save_jobs_json(data)
            print("UPDATED schedules:")
        for c in changes:
            print(f"  {c}")
    else:
        print(f"NO CHANGES — Search: {search_schedule['label']}, App: {app_schedule['label']}")


if __name__ == '__main__':
    main()
