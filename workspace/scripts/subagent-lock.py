#!/usr/bin/env python3
"""Subagent lock manager. Prevents duplicate subagent spawning.

Usage:
  python3 scripts/subagent-lock.py check <ats_type>   → LOCKED or UNLOCKED
  python3 scripts/subagent-lock.py lock <ats_type>     → creates lock file
  python3 scripts/subagent-lock.py unlock <ats_type>   → removes lock file

Lock files: ~/.openclaw/workspace/.locks/apply-<type>.lock
Stale locks auto-expire after 25 minutes (subagent timeout 15min + 10min buffer).
"""

import sys
import os
import time

LOCKS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
    ".locks"
)
STALE_SECONDS = 25 * 60  # 25 minutes (15m timeout + 10m buffer)


def lock_path(ats_type):
    return os.path.join(LOCKS_DIR, f"apply-{ats_type}.lock")


def is_stale(path):
    try:
        age = time.time() - os.path.getmtime(path)
        if age > STALE_SECONDS:
            return True

        # Lock file format:
        #   line1: unix timestamp
        #   line2: pid
        # If pid is gone, treat lock as stale even before ttl.
        with open(path, "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        if len(lines) >= 2:
            try:
                pid = int(lines[1])
                os.kill(pid, 0)
            except (ValueError, ProcessLookupError):
                return True
            except PermissionError:
                # Process exists but belongs to another user; keep lock.
                pass
        return False
    except OSError:
        return True


def cmd_check(ats_type):
    path = lock_path(ats_type)
    if os.path.exists(path):
        if is_stale(path):
            os.remove(path)
            print("UNLOCKED (stale lock removed)")
        else:
            age_min = (time.time() - os.path.getmtime(path)) / 60
            print(f"LOCKED ({age_min:.0f}min ago)")
    else:
        print("UNLOCKED")


def cmd_lock(ats_type):
    os.makedirs(LOCKS_DIR, exist_ok=True)
    path = lock_path(ats_type)
    with open(path, "w") as f:
        f.write(f"{int(time.time())}\n{os.getpid()}\n")
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
