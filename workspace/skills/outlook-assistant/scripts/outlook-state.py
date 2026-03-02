#!/usr/bin/env python3
"""State management for Outlook Assistant — dismissed/snoozed items + scan cache.

Usage:
    python3 outlook-state.py dismiss <message_id> [--reason "text"]
    python3 outlook-state.py snooze <message_id> --hours 4
    python3 outlook-state.py is-dismissed <message_id>
    python3 outlook-state.py list-dismissed
    python3 outlook-state.py cache-scan '<json_results>'
    python3 outlook-state.py cleanup --older-than 30
"""
import argparse
import json
import os
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(SCRIPT_DIR, "..", "state")
DISMISSED_PATH = os.path.join(STATE_DIR, "dismissed.json")
SCAN_CACHE_PATH = os.path.join(STATE_DIR, "scan-cache.json")


def _ensure_state_dir():
    os.makedirs(STATE_DIR, exist_ok=True)


def _load_state(path):
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        return json.load(f)


def _save_state(path, data):
    _ensure_state_dir()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def dismiss(msg_id, reason=""):
    state = _load_state(DISMISSED_PATH)
    if "dismissed" not in state:
        state["dismissed"] = {}
    if "snoozed" not in state:
        state["snoozed"] = {}

    state["dismissed"][msg_id] = {
        "ts": int(time.time()),
        "reason": reason,
    }
    # Remove from snoozed if present
    state["snoozed"].pop(msg_id, None)
    _save_state(DISMISSED_PATH, state)
    print(f"DISMISSED: {msg_id}")


def snooze(msg_id, hours):
    state = _load_state(DISMISSED_PATH)
    if "snoozed" not in state:
        state["snoozed"] = {}
    until_ts = int(time.time()) + (hours * 3600)
    state["snoozed"][msg_id] = {"until_ts": until_ts}
    _save_state(DISMISSED_PATH, state)
    print(f"SNOOZED: {msg_id} until {hours}h from now")


def is_dismissed(msg_id):
    state = _load_state(DISMISSED_PATH)
    dismissed = state.get("dismissed", {})
    snoozed = state.get("snoozed", {})

    if msg_id in dismissed:
        print("DISMISSED")
        return True

    if msg_id in snoozed:
        until_ts = snoozed[msg_id].get("until_ts", 0)
        if time.time() < until_ts:
            remaining = (until_ts - time.time()) / 3600
            print(f"SNOOZED ({remaining:.1f}h remaining)")
            return True
        # Snooze expired
        print("NOT_DISMISSED (snooze expired)")
        return False

    print("NOT_DISMISSED")
    return False


def list_dismissed():
    state = _load_state(DISMISSED_PATH)
    dismissed = state.get("dismissed", {})
    snoozed = state.get("snoozed", {})

    if not dismissed and not snoozed:
        print("No dismissed or snoozed items.")
        return

    now = time.time()
    if dismissed:
        print(f"Dismissed ({len(dismissed)}):")
        for mid, info in sorted(dismissed.items(), key=lambda x: x[1].get("ts", 0), reverse=True):
            age_h = (now - info.get("ts", 0)) / 3600
            reason = info.get("reason", "")
            print(f"  {mid[:20]}... | {age_h:.0f}h ago | {reason}")

    active_snoozed = {k: v for k, v in snoozed.items() if v.get("until_ts", 0) > now}
    if active_snoozed:
        print(f"\nSnoozed ({len(active_snoozed)} active):")
        for mid, info in active_snoozed.items():
            remaining = (info["until_ts"] - now) / 3600
            print(f"  {mid[:20]}... | {remaining:.1f}h remaining")


def cache_scan(json_str):
    data = json.loads(json_str)
    data["cached_at"] = int(time.time())
    _save_state(SCAN_CACHE_PATH, data)
    count = data.get("count", len(data.get("items", [])))
    print(f"CACHED: {count} items")


def get_cached_scan():
    data = _load_state(SCAN_CACHE_PATH)
    if not data:
        print("NO_CACHE")
        return None
    cached_at = data.get("cached_at", 0)
    age_min = (time.time() - cached_at) / 60
    print(f"CACHE_AGE: {age_min:.0f} minutes")
    return data


def cleanup(older_than_days):
    state = _load_state(DISMISSED_PATH)
    cutoff = time.time() - (older_than_days * 86400)

    dismissed = state.get("dismissed", {})
    expired_snoozed = {k: v for k, v in state.get("snoozed", {}).items()
                       if v.get("until_ts", 0) < time.time()}

    old_dismissed = {k: v for k, v in dismissed.items() if v.get("ts", 0) < cutoff}
    for k in old_dismissed:
        del dismissed[k]
    for k in expired_snoozed:
        state.get("snoozed", {}).pop(k, None)

    state["dismissed"] = dismissed
    _save_state(DISMISSED_PATH, state)
    print(f"Cleaned up: {len(old_dismissed)} old dismissed, {len(expired_snoozed)} expired snoozed")


def main():
    parser = argparse.ArgumentParser(description="Outlook state manager")
    sub = parser.add_subparsers(dest="command")

    p_dismiss = sub.add_parser("dismiss")
    p_dismiss.add_argument("message_id")
    p_dismiss.add_argument("--reason", default="")

    p_snooze = sub.add_parser("snooze")
    p_snooze.add_argument("message_id")
    p_snooze.add_argument("--hours", type=float, required=True)

    p_is = sub.add_parser("is-dismissed")
    p_is.add_argument("message_id")

    sub.add_parser("list-dismissed")

    p_cache = sub.add_parser("cache-scan")
    p_cache.add_argument("json_data")

    sub.add_parser("get-cache")

    p_clean = sub.add_parser("cleanup")
    p_clean.add_argument("--older-than", type=int, default=30, help="Days")

    args = parser.parse_args()

    if args.command == "dismiss":
        dismiss(args.message_id, args.reason)
    elif args.command == "snooze":
        snooze(args.message_id, args.hours)
    elif args.command == "is-dismissed":
        is_dismissed(args.message_id)
    elif args.command == "list-dismissed":
        list_dismissed()
    elif args.command == "cache-scan":
        cache_scan(args.json_data)
    elif args.command == "get-cache":
        get_cached_scan()
    elif args.command == "cleanup":
        cleanup(args.older_than)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
