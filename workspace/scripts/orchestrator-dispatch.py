#!/usr/bin/env python3
"""Deterministic dispatcher for Application Orchestrator.

Builds a single readiness snapshot for ashby/greenhouse/lever in one pass:
- lock status
- actionable queue depth
- top URL
- READY vs SKIPPED_* reason

Also emits adaptive suggestions based on backlog.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

from queue_utils import filter_jobs, read_queue_sections

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
QUEUE_PATH = os.path.join(WORKSPACE, "job-queue.md")
LOCK_PATH = os.path.join(WORKSPACE, ".queue.lock")
SCRIPTS_DIR = os.path.dirname(os.path.realpath(__file__))
ATS_TYPES = ["ashby", "greenhouse", "lever"]
NO_AUTO_COMPANIES = {"openai", "databricks", "pinterest", "deepmind", "google deepmind"}
LEVER_SKILL_PATH = os.path.join(WORKSPACE, "skills", "apply-lever", "SKILL.md")
LEVER_ENABLE_ENV = "OPENCLAW_ENABLE_LEVER"


def check_lock(ats: str) -> dict:
    script = os.path.join(SCRIPTS_DIR, "subagent-lock.py")
    try:
        proc = subprocess.run(
            ["python3", script, "check", ats],
            capture_output=True,
            text=True,
            timeout=5,
        )
        out = (proc.stdout or "").strip()
        locked = out.startswith("LOCKED")
        return {"locked": locked, "raw": out or "UNKNOWN"}
    except Exception as e:
        return {"locked": False, "raw": f"ERROR {e}"}


def adaptive_settings(total_actionable: int) -> dict:
    if total_actionable <= 100:
        return {
            "preflight_top": 8,
            "apply_cap": {"ashby": 3, "greenhouse": 3, "lever": 2},
            "backlog_tier": "normal",
        }
    if total_actionable <= 250:
        return {
            "preflight_top": 10,
            "apply_cap": {"ashby": 4, "greenhouse": 4, "lever": 3},
            "backlog_tier": "high",
        }
    return {
        "preflight_top": 12,
        "apply_cap": {"ashby": 5, "greenhouse": 5, "lever": 4},
        "backlog_tier": "critical",
    }


def lever_automation_enabled() -> bool:
    env = (os.environ.get(LEVER_ENABLE_ENV) or "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    if env in {"0", "false", "no", "off"}:
        return False
    try:
        with open(LEVER_SKILL_PATH, "r", encoding="utf-8", errors="ignore") as f:
            header = f.read(1200)
        return "## STATUS: DISABLED" not in header
    except OSError:
        # Fail safe: if we cannot read policy, do not disable lever implicitly.
        return True


def build_dispatch() -> dict:
    sections, stats = read_queue_sections(QUEUE_PATH, LOCK_PATH, no_auto_companies=NO_AUTO_COMPANIES)
    pending = sections.get("pending", [])
    actionable = filter_jobs(pending, actionable_only=True, ats_filter=None)
    lever_enabled = lever_automation_enabled()
    by_ats = {
        ats: sorted(
            filter_jobs(pending, actionable_only=True, ats_filter=ats),
            key=lambda j: j.get("score", 0),
            reverse=True,
        )
        for ats in ATS_TYPES
    }

    ats_status = {}
    ready = []
    for ats in ATS_TYPES:
        lock_info = check_lock(ats)
        jobs = by_ats[ats]
        if ats == "lever" and not lever_enabled:
            jobs = []
            lock_info = {"locked": True, "raw": "LOCKED disabled-by-policy"}
        top_job = jobs[0] if jobs else None
        if lock_info["locked"]:
            status = "SKIPPED_LOCKED"
        elif not jobs:
            status = "SKIPPED_EMPTY"
        else:
            status = "READY"
            ready.append(ats)
        ats_status[ats] = {
            "status": status,
            "lock": lock_info["raw"],
            "actionable_count": len(jobs),
            "top_score": top_job.get("score") if top_job else None,
            "top_url": top_job.get("url") if top_job else "",
            "top_company": top_job.get("company") if top_job else "",
            "top_title": top_job.get("title") if top_job else "",
        }

    settings = adaptive_settings(len(actionable))
    now = datetime.now(timezone.utc)
    return {
        "timestamp_ms": int(now.timestamp() * 1000),
        "timestamp_iso": now.isoformat(),
        "queue_stats": {
            "pending": stats.get("pending", len(pending)),
            "in_progress": stats.get("in_progress", len(sections.get("in_progress", []))),
            "actionable_total": len(actionable),
        },
        "settings": settings,
        "ats": ats_status,
        "ready_ats": ready,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic orchestrator dispatch snapshot")
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    args = parser.parse_args()

    start = time.time()
    dispatch = build_dispatch()
    dispatch["elapsed_ms"] = int((time.time() - start) * 1000)

    if args.json:
        print(json.dumps(dispatch, ensure_ascii=True, indent=2))
        return 0

    q = dispatch["queue_stats"]
    s = dispatch["settings"]
    print(
        f"DISPATCH: pending={q['pending']} actionable={q['actionable_total']} "
        f"tier={s['backlog_tier']} preflight_top={s['preflight_top']}"
    )
    for ats in ATS_TYPES:
        a = dispatch["ats"][ats]
        print(
            f"{ats}: {a['status']} | lock={a['lock']} | actionable={a['actionable_count']} | "
            f"top={a['top_company']} — {a['top_title']}"
        )
    if not dispatch["ready_ats"]:
        print("READY: none")
    else:
        print(f"READY: {', '.join(dispatch['ready_ats'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
