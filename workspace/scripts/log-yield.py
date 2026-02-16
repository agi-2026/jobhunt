#!/usr/bin/env python3
"""
Log yield data from search runs.

Called by search scripts (or Search Agent) to track how many new jobs
were found per run. Used by dynamic-scheduler.py to adjust frequencies.

Usage:
  python3 scripts/log-yield.py <new_count> <dup_count> [source]

Examples:
  python3 scripts/log-yield.py 5 3 "Ashby API"
  python3 scripts/log-yield.py 0 12 "Greenhouse API"
"""
import sys
import os
import json
from datetime import datetime, timezone

WORKSPACE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
YIELD_LOG = os.path.join(WORKSPACE, 'yield-log.json')
MAX_ENTRIES = 500  # Keep last 500 entries (~2 days at 5min intervals)

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 log-yield.py <new_count> <dup_count> [source]")
        sys.exit(1)

    new_count = int(sys.argv[1])
    dup_count = int(sys.argv[2])
    source = sys.argv[3] if len(sys.argv) > 3 else 'Search Agent'

    # Load existing log
    entries = []
    if os.path.exists(YIELD_LOG):
        try:
            with open(YIELD_LOG, 'r') as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            entries = []

    # Append new entry
    entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'new_count': new_count,
        'dup_count': dup_count,
        'source': source,
    }
    entries.append(entry)

    # Trim to max entries
    if len(entries) > MAX_ENTRIES:
        entries = entries[-MAX_ENTRIES:]

    # Save
    with open(YIELD_LOG, 'w') as f:
        json.dump(entries, f, indent=2)

    print(f"YIELD: {new_count} new, {dup_count} duplicate ({source})")

if __name__ == '__main__':
    main()
