#!/usr/bin/env python3
"""
Health check script for the job search agent system.
Reads jobs.json directly (no CLI timeout issues).
Returns structured health report.

Usage:
  python3 scripts/health-check.py              # Full health report
  python3 scripts/health-check.py --alert      # Only if something needs attention
  python3 scripts/health-check.py --json        # JSON output

Used by: Health Monitor cron job (runs every 30 min)
"""
import sys
import os
import json
from datetime import datetime, timezone

OPENCLAW_DIR = os.path.expanduser('~/.openclaw')
JOBS_JSON = os.path.join(OPENCLAW_DIR, 'cron', 'jobs.json')
WORKSPACE = os.path.join(OPENCLAW_DIR, 'workspace')
QUEUE_PATH = os.path.join(WORKSPACE, 'job-queue.md')
TRACKER_PATH = os.path.join(WORKSPACE, 'job-tracker.md')

H1B_DEADLINE_MS = int(datetime(2026, 3, 15, tzinfo=timezone.utc).timestamp() * 1000)

def get_agent_health():
    """Check all agents for errors, stale runs, stuck states."""
    with open(JOBS_JSON, 'r') as f:
        data = json.load(f)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    alerts = []
    agents = []

    for job in data.get('jobs', []):
        state = job.get('state', {})
        name = job.get('name', 'Unknown')
        enabled = job.get('enabled', True)
        last_status = state.get('lastStatus', '')
        consecutive_errors = state.get('consecutiveErrors', 0)
        last_run_ms = state.get('lastRunAtMs', 0)
        running_ms = state.get('runningAtMs', 0)
        last_duration_ms = state.get('lastDurationMs', 0)

        agent_info = {
            'name': name,
            'enabled': enabled,
            'status': last_status,
            'consecutive_errors': consecutive_errors,
            'last_run_ago_min': round((now_ms - last_run_ms) / 60000) if last_run_ms else None,
            'last_duration_sec': round(last_duration_ms / 1000) if last_duration_ms else None,
            'is_running': bool(running_ms and (now_ms - running_ms) < 1800000),
        }
        agents.append(agent_info)

        # Alert conditions
        if consecutive_errors >= 3:
            alerts.append(f"CRITICAL: {name} has {consecutive_errors} consecutive errors")
        elif consecutive_errors >= 1:
            alerts.append(f"WARNING: {name} has {consecutive_errors} error(s)")

        if last_run_ms and (now_ms - last_run_ms) > 3600000 and enabled:  # >1h since last run
            hours_ago = round((now_ms - last_run_ms) / 3600000, 1)
            alerts.append(f"WARNING: {name} hasn't run in {hours_ago}h")

        if running_ms and (now_ms - running_ms) > 1800000:  # stuck >30 min
            alerts.append(f"WARNING: {name} appears stuck (running for >{round((now_ms - running_ms)/60000)}m)")

        if last_duration_ms and last_duration_ms > 600000 and name != 'Application Agent':  # >10 min for non-apply
            alerts.append(f"INFO: {name} took {round(last_duration_ms/1000)}s last run (slow)")

    return agents, alerts

def get_queue_health():
    """Check queue for issues."""
    alerts = []
    try:
        with open(QUEUE_PATH, 'r') as f:
            content = f.read()

        import re
        pending_count = len(re.findall(r'^### \[\d+\]', content, re.MULTILINE))
        in_progress = content.count('## IN PROGRESS')

        if pending_count == 0:
            alerts.append("INFO: Job queue is empty — search agent may need attention")
        elif pending_count > 100:
            alerts.append(f"WARNING: Queue has {pending_count} pending jobs — may need compaction")

        # Check for stale IN PROGRESS
        ip_section = content.split('## IN PROGRESS')[-1].split('## ')[0] if '## IN PROGRESS' in content else ''
        ip_jobs = re.findall(r'^### \[\d+\].*$', ip_section, re.MULTILINE)
        if ip_jobs:
            alerts.append(f"WARNING: {len(ip_jobs)} jobs stuck IN PROGRESS")

        return {'pending': pending_count, 'in_progress': len(ip_jobs)}, alerts
    except Exception as e:
        return {'error': str(e)}, [f"ERROR: Cannot read queue: {e}"]

def get_pipeline_health():
    """Check application pipeline for anomalies."""
    alerts = []
    try:
        with open(TRACKER_PATH, 'r') as f:
            content = f.read()

        import re
        stages = {}
        for m in re.finditer(r'- \*\*Stage:\*\*\s*(.*)', content):
            stage = m.group(1).strip()
            stages[stage] = stages.get(stage, 0) + 1

        total_applied = sum(v for k, v in stages.items() if k != 'Discovered')
        phone_screens = stages.get('Phone Screen', 0)
        interviews = stages.get('Technical Interview', 0)

        if total_applied > 50 and phone_screens == 0 and interviews == 0:
            alerts.append(f"CONCERN: {total_applied} applications but 0 phone screens/interviews — review application quality")

        return stages, alerts
    except Exception as e:
        return {'error': str(e)}, [f"ERROR: Cannot read tracker: {e}"]

def main():
    alert_only = '--alert' in sys.argv
    json_mode = '--json' in sys.argv

    agents, agent_alerts = get_agent_health()
    queue, queue_alerts = get_queue_health()
    pipeline, pipeline_alerts = get_pipeline_health()

    all_alerts = agent_alerts + queue_alerts + pipeline_alerts

    # H-1B countdown
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    days_left = (H1B_DEADLINE_MS - now_ms) / 86400000
    if days_left < 14:
        all_alerts.insert(0, f"CRITICAL: H-1B deadline in {int(days_left)} days")

    if json_mode:
        print(json.dumps({
            'timestamp': datetime.now().isoformat(),
            'agents': agents,
            'queue': queue,
            'pipeline': pipeline,
            'alerts': all_alerts,
            'h1b_days_left': int(days_left),
        }, indent=2))
        return

    if alert_only and not all_alerts:
        print("OK — no alerts")
        return

    # Text output
    print(f"=== HEALTH CHECK — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    print(f"H-1B: {int(days_left)} days left\n")

    if all_alerts:
        print("ALERTS:")
        for a in all_alerts:
            print(f"  {a}")
        print()

    print("AGENTS:")
    for a in agents:
        status = "RUNNING" if a['is_running'] else a['status'].upper()
        errors = f" ({a['consecutive_errors']} errors)" if a['consecutive_errors'] else ""
        duration = f" [{a['last_duration_sec']}s]" if a['last_duration_sec'] else ""
        ago = f" {a['last_run_ago_min']}m ago" if a['last_run_ago_min'] else ""
        print(f"  {a['name']}: {status}{errors}{duration}{ago}")

    print(f"\nQUEUE: {queue.get('pending', '?')} pending | {queue.get('in_progress', '?')} in_progress")

    print(f"\nPIPELINE: {pipeline}")

if __name__ == '__main__':
    main()
