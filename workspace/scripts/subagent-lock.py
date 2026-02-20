#!/usr/bin/env python3
"""Subagent lock manager. Prevents duplicate subagent spawning.

Usage:
  python3 scripts/subagent-lock.py check <ats_type>    -> LOCKED or UNLOCKED
  python3 scripts/subagent-lock.py lock <ats_type>     -> creates lock file
  python3 scripts/subagent-lock.py unlock <ats_type>   -> removes lock file

Lock files: ~/.openclaw/workspace/.locks/apply-<type>.lock
Stale locks auto-expire after 16 minutes (subagent timeout 15m + small buffer).

Design note:
  The lock is intentionally time-based (TTL), not PID-liveness based. Each
  `lock` action is created by a short-lived `exec` process, so PID checks would
  invalidate the lock immediately and allow overlapping subagents.
"""

import os
import socket
import sys
import time

LOCKS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    ".locks"
)
STALE_SECONDS = 16 * 60  # 16 minutes (15m timeout + small buffer)


def lock_path(ats_type):
    return os.path.join(LOCKS_DIR, f"apply-{ats_type}.lock")


def is_stale(path):
    try:
        ts = int(os.path.getmtime(path))
        with open(path, "r") as f:
            first = (f.readline() or "").strip()
            if first.isdigit():
                ts = int(first)

        age = time.time() - ts
        return age > STALE_SECONDS
    except (OSError, ValueError):
        return True


def cmd_check(ats_type):
    path = lock_path(ats_type)
    if os.path.exists(path):
        if is_stale(path):
            os.remove(path)
            print("UNLOCKED (stale lock removed)")
        else:
            try:
                with open(path, "r") as f:
                    first = (f.readline() or "").strip()
                ts = int(first) if first.isdigit() else int(os.path.getmtime(path))
            except (OSError, ValueError):
                ts = int(os.path.getmtime(path))
            age_min = (time.time() - ts) / 60
            print(f"LOCKED ({age_min:.0f}min ago)")
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
