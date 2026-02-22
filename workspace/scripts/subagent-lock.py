#!/usr/bin/env python3
"""Subagent lock manager. Prevents duplicate subagent spawning.

Usage:
  python3 scripts/subagent-lock.py check <ats_type>    -> LOCKED or UNLOCKED
  python3 scripts/subagent-lock.py lock <ats_type>     -> creates lock file
  python3 scripts/subagent-lock.py unlock <ats_type>   -> removes lock file

Lock files: ~/.openclaw/workspace/.locks/apply-<type>.lock
Stale TTL: ashby/ashby2/lever=15min, greenhouse=45min (no effective limit within 30min session timeout).

Design note:
  The lock is intentionally time-based (TTL), not PID-liveness based. Each
  `lock` action is created by a short-lived `exec` process, so PID checks would
  invalidate the lock immediately and allow overlapping subagents. We do
  additionally use subagent run/session heartbeat metadata to clear orphaned
  locks when a run has stalled.
"""

import os
import json
import socket
import sys
import time

LOCKS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    ".locks"
)
# Per-slot TTL: Greenhouse uses Sonnet on complex forms (can take 20-30 min per session).
# Ashby/Lever use Haiku and typically finish in 10-15 min.
SLOT_STALE_SECONDS = {
    "ashby":      15 * 60,   # 15 min
    "ashby2":     15 * 60,   # 15 min
    "greenhouse": 45 * 60,   # 45 min (30 min subagent timeout + 15 min buffer)
    "lever":      15 * 60,   # 15 min
}
DEFAULT_STALE_SECONDS = 20 * 60  # fallback for unknown slot names
ORPHAN_GRACE_SECONDS = 90
RUN_HEARTBEAT_TIMEOUT_SECONDS = 10 * 60  # 10 min — must match apply-watchdog.py
SUBAGENT_RUNS_PATH = os.path.expanduser("~/.openclaw/subagents/runs.json")
SESSION_STORE_PATH = os.path.expanduser("~/.openclaw/agents/main/sessions/sessions.json")
SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")


def lock_path(ats_type):
    return os.path.join(LOCKS_DIR, f"apply-{ats_type}.lock")


def _slot_ttl(ats_type: str) -> int:
    return SLOT_STALE_SECONDS.get(ats_type, DEFAULT_STALE_SECONDS)


def is_stale(path, ats_type: str = ""):
    try:
        ts = int(os.path.getmtime(path))
        with open(path, "r") as f:
            first = (f.readline() or "").strip()
            if first.isdigit():
                ts = int(first)

        age = time.time() - ts
        return age > _slot_ttl(ats_type)
    except (OSError, ValueError):
        return True


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _last_session_heartbeat_sec(run, session_store, now):
    child_key = str(run.get("childSessionKey") or "")
    if not child_key:
        return None

    entry = session_store.get(child_key) if isinstance(session_store, dict) else None
    if not isinstance(entry, dict):
        return None

    candidates = []
    updated_ms = entry.get("updatedAt")
    if isinstance(updated_ms, (int, float)):
        candidates.append(float(updated_ms) / 1000.0)

    session_id = entry.get("sessionId")
    if isinstance(session_id, str) and session_id:
        transcript = os.path.join(SESSION_DIR, f"{session_id}.jsonl")
        if os.path.exists(transcript):
            try:
                candidates.append(float(os.path.getmtime(transcript)))
            except OSError:
                pass

    if not candidates:
        return None
    return min(now, max(candidates))


def _run_is_active(run, session_store, now):
    if not isinstance(run, dict):
        return False
    if run.get("endedAt"):
        return False

    label = str(run.get("label", "")).lower()
    task = str(run.get("task", "")).lower()
    if not (label.startswith("apply-") or "subagent-lock.py lock apply" in task):
        return False

    started_ms = run.get("startedAt") or run.get("createdAt") or 0
    try:
        started_sec = float(started_ms) / 1000.0
    except (TypeError, ValueError):
        started_sec = now

    run_age_sec = max(0.0, now - started_sec)
    # Use the largest possible TTL for run-age check (greenhouse is longest)
    max_ttl = max(SLOT_STALE_SECONDS.values()) if SLOT_STALE_SECONDS else DEFAULT_STALE_SECONDS
    if run_age_sec > max_ttl:
        return False

    last_heartbeat = _last_session_heartbeat_sec(run, session_store, now)
    if last_heartbeat is None:
        # Allow short startup windows where session metadata is not persisted yet.
        return run_age_sec <= ORPHAN_GRACE_SECONDS

    heartbeat_age = max(0.0, now - last_heartbeat)
    if run_age_sec > ORPHAN_GRACE_SECONDS and heartbeat_age > RUN_HEARTBEAT_TIMEOUT_SECONDS:
        return False
    return True


def has_active_subagent_runs():
    """Check for running apply subagents using run + session heartbeat metadata."""
    data = _load_json(SUBAGENT_RUNS_PATH)
    if not data:
        # Unknown state: fail safe and assume active.
        return True

    runs = (data or {}).get("runs", {})
    if not isinstance(runs, dict):
        return True

    now = time.time()
    session_store = _load_json(SESSION_STORE_PATH)
    for run in runs.values():
        if _run_is_active(run, session_store, now):
            return True
    return False


def cmd_check(ats_type):
    path = lock_path(ats_type)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                first = (f.readline() or "").strip()
            ts = int(first) if first.isdigit() else int(os.path.getmtime(path))
        except (OSError, ValueError):
            ts = int(os.path.getmtime(path))
        age_sec = time.time() - ts

        # Auto-heal orphaned locks when no subagent is active.
        if age_sec > ORPHAN_GRACE_SECONDS and not has_active_subagent_runs():
            os.remove(path)
            print("UNLOCKED (orphan lock removed)")
            return

        if is_stale(path, ats_type):
            os.remove(path)
            print("UNLOCKED (stale lock removed)")
        else:
            age_min = (time.time() - ts) / 60
            ttl_min = _slot_ttl(ats_type) // 60
            print(f"LOCKED ({age_min:.0f}min ago, ttl={ttl_min}min)")
    else:
        print("UNLOCKED")


def cmd_lock(ats_type):
    os.makedirs(LOCKS_DIR, exist_ok=True)
    path = lock_path(ats_type)
    now = int(time.time())
    with open(path, "w") as f:
        f.write(f"{now}\n")
        f.write(f"pid={os.getpid()}\n")
        f.write(f"host={socket.gethostname()}\n")
    print(f"LOCKED apply-{ats_type}")


def cmd_unlock(ats_type):
    path = lock_path(ats_type)
    if os.path.exists(path):
        os.remove(path)
        print(f"UNLOCKED apply-{ats_type}")
    else:
        print(f"UNLOCKED (no lock existed)")


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/subagent-lock.py <check|lock|unlock> <ats_type>")
        sys.exit(1)

    action = sys.argv[1]
    ats_type = sys.argv[2]

    if action == "check":
        cmd_check(ats_type)
    elif action == "lock":
        cmd_lock(ats_type)
    elif action == "unlock":
        cmd_unlock(ats_type)
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
