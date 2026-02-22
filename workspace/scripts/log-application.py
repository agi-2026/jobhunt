#!/usr/bin/env python3
"""
log-application.py — Append a structured entry to workspace/logs/applications.jsonl

Usage:
    python3 scripts/log-application.py <url> <company> <title> <ats> <outcome> [--duration N] [--note "text"]

Outcomes: SUBMITTED, SKIPPED, DEFERRED, ERROR
ATS types: ashby, greenhouse, lever

Called by subagents after each application attempt:
    exec: python3 scripts/log-application.py "https://..." "Company" "Title" "greenhouse" "SUBMITTED"
"""

import sys
import os
import json
import argparse
import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LOG_DIR = os.path.join(WORKSPACE, "logs")
LOG_FILE = os.path.join(LOG_DIR, "applications.jsonl")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("company")
    parser.add_argument("title")
    parser.add_argument("ats", choices=["ashby", "greenhouse", "lever", "other"])
    parser.add_argument("outcome", choices=["SUBMITTED", "SKIPPED", "DEFERRED", "ERROR"])
    parser.add_argument("--duration", type=int, default=0, help="Duration in seconds")
    parser.add_argument("--note", default="", help="Optional note")
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)

    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "url": args.url,
        "company": args.company,
        "title": args.title,
        "ats": args.ats,
        "outcome": args.outcome,
        "duration_s": args.duration,
        "note": args.note,
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"LOGGED: {args.outcome} | {args.company} — {args.title} [{args.ats}]")


if __name__ == "__main__":
    main()
