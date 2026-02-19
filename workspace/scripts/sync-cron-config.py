#!/usr/bin/env python3
"""Sync canonical repo cron config to active OpenClaw cron config.

Default behavior:
- validate both JSON files
- preserve target job state fields by id/name
- backup target config
- write synced config
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SOURCE_PATH = os.path.join(REPO_ROOT, "cron", "jobs.json")
TARGET_PATH = os.path.expanduser("~/.openclaw/cron/jobs.json")
BACKUP_DIR = os.path.expanduser("~/.openclaw/cron/backups")


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def strip_runtime_state(data: dict) -> dict:
    """Return a comparable config view without volatile runtime state fields."""
    out = {"version": data.get("version", 1), "jobs": []}
    for job in data.get("jobs", []):
        j = dict(job)
        j.pop("state", None)
        out["jobs"].append(j)
    return out


def stable_hash_json(data: dict) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def merge_states(source: dict, target: dict) -> dict:
    by_id = {j.get("id"): j for j in target.get("jobs", []) if j.get("id")}
    by_name = {j.get("name"): j for j in target.get("jobs", []) if j.get("name")}
    merged = {"version": source.get("version", 1), "jobs": []}
    for job in source.get("jobs", []):
        out = dict(job)
        t = by_id.get(job.get("id")) or by_name.get(job.get("name"))
        if t and "state" in t:
            out["state"] = t["state"]
        merged["jobs"].append(out)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync repo cron/jobs.json to ~/.openclaw/cron/jobs.json")
    parser.add_argument("--check", action="store_true", help="Check drift only; do not write")
    parser.add_argument("--no-preserve-state", action="store_true", help="Do not merge runtime state fields")
    parser.add_argument("--strict", action="store_true", help="Compare raw file hash (includes volatile state)")
    args = parser.parse_args()

    if not os.path.exists(SOURCE_PATH):
        print(f"ERROR: source not found: {SOURCE_PATH}", file=sys.stderr)
        return 1
    if not os.path.exists(TARGET_PATH):
        print(f"ERROR: target not found: {TARGET_PATH}", file=sys.stderr)
        return 1

    source = load_json(SOURCE_PATH)
    target = load_json(TARGET_PATH)

    source_hash = sha256_of(SOURCE_PATH)
    target_hash = sha256_of(TARGET_PATH)
    source_stable_hash = stable_hash_json(strip_runtime_state(source))
    target_stable_hash = stable_hash_json(strip_runtime_state(target))
    same = source_hash == target_hash
    same_stable = source_stable_hash == target_stable_hash

    print(f"SOURCE: {SOURCE_PATH}")
    print(f"TARGET: {TARGET_PATH}")
    print(f"HASH_SOURCE: {source_hash}")
    print(f"HASH_TARGET: {target_hash}")
    print(f"STABLE_HASH_SOURCE: {source_stable_hash}")
    print(f"STABLE_HASH_TARGET: {target_stable_hash}")
    print(f"DRIFT_STRICT: {'NO' if same else 'YES'}")
    print(f"DRIFT_STABLE: {'NO' if same_stable else 'YES'}")

    drift = (not same) if args.strict else (not same_stable)

    if args.check:
        return 0 if not drift else 2

    if not drift:
        print("No changes written (already in sync).")
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"jobs-{ts}.json")
    shutil.copy2(TARGET_PATH, backup_path)
    print(f"BACKUP: {backup_path}")

    out_data = source if args.no_preserve_state else merge_states(source, target)
    with open(TARGET_PATH, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
        f.write("\n")
    print("SYNC_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

