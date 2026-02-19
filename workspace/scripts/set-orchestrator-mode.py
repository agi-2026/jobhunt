#!/usr/bin/env python3
"""
Toggle Application Orchestrator scope between:
- full: ashby + greenhouse + lever
- greenhouse: greenhouse only

Updates canonical cron config at jobhunt/cron/jobs.json.
Run sync-cron-config.py afterward to apply runtime config.
"""
import argparse
import json
import os
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
CRON_PATH = os.path.join(REPO_ROOT, "cron", "jobs.json")
RUNTIME_CRON_PATH = os.path.expanduser("~/.openclaw/cron/jobs.json")
ORCHESTRATOR_NAME = "Application Orchestrator"


FULL_MESSAGE = """You are the APPLICATION ORCHESTRATOR.

Run this flow only:
1) `exec: python3 scripts/orchestrator-dispatch.py --json`
2) `exec: python3 scripts/batch-preflight.py --all --remove --top 12 --timeout 90`
3) For each ATS in [ashby, greenhouse, lever], if ready, spawn ONE subagent in parallel via sessions_spawn.

Spawn requirements:
- unique label: apply-<ats>-<unix_ms>-<rand4>
- retry once on "label already in use"
- runTimeoutSeconds: ashby=900, greenhouse=900, lever=600
- thinking: low
- cleanup: keep

Subagent task contract (all ATS):
- lock first, unlock always (`scripts/subagent-lock.py`)
- use ATS SKILL.md exactly
- STRICT browser mode: NEVER action=open, ALWAYS navigate, NEVER pass targetId
- use queue-summary output directly, process exactly TOP 1 job this run
- if blocked by captcha/verification, keep pending and continue
- MANDATORY ESSAY POLICY: if required essay/free-text answer is detected, DO NOT use any LLM answer generation; run `scripts/defer-manual-apply.py` and continue to next URL

After spawning, write guardrail log once:
`exec: python3 scripts/log-orchestrator-cycle.py --ashby <...> --greenhouse <...> --lever <...> --runid-ashby "<...>" --runid-greenhouse "<...>" --runid-lever "<...>"`

Return compact ATS lines only (SPAWNED/SKIPPED/ERROR)."""


GREENHOUSE_ONLY_MESSAGE = """You are the APPLICATION ORCHESTRATOR (GREENHOUSE-ONLY MODE).

Run this flow only:
1) `exec: python3 scripts/orchestrator-dispatch.py --json`
2) `exec: python3 scripts/batch-preflight.py --all --remove --top 12 --timeout 90`
3) Only process ATS=greenhouse in this mode. If greenhouse is ready, spawn ONE greenhouse subagent.

Spawn requirements:
- unique label: apply-greenhouse-<unix_ms>-<rand4>
- retry once on "label already in use"
- runTimeoutSeconds: greenhouse=900
- thinking: low
- cleanup: keep

Subagent task contract (greenhouse):
- lock first, unlock always (`scripts/subagent-lock.py`)
- use skills/apply-greenhouse/SKILL.md exactly
- STRICT browser mode: NEVER action=open, ALWAYS navigate, NEVER pass targetId
- use queue-summary output directly, process exactly TOP 1 job this run
- if blocked by captcha/verification, keep pending and continue
- MANDATORY ESSAY POLICY: if required essay/free-text answer is detected, DO NOT use any LLM answer generation; run `scripts/defer-manual-apply.py` and continue to next URL

After spawning, write guardrail log once:
`exec: python3 scripts/log-orchestrator-cycle.py --ashby SKIPPED_MODE --greenhouse <SPAWNED|SKIPPED_LOCKED|SKIPPED_EMPTY|ERROR|UNKNOWN> --lever SKIPPED_MODE --runid-ashby "" --runid-greenhouse "<...>" --runid-lever ""`

Return compact ATS lines only (SPAWNED/SKIPPED/ERROR)."""


def set_mode_on_file(path: str, mode: str, solo: bool) -> None:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    target = None
    for job in data.get("jobs", []):
        if job.get("name") == ORCHESTRATOR_NAME:
            target = job
            break

    if target is None:
        raise RuntimeError(f"Application Orchestrator job not found in {path}")

    payload = target.setdefault("payload", {})
    payload["message"] = GREENHOUSE_ONLY_MESSAGE if mode == "greenhouse" else FULL_MESSAGE

    # Optional: suppress other cron load while testing low-quota apply flow.
    if solo:
        for job in data.get("jobs", []):
            name = job.get("name", "")
            if name == "Search Agent":
                job["enabled"] = False
            elif name == "Health + Analysis Monitor":
                job["enabled"] = False
            elif name == ORCHESTRATOR_NAME:
                job["enabled"] = True
    else:
        # Restore default enabled state for known jobs.
        for job in data.get("jobs", []):
            name = job.get("name", "")
            if name in ("Search Agent", "Health + Analysis Monitor", ORCHESTRATOR_NAME):
                job["enabled"] = True

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set Application Orchestrator mode.")
    parser.add_argument("--mode", choices=["full", "greenhouse"], required=True)
    parser.add_argument("--canonical-only", action="store_true", help="Only update repo cron/jobs.json")
    parser.add_argument("--solo", action="store_true", help="Disable Search/Health jobs during testing")
    args = parser.parse_args()

    try:
        set_mode_on_file(CRON_PATH, args.mode, args.solo)
        print(f"UPDATED: {CRON_PATH}")
        if not args.canonical_only and os.path.exists(RUNTIME_CRON_PATH):
            set_mode_on_file(RUNTIME_CRON_PATH, args.mode, args.solo)
            print(f"UPDATED: {RUNTIME_CRON_PATH}")
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    print(f"OK: set orchestrator mode -> {args.mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
