#!/usr/bin/env python3
"""
Log/check Application Orchestrator cycle status.

Write mode:
  python3 scripts/log-orchestrator-cycle.py \
    --ashby SPAWNED --greenhouse SKIPPED_EMPTY --lever SKIPPED_LOCKED \
    --runid-ashby run_123

Freshness check mode:
  python3 scripts/log-orchestrator-cycle.py --check-fresh --max-age-min 10
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
import fcntl

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
LOG_DIR = os.path.join(WORKSPACE, "logs")
LOG_PATH = os.path.join(LOG_DIR, "orchestrator-cycles.jsonl")
LOCK_PATH = os.path.join(LOG_DIR, ".orchestrator-cycles.lock")
VALID_STATUS = {
    "SPAWNED",
    "SKIPPED_LOCKED",
    "SKIPPED_EMPTY",
    "SKIPPED_NOT_CHOSEN",
    "ERROR",
    "UNKNOWN",
}

# Backward-compatible aliases used in older orchestrator prompts.
STATUS_ALIAS = {
    "SKIPPED_NOT_HIGHEST": "SKIPPED_NOT_CHOSEN",
    "SKIPPED_MODE": "UNKNOWN",
}


def _ensure_paths() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def _read_latest_entry():
    if not os.path.exists(LOG_PATH):
        return None
    last = ""
    with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.strip():
                last = line.strip()
    if not last:
        return None
    try:
        return json.loads(last)
    except json.JSONDecodeError:
        return None


def _append_entry(entry: dict) -> None:
    _ensure_paths()
    with open(LOCK_PATH, "w", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=True) + "\n")
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


def check_fresh(max_age_min: int) -> int:
    latest = _read_latest_entry()
    if not latest:
        print("STALE: no orchestrator cycle log found")
        return 2

    ts_ms = int(latest.get("timestamp_ms", 0) or 0)
    if ts_ms <= 0:
        print("STALE: latest orchestrator cycle log missing timestamp")
        return 2

    age_min = (int(time.time() * 1000) - ts_ms) / 60000.0
    if age_min > max_age_min:
        print(f"STALE: last cycle {age_min:.1f} min ago (> {max_age_min} min)")
        return 2

    statuses = latest.get("statuses", {})
    print(
        "OK: "
        f"last_cycle_age_min={age_min:.1f} "
        f"ashby={statuses.get('ashby', 'UNKNOWN')} "
        f"greenhouse={statuses.get('greenhouse', 'UNKNOWN')} "
        f"lever={statuses.get('lever', 'UNKNOWN')} "
        f"spawned={latest.get('spawned_count', 0)}"
    )
    return 0


def normalize_status(raw: str) -> str:
    v = (raw or "").strip().upper()
    v = STATUS_ALIAS.get(v, v)
    if v not in VALID_STATUS:
        raise ValueError(f"Invalid status '{raw}'. Valid: {', '.join(sorted(VALID_STATUS))}")
    return v


def main() -> int:
    parser = argparse.ArgumentParser(description="Log/check orchestrator cycle status")
    parser.add_argument("--check-fresh", action="store_true", help="Only check latest cycle freshness")
    parser.add_argument("--max-age-min", type=int, default=10, help="Freshness threshold in minutes")
    parser.add_argument("--ashby", default="UNKNOWN")
    parser.add_argument("--greenhouse", default="UNKNOWN")
    parser.add_argument("--lever", default="UNKNOWN")
    parser.add_argument("--runid-ashby", default="")
    parser.add_argument("--runid-greenhouse", default="")
    parser.add_argument("--runid-lever", default="")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    if args.check_fresh:
        return check_fresh(args.max_age_min)

    try:
        ashby = normalize_status(args.ashby)
        greenhouse = normalize_status(args.greenhouse)
        lever = normalize_status(args.lever)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    statuses = {"ashby": ashby, "greenhouse": greenhouse, "lever": lever}
    run_ids = {
        "ashby": args.runid_ashby.strip(),
        "greenhouse": args.runid_greenhouse.strip(),
        "lever": args.runid_lever.strip(),
    }
    entry = {
        "timestamp_ms": int(now.timestamp() * 1000),
        "timestamp_iso": now.isoformat(),
        "statuses": statuses,
        "spawned_count": sum(1 for s in statuses.values() if s == "SPAWNED"),
        "run_ids": run_ids,
        "note": args.note.strip(),
        "pid": os.getpid(),
    }
    _append_entry(entry)

    print(
        f"ORCH_GUARDRAIL {entry['timestamp_iso']} "
        f"ashby={ashby} greenhouse={greenhouse} lever={lever} "
        f"spawned={entry['spawned_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
