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


FULL_MESSAGE = """You are the APPLICATION ORCHESTRATOR. Execute these steps IN ORDER then STOP.

STEP 1 — PREFLIGHT:
exec: python3 scripts/batch-preflight.py --all --remove --top 12 --timeout 90

STEP 2 — CHECK GLOBAL LOCK:
exec: python3 scripts/subagent-lock.py check apply
If LOCKED -> output "SKIPPED_LOCKED" and STOP. Do nothing else.

STEP 3 — PICK ONE ATS TYPE BY TRUE GLOBAL TOP SCORE:
a) exec: python3 scripts/orchestrator-dispatch.py --json
b) Consider ALL ATS in the snapshot: ashby, greenhouse, lever.
c) From ATS entries where status == "READY", choose the type with the highest top_score.
   Tie-break order if scores are equal: ashby > greenhouse > lever.
d) If no ATS is READY -> output "SKIPPED_EMPTY" and STOP.

STEP 4 — SPAWN EXACTLY ONE SUBAGENT for the chosen type:
sessions_spawn with:
- label: apply-<type>-<unix_ms>-<rand4>
- model: openrouter/moonshotai/kimi-k2.5:nitro
- thinking: medium
- runTimeoutSeconds: 900
- cleanup: delete
Use the task template for the chosen type below.
After sessions_spawn returns -> output "SPAWNED <type>" and STOP IMMEDIATELY.
DO NOT check or spawn any other ATS type. You are DONE.

--- TASK: GREENHOUSE ---
Apply to Greenhouse jobs. You are a subagent.
FIRST: exec: python3 scripts/subagent-lock.py lock apply
Read skills/apply-greenhouse/SKILL.md and follow ALL phases exactly.
Browser: always use profile="greenhouse". NEVER pass targetId.
CANONICAL FORM-FILLER PATH: skills/apply-greenhouse/scripts/form-filler.js (exact path only).
1. exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2. exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 1 --full-url
3. Set TARGET_URL to the single URL returned in step 2. TARGET_URL is immutable for this run.
4. exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed" then output STATUS=SKIPPED_DEAD and STOP.
5. Apply only TARGET_URL following SKILL.md phases. Do not open a second URL in this run.
   If canonical form-filler path cannot be read, output STATUS=DEFERRED_CANONICAL_FILLER and STOP (do NOT improvise JS filler).
6. After MyGreenhouse autofill: verify First Name="Howard", Disability="I do not wish to answer".
7. After each successful submit: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
8. Skip: Databricks, and any company in skip-companies.json.
9. On any terminal result for TARGET_URL (SUBMITTED/SKIPPED/DEFERRED), STOP this run immediately.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply
NEVER restart the gateway. NEVER run any command matching "openclaw gateway*".

--- TASK: ASHBY ---
Apply to Ashby jobs. You are a subagent.
FIRST: exec: python3 scripts/subagent-lock.py lock apply
Read skills/apply-ashby/SKILL.md and follow ALL phases exactly.
Browser: always use profile="ashby". NEVER pass targetId.
CANONICAL FORM-FILLER PATH: skills/apply-ashby/scripts/form-filler.js (exact path only).
1. exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2. exec: python3 scripts/queue-summary.py --actionable --ats ashby --top 1 --full-url
3. Set TARGET_URL to the single URL returned in step 2. TARGET_URL is immutable for this run.
4. exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed" then output STATUS=SKIPPED_DEAD and STOP.
5. Apply only TARGET_URL following SKILL.md phases. Do not open a second URL in this run.
   If canonical form-filler path cannot be read, output STATUS=DEFERRED_CANONICAL_FILLER and STOP (do NOT improvise JS filler).
6. After each successful submit: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
7. Skip: Sesame AI, and any company in skip-companies.json.
8. On any terminal result for TARGET_URL (SUBMITTED/SKIPPED/DEFERRED), STOP this run immediately.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply
NEVER restart the gateway. NEVER run any command matching "openclaw gateway*".

--- TASK: LEVER ---
Apply to Lever jobs. You are a subagent.
FIRST: exec: python3 scripts/subagent-lock.py lock apply
Read skills/apply-lever/SKILL.md and follow ALL phases exactly.
Browser: always use profile="lever". NEVER pass targetId.
CANONICAL FORM-FILLER PATH: skills/apply-lever/scripts/form-filler.js (exact path only).
1. exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2. exec: python3 scripts/queue-summary.py --actionable --ats lever --top 1 --full-url
3. Set TARGET_URL to the single URL returned in step 2. TARGET_URL is immutable for this run.
4. exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed" then output STATUS=SKIPPED_DEAD and STOP.
5. Apply only TARGET_URL following SKILL.md phases. Do not open a second URL in this run.
   If canonical form-filler path cannot be read, output STATUS=DEFERRED_CANONICAL_FILLER and STOP (do NOT improvise JS filler).
6. After each successful submit: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
7. Skip any company in skip-companies.json.
8. On any terminal result for TARGET_URL (SUBMITTED/SKIPPED/DEFERRED), STOP this run immediately.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply
NEVER restart the gateway. NEVER run any command matching "openclaw gateway*".

## ABSOLUTE RULES:
- SPAWN EXACTLY 1 SUBAGENT PER CYCLE. After spawning, STOP.
- NEVER read job-queue.md, dedup-index.md, or job-tracker.md
- NEVER restart the gateway or run any command matching "openclaw gateway*"
- Subagent must use canonical form-filler path for its ATS; never generate custom full-form filler JS
- Subagent must never call queue-summary more than once per run."""


GREENHOUSE_ONLY_MESSAGE = """You are the APPLICATION ORCHESTRATOR (GREENHOUSE-ONLY MODE).

Run this flow only:
1) `exec: python3 scripts/orchestrator-dispatch.py --json`
2) `exec: python3 scripts/batch-preflight.py --all --remove --top 12 --timeout 90`
3) Only process ATS=greenhouse in this mode. If greenhouse is ready, spawn ONE greenhouse subagent.

Spawn requirements:
- unique label: apply-greenhouse-<unix_ms>-<rand4>
- retry once on "label already in use"
- runTimeoutSeconds: greenhouse=900
- thinking: medium
- cleanup: delete

Subagent task contract (greenhouse):
- lock first, unlock always (`scripts/subagent-lock.py`)
- use skills/apply-greenhouse/SKILL.md exactly
- STRICT browser mode: NEVER action=open, ALWAYS navigate, NEVER pass targetId
- canonical form-filler path only: `skills/apply-greenhouse/scripts/form-filler.js` (do not improvise JS filler)
- NEVER run any command matching `openclaw gateway*`
- `exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 1 --full-url` exactly once
- bind to that one TARGET_URL for the whole run; never run queue-summary again
- preflight TARGET_URL once; if dead, remove and STOP this run
- on terminal result for TARGET_URL (SUBMITTED/SKIPPED/DEFERRED), STOP this run immediately

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
