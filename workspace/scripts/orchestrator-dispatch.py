#!/usr/bin/env python3
"""Deterministic dispatcher for Application Orchestrator.

Builds a single readiness snapshot for all slots in one pass:
- lock status (per slot — ashby and ashby2 have independent locks)
- actionable queue depth
- top URL
- READY vs SKIPPED_* reason

Slots:
  ashby       → ats=ashby,      profile=ashby,      model=haiku
  ashby2      → ats=ashby,      profile=ashby-2,    model=haiku   (parallel Ashby session)
  greenhouse  → ats=greenhouse,  profile=greenhouse,  model=sonnet  (complex forms need Sonnet)
  lever       → ats=lever,       profile=lever,       model=haiku

ashby + ashby2 share the same Ashby queue. claim-job.py prevents double-apply.
ashby2 only spawns when ashby also has jobs (need ≥2 Ashby jobs for both to be useful).
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

MODEL_HAIKU = "anthropic/claude-haiku-4-5-20251001"
MODEL_SONNET = "anthropic/claude-sonnet-4-6"

# Ordered slot definitions — each slot has independent lock + browser profile
# ashby2 disabled — caused collision issues (both agents opening same job, one frozen)
ATS_SLOTS = [
    {"slot": "ashby",      "ats": "ashby",      "model": MODEL_HAIKU},
    {"slot": "greenhouse", "ats": "greenhouse",  "model": MODEL_SONNET},
    {"slot": "lever",      "ats": "lever",       "model": MODEL_HAIKU},
]

NO_AUTO_COMPANIES = {"openai", "databricks", "pinterest", "deepmind", "google deepmind"}
LEVER_SKILL_PATH = os.path.join(WORKSPACE, "skills", "apply-lever", "SKILL.md")
LEVER_ENABLE_ENV = "OPENCLAW_ENABLE_LEVER"


def check_lock(slot: str) -> dict:
    script = os.path.join(SCRIPTS_DIR, "subagent-lock.py")
    try:
        proc = subprocess.run(
            ["python3", script, "check", slot],
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
            "apply_cap": {"ashby": 3, "ashby2": 3, "greenhouse": 3, "lever": 3},
            "backlog_tier": "normal",
        }
    if total_actionable <= 250:
        return {
            "apply_cap": {"ashby": 4, "ashby2": 4, "greenhouse": 3, "lever": 3},
            "backlog_tier": "high",
        }
    return {
        "apply_cap": {"ashby": 5, "ashby2": 5, "greenhouse": 3, "lever": 4},
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
        return True


def build_dispatch() -> dict:
    sections, stats = read_queue_sections(QUEUE_PATH, LOCK_PATH, no_auto_companies=NO_AUTO_COMPANIES)
    pending = sections.get("pending", [])
    actionable = filter_jobs(pending, actionable_only=True, ats_filter=None)
    lever_enabled = lever_automation_enabled()

    # Build per-ATS job lists (ashby2 shares ashby's job list)
    unique_ats = list(dict.fromkeys(s["ats"] for s in ATS_SLOTS))
    by_ats = {
        ats: sorted(
            filter_jobs(pending, actionable_only=True, ats_filter=ats),
            key=lambda j: j.get("score", 0),
            reverse=True,
        )
        for ats in unique_ats
    }

    slot_status = {}
    ready_slots = []

    for slot_def in ATS_SLOTS:
        slot = slot_def["slot"]
        ats = slot_def["ats"]
        model = slot_def["model"]
        sibling = slot_def.get("requires_sibling")

        lock_info = check_lock(slot)
        jobs = list(by_ats.get(ats, []))

        # Disable lever if policy says so
        if ats == "lever" and not lever_enabled:
            jobs = []
            lock_info = {"locked": True, "raw": "LOCKED disabled-by-policy"}

        # ashby2 only fires if there are enough jobs for both sessions
        if sibling and len(jobs) < ASHBY2_MIN_JOBS:
            status = "SKIPPED_INSUFFICIENT_JOBS"
        elif lock_info["locked"]:
            status = "SKIPPED_LOCKED"
        elif not jobs:
            status = "SKIPPED_EMPTY"
        else:
            status = "READY"
            ready_slots.append({"slot": slot, "ats": ats, "model": model})

        top_job = jobs[0] if jobs else None
        slot_status[slot] = {
            "status": status,
            "lock": lock_info["raw"],
            "actionable_count": len(jobs),
            "top_score": top_job.get("score") if top_job else None,
            "top_url": top_job.get("url") if top_job else "",
            "top_company": top_job.get("company") if top_job else "",
            "top_title": top_job.get("title") if top_job else "",
            "model": model,
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
        "slots": slot_status,
        "ready_slots": ready_slots,
        # Keep legacy ready_ats for any tooling that reads it
        "ready_ats": list(dict.fromkeys(s["ats"] for s in ready_slots)),
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
        f"tier={s['backlog_tier']}"
    )
    for slot, info in dispatch["slots"].items():
        print(
            f"{slot}: {info['status']} | lock={info['lock']} | actionable={info['actionable_count']} | "
            f"top={info['top_company']} — {info['top_title']}"
        )
    if not dispatch["ready_slots"]:
        print("READY: none")
    else:
        names = [s["slot"] for s in dispatch["ready_slots"]]
        print(f"READY: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
