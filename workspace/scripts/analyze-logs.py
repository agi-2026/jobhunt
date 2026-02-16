#!/usr/bin/env python3
"""
Log analysis script for the job search agent system.
Parses cron logs to identify failure patterns, timing issues, and improvement areas.

Usage:
  python3 scripts/analyze-logs.py                    # Today's analysis
  python3 scripts/analyze-logs.py --date 2026-02-15  # Specific date
  python3 scripts/analyze-logs.py --summary          # Compact summary for WhatsApp

Output: Markdown report with actionable insights
"""
import sys
import os
import json
import re
from datetime import datetime, timedelta
from collections import defaultdict

LOG_DIR = '/tmp/openclaw'
WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
ANALYSIS_DIR = os.path.join(WORKSPACE, 'analysis')

def ensure_analysis_dir():
    os.makedirs(ANALYSIS_DIR, exist_ok=True)

def find_log_file(date_str=None):
    """Find the log file for a given date."""
    if date_str is None:
        date_str = datetime.now().strftime('%Y-%m-%d')

    log_path = os.path.join(LOG_DIR, f'openclaw-{date_str}.log')
    if os.path.exists(log_path):
        return log_path

    # Fallback: look for any recent log
    for f in sorted(os.listdir(LOG_DIR), reverse=True):
        if f.startswith('openclaw-') and f.endswith('.log'):
            return os.path.join(LOG_DIR, f)

    return None

def parse_log_entries(log_path, max_bytes=50_000_000):
    """Parse log file for agent-related entries. Handles large files."""
    entries = {
        'errors': [],
        'timeouts': [],
        'successes': [],
        'agent_runs': defaultdict(list),
        'browser_errors': [],
        'token_errors': [],
    }

    file_size = os.path.getsize(log_path)
    # Read last 50MB max
    start_pos = max(0, file_size - max_bytes)

    with open(log_path, 'r', errors='ignore') as f:
        if start_pos > 0:
            f.seek(start_pos)
            f.readline()  # Skip partial line

        for line in f:
            line = line.strip()
            if not line:
                continue

            # Try to parse as JSON log entry
            try:
                entry = json.loads(line)
                level = entry.get('level', '').lower()
                msg = entry.get('msg', '') or entry.get('message', '') or ''
                agent = entry.get('agent', '') or entry.get('jobName', '') or ''
                ts = entry.get('time', '') or entry.get('timestamp', '')

                if level in ('error', 'fatal'):
                    entries['errors'].append({
                        'time': ts, 'agent': agent, 'message': msg[:200],
                        'details': str(entry.get('error', ''))[:200]
                    })

                if 'timeout' in msg.lower() or 'timed out' in msg.lower():
                    entries['timeouts'].append({
                        'time': ts, 'agent': agent, 'message': msg[:200]
                    })

                if 'browser' in msg.lower() and level == 'error':
                    entries['browser_errors'].append({
                        'time': ts, 'message': msg[:200]
                    })

                if 'token' in msg.lower() and ('expired' in msg.lower() or 'invalid' in msg.lower()):
                    entries['token_errors'].append({
                        'time': ts, 'message': msg[:200]
                    })

                if 'completed' in msg.lower() or 'finished' in msg.lower():
                    entries['successes'].append({
                        'time': ts, 'agent': agent, 'message': msg[:200]
                    })

                continue
            except (json.JSONDecodeError, ValueError):
                pass

            # Plain text log parsing
            line_lower = line.lower()
            if 'error' in line_lower:
                entries['errors'].append({'time': '', 'agent': '', 'message': line[:200], 'details': ''})
            if 'timeout' in line_lower:
                entries['timeouts'].append({'time': '', 'agent': '', 'message': line[:200]})

    return entries

def generate_report(entries, date_str):
    """Generate markdown analysis report."""
    report = [f"# Daily Analysis Report — {date_str}"]
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # Error summary
    error_count = len(entries['errors'])
    timeout_count = len(entries['timeouts'])
    browser_errors = len(entries['browser_errors'])
    token_errors = len(entries['token_errors'])

    report.append("## Summary")
    report.append(f"- Errors: {error_count}")
    report.append(f"- Timeouts: {timeout_count}")
    report.append(f"- Browser errors: {browser_errors}")
    report.append(f"- Token errors: {token_errors}")
    report.append(f"- Successes: {len(entries['successes'])}")
    report.append("")

    # Error patterns
    if entries['errors']:
        report.append("## Error Patterns")
        error_msgs = defaultdict(int)
        for e in entries['errors']:
            # Normalize error messages for grouping
            msg = e['message']
            msg = re.sub(r'\b\d{10,}\b', '<ID>', msg)  # Remove long IDs
            msg = re.sub(r'https?://\S+', '<URL>', msg)  # Remove URLs
            error_msgs[msg[:100]] += 1

        for msg, count in sorted(error_msgs.items(), key=lambda x: -x[1])[:10]:
            report.append(f"- ({count}x) {msg}")
        report.append("")

    # Timeout patterns
    if entries['timeouts']:
        report.append("## Timeout Patterns")
        for t in entries['timeouts'][:5]:
            report.append(f"- [{t.get('agent', '?')}] {t['message'][:150]}")
        report.append("")

    # Browser-specific issues
    if entries['browser_errors']:
        report.append("## Browser Issues")
        for b in entries['browser_errors'][:5]:
            report.append(f"- {b['message'][:150]}")
        report.append("")

    # Recommendations
    report.append("## Recommendations")
    if timeout_count > 5:
        report.append("- HIGH: Frequent timeouts — consider increasing timeout or simplifying agent tasks")
    if browser_errors > 3:
        report.append("- HIGH: Browser errors frequent — check if pages have changed structure")
    if token_errors > 0:
        report.append("- MEDIUM: Token errors detected — check OAuth refresh automation")
    if error_count > 20:
        report.append("- HIGH: High error rate — review agent prompts and error handling")
    if error_count == 0:
        report.append("- System running cleanly!")

    report.append("")
    return '\n'.join(report)

def generate_summary(entries, date_str):
    """Compact summary for WhatsApp delivery."""
    error_count = len(entries['errors'])
    timeout_count = len(entries['timeouts'])
    success_count = len(entries['successes'])

    lines = [f"Analysis {date_str}:"]
    lines.append(f"Errors: {error_count} | Timeouts: {timeout_count} | OK: {success_count}")

    if entries['errors']:
        error_msgs = defaultdict(int)
        for e in entries['errors']:
            msg = e['message'][:60]
            error_msgs[msg] += 1
        top_errors = sorted(error_msgs.items(), key=lambda x: -x[1])[:3]
        lines.append("Top errors:")
        for msg, count in top_errors:
            lines.append(f"  ({count}x) {msg}")

    if error_count == 0 and timeout_count == 0:
        lines.append("All systems nominal!")

    return '\n'.join(lines)

def main():
    date_str = datetime.now().strftime('%Y-%m-%d')
    summary_mode = False

    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == '--date' and i + 1 < len(args):
            date_str = args[i + 1]
        elif arg == '--summary':
            summary_mode = True

    log_path = find_log_file(date_str)
    if not log_path:
        print(f"No log file found for {date_str}")
        sys.exit(1)

    entries = parse_log_entries(log_path)

    if summary_mode:
        print(generate_summary(entries, date_str))
        return

    ensure_analysis_dir()
    report = generate_report(entries, date_str)

    # Save report
    report_path = os.path.join(ANALYSIS_DIR, f'daily-report-{date_str}.md')
    with open(report_path, 'w') as f:
        f.write(report)

    print(report)
    print(f"\nSaved to: {report_path}")

if __name__ == '__main__':
    main()
