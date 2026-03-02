#!/usr/bin/env python3
"""archive-orchestrator-session.py

Archives the orchestrator's isolated session file when it exceeds a size threshold,
preventing context overflow that causes the orchestrator to time out every run.

Safe to call from watchdog every 2 min — skips if a run is currently active.

Usage:
  python3 scripts/archive-orchestrator-session.py [--force] [--dry-run]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

# Orchestrator cron job ID and its persistent session ID
ORCH_JOB_ID = "b2a0f25e-bd8a-43de-bf77-68802c7c9a0f"
SESSION_ID = "5cc4750d-8665-4570-a829-036e85c3cbcf"

SESSIONS_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
JOBS_FILE = os.path.expanduser("~/.openclaw/cron/jobs.json")

# Archive when EITHER threshold is exceeded
SIZE_THRESHOLD_BYTES = 400 * 1024   # 400KB (overflow historically at ~677KB)
LINE_THRESHOLD = 120                 # lines (overflow historically at ~187 lines)

# If a run started within this many seconds, assume it may still be active → skip
RUN_ACTIVE_GRACE_SECS = 90


def is_orchestrator_active(jobs_file: str) -> tuple[bool, str]:
    """Returns (active, reason). Active means a run may currently be executing."""
    try:
        with open(jobs_file) as f:
            data = json.load(f)
        for job in data.get("jobs", []):
            if job.get("id") == ORCH_JOB_ID:
                state = job.get("state", {})
                last_run_ms = state.get("lastRunAtMs", 0)
                last_dur_ms = state.get("lastDurationMs", 0)
                now_ms = time.time() * 1000
                elapsed_since_start_s = (now_ms - last_run_ms) / 1000
                # If run started within grace period, might still be executing
                if elapsed_since_start_s < RUN_ACTIVE_GRACE_SECS:
                    return True, f"run started {elapsed_since_start_s:.0f}s ago"
                return False, f"last run {elapsed_since_start_s:.0f}s ago (dur={last_dur_ms}ms)"
    except Exception as e:
        return False, f"jobs.json read error: {e}"
    return False, "job not found"


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive orchestrator session if too large")
    parser.add_argument("--force", action="store_true", help="Archive regardless of thresholds or active check")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done, don't archive")
    args = parser.parse_args()

    session_path = os.path.join(SESSIONS_DIR, f"{SESSION_ID}.jsonl")

    if not os.path.exists(session_path):
        print(f"Session not found: {session_path}")
        return 0

    stat = os.stat(session_path)
    size_bytes = stat.st_size

    with open(session_path, "r", encoding="utf-8", errors="ignore") as f:
        line_count = sum(1 for _ in f)

    size_kb = size_bytes // 1024
    size_threshold_kb = SIZE_THRESHOLD_BYTES // 1024

    if not args.force:
        # Check thresholds
        over_size = size_bytes >= SIZE_THRESHOLD_BYTES
        over_lines = line_count >= LINE_THRESHOLD

        if not over_size and not over_lines:
            print(
                f"OK: session {size_kb}KB / {line_count} lines "
                f"(thresholds: {size_threshold_kb}KB / {LINE_THRESHOLD} lines)"
            )
            return 0

        reason = []
        if over_size:
            reason.append(f"size {size_kb}KB >= {size_threshold_kb}KB")
        if over_lines:
            reason.append(f"lines {line_count} >= {LINE_THRESHOLD}")
        trigger = " AND ".join(reason)

        # Check if orchestrator is actively running
        active, active_reason = is_orchestrator_active(JOBS_FILE)
        if active:
            print(f"SKIP: {trigger} — but orchestrator is active ({active_reason}). Will retry next cycle.")
            return 0
        print(f"ARCHIVING: {trigger} ({active_reason})")
    else:
        print(f"FORCE: archiving {size_kb}KB / {line_count} lines session")

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    archive_name = f"{SESSION_ID}.jsonl.archived-{ts}"
    archive_path = os.path.join(SESSIONS_DIR, archive_name)

    if args.dry_run:
        print(f"DRY-RUN: would rename → {archive_name}")
        return 0

    os.rename(session_path, archive_path)
    print(f"Archived {size_kb}KB / {line_count} lines → {archive_name}")

    # Remove lock file if it exists (stale after archiving)
    lock_path = session_path + ".lock"
    if os.path.exists(lock_path):
        os.remove(lock_path)
        print(f"Removed stale lock: {os.path.basename(lock_path)}")

    # Prune old archives — keep only the 5 most recent
    archives = sorted(
        [f for f in os.listdir(SESSIONS_DIR) if f.startswith(f"{SESSION_ID}.jsonl.archived-")],
        reverse=True,
    )
    for old in archives[5:]:
        old_path = os.path.join(SESSIONS_DIR, old)
        try:
            os.remove(old_path)
            print(f"Pruned old archive: {old}")
        except OSError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
