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


FULL_MESSAGE = """You are the APPLICATION ORCHESTRATOR. Be deterministic and concise.

METADATA-FIRST CONTEXT (CRITICAL)
1) exec: python3 scripts/context-manifest.py build
2) exec: python3 scripts/context-manifest.py list --profile orchestrator --limit 20
Only read file contents if needed, via:
  exec: python3 scripts/context-manifest.py read <entry_id> [--section "<heading>"] [--max-lines 180]
Do NOT load large files directly by path unless manifest lookup fails.

STEP 1 — CHECK GLOBAL LOCK FIRST:
exec: python3 scripts/subagent-lock.py check apply
If LOCKED -> output "SKIPPED_LOCKED" and STOP.

STEP 2 — PREFLIGHT:
exec: python3 scripts/batch-preflight.py --all --remove --top 8 --timeout 90

STEP 3 — DISPATCH:
exec: python3 scripts/orchestrator-dispatch.py --json
Pick exactly ONE ATS from READY entries (ashby, greenhouse, lever):
- highest top_score wins
- tie-break: ashby > greenhouse > lever
If none READY -> output "SKIPPED_EMPTY" and STOP.

STEP 4 — SPAWN EXACTLY ONE SUBAGENT:
sessions_spawn with:
- label: apply-<type>-<unix_ms>-<rand4>
- model: openrouter/stepfun/step-3.5-flash
- thinking: low
- runTimeoutSeconds: 360
- cleanup: keep
- agentId: main (or omit agentId; NEVER use apply-* ids)
If spawn fails with forbidden/disallowed agentId, retry once with agentId=main.
Use ATS task template below.
CRITICAL TASK COPY RULE:
- The `task` argument MUST be copied VERBATIM from the selected ATS TASK TEMPLATE block below.
- Do NOT summarize/paraphrase. Forbidden examples: "follow template", "run apply sequence", "acquire lock and apply".
- If you cannot provide the full verbatim template, output exactly: "ERROR_TASK_NOT_VERBATIM" and STOP.
- The task must include the queue-summary line and the FINALLY unlock line from the template.
After accepted spawn, output exactly: "SPAWNED <type>" and STOP immediately.

--- TASK TEMPLATE: GREENHOUSE ---
Apply one Greenhouse job only.
FIRST:
- exec: python3 scripts/subagent-lock.py lock apply
- exec: python3 scripts/context-manifest.py build
- exec: python3 scripts/context-manifest.py list --profile apply-greenhouse --limit 20
- exec: python3 scripts/tool-menu.py --profile greenhouse --json
- Tool policy: use only exec + browser + process in apply runs. Do NOT use read/write/edit tools.
Then:
1) exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2) exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 1 --full-url
3) Set immutable TARGET_URL from step 2.
4) exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed"; output STATUS=SKIPPED_DEAD; STOP.
5) Keep context minimal (no large runbook reads):
   - Do NOT read greenhouse_skill sections in normal flow; follow this task template directly.
   - Read greenhouse_form_filler only immediately before first browser evaluate via:
     exec: python3 scripts/context-manifest.py read greenhouse_form_filler --max-lines 360 --raw
   - Do NOT use `python -c`, `cat`, `sed`, or any direct file read for form-filler.js; only the context-manifest command above is allowed.
   - Read greenhouse_custom_answers / greenhouse_verify_code only if those branches are actually needed.
   - After form-filler evaluate, continue directly to combobox/upload/submit; avoid extra large reads.
   - For resume upload, use browser `action=upload` with top-level `paths` and `element` (or `ref`/`inputRef`) from fileUploadSelectors (do NOT click "Attach" first).
6) Browser schema is strict:
   - JS evaluate MUST use browser `action=act` with `request.kind=evaluate`.
   - For multiline JS (form-filler/custom helpers), put code in `request.fn` (full function text from JS source).
   - `request.fn` must be COMPLETE source (no placeholders like `...`, `[...]`, or `(truncated for brevity)`).
   - For ALL `action=act` calls, kind/args must be inside `request={...}` (never top-level `kind/ref/text/paths`).
   - `request` MUST be an object, never a JSON string (invalid: `request: "{...}"`).
   - Canonical evaluate call shape: `{"action":"act","profile":"<ats-profile>","request":{"kind":"evaluate","fn":"<full_js_source>"}}`.
   - If browser validation says `request: must be object` or shows `"request": "{...}"`, output STATUS=DEFERRED_TOOL_SCHEMA and STOP immediately (do not retry the same call).
   - File upload is NOT an `act` request: use browser `action=upload` with top-level `paths` + (`element` or `ref` or `inputRef`).
   - `action=evaluate` is invalid.
   - Never pass targetId.
   - If the same browser schema/validation error repeats twice, output STATUS=DEFERRED_TOOL_SCHEMA and STOP.
   - If browser tool returns timeout/unreachable/control-service error: output STATUS=DEFERRED_BROWSER_TIMEOUT and STOP immediately.
7) On confirmed submit only: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
8) Terminal outcomes allowed: SUBMITTED / SKIPPED / DEFERRED. After one terminal outcome, STOP run.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply

--- TASK TEMPLATE: ASHBY ---
Apply one Ashby job only.
FIRST:
- exec: python3 scripts/subagent-lock.py lock apply
- exec: python3 scripts/context-manifest.py build
- exec: python3 scripts/context-manifest.py list --profile apply-ashby --limit 20
- exec: python3 scripts/tool-menu.py --profile ashby --json
- Tool policy: use only exec + browser + process in apply runs. Do NOT use read/write/edit tools.
Then:
1) exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2) exec: python3 scripts/queue-summary.py --actionable --ats ashby --top 1 --full-url
3) Set immutable TARGET_URL from step 2.
4) exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed"; output STATUS=SKIPPED_DEAD; STOP.
5) Use lazy metadata reads via manifest (do NOT preload large JS):
   - exec: python3 scripts/context-manifest.py read ashby_skill --section "Application Flow" --max-lines 180
   - exec: python3 scripts/context-manifest.py read ashby_skill --section "Browser Profile" --max-lines 80
   - Read ashby_form_filler full only immediately before first browser evaluate via:
     exec: python3 scripts/context-manifest.py read ashby_form_filler --max-lines 1400 --raw
   - Do NOT use `python -c`, `cat`, `sed`, or any direct file read for form-filler.js; only the context-manifest command above is allowed.
   - Read ashby_custom_answers only if customQuestions[] is non-empty.
6) Browser schema is strict:
   - JS evaluate MUST use browser `action=act` with `request.kind=evaluate`.
   - For multiline JS (form-filler/custom helpers), put code in `request.fn` (full function text from JS source).
   - `request.fn` must be COMPLETE source (no placeholders like `...`, `[...]`, or `(truncated for brevity)`).
   - For ALL `action=act` calls, kind/args must be inside `request={...}` (never top-level `kind/ref/text/paths`).
   - `request` MUST be an object, never a JSON string (invalid: `request: "{...}"`).
   - Canonical evaluate call shape: `{"action":"act","profile":"<ats-profile>","request":{"kind":"evaluate","fn":"<full_js_source>"}}`.
   - If browser validation says `request: must be object` or shows `"request": "{...}"`, output STATUS=DEFERRED_TOOL_SCHEMA and STOP immediately (do not retry the same call).
   - File upload is NOT an `act` request: use browser `action=upload` with top-level `paths` + (`element` or `ref` or `inputRef`).
   - `action=evaluate` is invalid.
   - Never pass targetId.
   - If the same browser schema/validation error repeats twice, output STATUS=DEFERRED_TOOL_SCHEMA and STOP.
   - If browser tool returns timeout/unreachable/control-service error: output STATUS=DEFERRED_BROWSER_TIMEOUT and STOP immediately.
7) On confirmed submit only: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
8) Terminal outcomes allowed: SUBMITTED / SKIPPED / DEFERRED. After one terminal outcome, STOP run.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply

--- TASK TEMPLATE: LEVER ---
Apply one Lever job only.
FIRST:
- exec: python3 scripts/subagent-lock.py lock apply
- exec: python3 scripts/context-manifest.py build
- exec: python3 scripts/context-manifest.py list --profile apply-lever --limit 20
- exec: python3 scripts/tool-menu.py --profile lever --json
- Tool policy: use only exec + browser + process in apply runs. Do NOT use read/write/edit tools.
Then:
1) exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2) exec: python3 scripts/queue-summary.py --actionable --ats lever --top 1 --full-url
3) Set immutable TARGET_URL from step 2.
4) exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed"; output STATUS=SKIPPED_DEAD; STOP.
5) Keep context minimal (no large runbook reads):
   - Do NOT read lever_skill sections in normal flow; follow this task template directly.
   - Read lever_form_filler only immediately before first browser evaluate via:
     exec: python3 scripts/context-manifest.py read lever_form_filler --max-lines 360 --raw
   - Do NOT use `python -c`, `cat`, `sed`, or any direct file read for form-filler.js; only the context-manifest command above is allowed.
   - Read lever_custom_answers only if customQuestions[] is non-empty.
   - Read lever_detect_hcaptcha only after submit if captcha branch is detected.
6) Browser schema is strict:
   - JS evaluate MUST use browser `action=act` with `request.kind=evaluate`.
   - For multiline JS (form-filler/custom helpers), put code in `request.fn` (full function text from JS source).
   - `request.fn` must be COMPLETE source (no placeholders like `...`, `[...]`, or `(truncated for brevity)`).
   - For ALL `action=act` calls, kind/args must be inside `request={...}` (never top-level `kind/ref/text/paths`).
   - `request` MUST be an object, never a JSON string (invalid: `request: "{...}"`).
   - Canonical evaluate call shape: `{"action":"act","profile":"<ats-profile>","request":{"kind":"evaluate","fn":"<full_js_source>"}}`.
   - If browser validation says `request: must be object` or shows `"request": "{...}"`, output STATUS=DEFERRED_TOOL_SCHEMA and STOP immediately (do not retry the same call).
   - File upload is NOT an `act` request: use browser `action=upload` with top-level `paths` + (`element` or `ref` or `inputRef`).
   - `action=evaluate` is invalid.
   - Never pass targetId.
   - If the same browser schema/validation error repeats twice, output STATUS=DEFERRED_TOOL_SCHEMA and STOP.
   - If browser tool returns timeout/unreachable/control-service error: output STATUS=DEFERRED_BROWSER_TIMEOUT and STOP immediately.
7) On confirmed submit only: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
8) Terminal outcomes allowed: SUBMITTED / SKIPPED / DEFERRED. After one terminal outcome, STOP run.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply

## ABSOLUTE RULES
- SPAWN EXACTLY 1 SUBAGENT PER CYCLE, then STOP.
- NEVER read job-queue.md, dedup-index.md, or job-tracker.md into context.
- NEVER restart the gateway or run any command matching "openclaw gateway*".
- Subagent must not call queue-summary more than once per run.
- Subagent must use only exec + browser + process during apply runs (no read/write/edit tools).
- Do not execute .js files with python/node; for JS helpers, read content then pass to browser `action=act` with `request.kind=evaluate`.
- Never read form-filler.js via `python -c`, `cat`, `sed`, `awk`, or `head`; only `python3 scripts/context-manifest.py read <*_form_filler> ... --raw` is allowed.
- Subagent must NEVER run `openclaw` commands of any kind during apply runs (especially `openclaw gateway *`).
- If scripts/log-orchestrator-cycle.py is used, only supported flags are:
  --ashby <SPAWNED|SKIPPED_LOCKED|SKIPPED_EMPTY|SKIPPED_NOT_CHOSEN|ERROR|UNKNOWN>
  --greenhouse <SPAWNED|SKIPPED_LOCKED|SKIPPED_EMPTY|SKIPPED_NOT_CHOSEN|ERROR|UNKNOWN>
  --lever <SPAWNED|SKIPPED_LOCKED|SKIPPED_EMPTY|SKIPPED_NOT_CHOSEN|ERROR|UNKNOWN>
  --runid-ashby/--runid-greenhouse/--runid-lever/--note."""


GREENHOUSE_ONLY_MESSAGE = """You are the APPLICATION ORCHESTRATOR (GREENHOUSE-ONLY MODE).

METADATA-FIRST CONTEXT:
1) exec: python3 scripts/context-manifest.py build
2) exec: python3 scripts/context-manifest.py list --profile orchestrator --limit 20

STEP 1 — CHECK GLOBAL LOCK FIRST:
exec: python3 scripts/subagent-lock.py check apply
If LOCKED -> output "SKIPPED_LOCKED" and STOP.

STEP 2 — PREFLIGHT:
exec: python3 scripts/batch-preflight.py --all --remove --top 12 --timeout 90

STEP 3 — DISPATCH:
exec: python3 scripts/orchestrator-dispatch.py --json
Only process ATS=greenhouse in this mode.
If greenhouse not READY -> output "SKIPPED_EMPTY" and STOP.

STEP 4 — SPAWN EXACTLY ONE GREENHOUSE SUBAGENT:
sessions_spawn with:
- label: apply-greenhouse-<unix_ms>-<rand4>
- model: openrouter/stepfun/step-3.5-flash
- thinking: low
- runTimeoutSeconds: 360
- cleanup: keep
- agentId: main (or omit agentId; NEVER use apply-* ids)
If spawn fails with forbidden/disallowed agentId, retry once with agentId=main.
CRITICAL TASK COPY RULE:
- The `task` argument MUST be copied VERBATIM from the GREENHOUSE TASK TEMPLATE block below.
- Do NOT summarize/paraphrase. Forbidden examples: "follow template", "run apply sequence", "acquire lock and apply".
- If you cannot provide the full verbatim template, output exactly: "ERROR_TASK_NOT_VERBATIM" and STOP.
- The task must include all of these exact lines:
  - `Apply one Greenhouse job only.`
  - `2) exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 1 --full-url`
  - `FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply`
After accepted spawn, output exactly: "SPAWNED greenhouse" and STOP immediately.

--- TASK TEMPLATE: GREENHOUSE ---
Apply one Greenhouse job only.
FIRST:
- exec: python3 scripts/subagent-lock.py lock apply
- exec: python3 scripts/context-manifest.py build
- exec: python3 scripts/context-manifest.py list --profile apply-greenhouse --limit 20
- exec: python3 scripts/tool-menu.py --profile greenhouse --json
- Tool policy: use only exec + browser + process in apply runs. Do NOT use read/write/edit tools.
Then:
1) exec: cp ~/.openclaw/workspace/resume/Resume_Howard.pdf /tmp/openclaw/uploads/
2) exec: python3 scripts/queue-summary.py --actionable --ats greenhouse --top 1 --full-url
3) Set immutable TARGET_URL from step 2.
4) exec: python3 scripts/preflight-check.py "<TARGET_URL>"
   If DEAD: exec: python3 scripts/remove-from-queue.py "<TARGET_URL>" "DEAD: preflight failed"; output STATUS=SKIPPED_DEAD; STOP.
5) Keep context minimal (no large runbook reads):
   - Do NOT read greenhouse_skill sections in normal flow; follow this task template directly.
   - Read greenhouse_form_filler only immediately before first browser evaluate via:
     exec: python3 scripts/context-manifest.py read greenhouse_form_filler --max-lines 360 --raw
   - Do NOT use `python -c`, `cat`, `sed`, or any direct file read for form-filler.js; only the context-manifest command above is allowed.
   - Read greenhouse_custom_answers / greenhouse_verify_code only if those branches are actually needed.
   - After form-filler evaluate, continue directly to combobox/upload/submit; avoid extra large reads.
   - For resume upload, use browser `action=upload` with top-level `paths` and `element` (or `ref`/`inputRef`) from fileUploadSelectors (do NOT click "Attach" first).
6) Browser schema is strict:
   - JS evaluate MUST use browser `action=act` with `request.kind=evaluate`.
   - For multiline JS (form-filler/custom helpers), put code in `request.fn` (full function text from JS source).
   - `request.fn` must be COMPLETE source (no placeholders like `...`, `[...]`, or `(truncated for brevity)`).
   - For ALL `action=act` calls, kind/args must be inside `request={...}` (never top-level `kind/ref/text/paths`).
   - `request` MUST be an object, never a JSON string (invalid: `request: "{...}"`).
   - Canonical evaluate call shape: `{"action":"act","profile":"<ats-profile>","request":{"kind":"evaluate","fn":"<full_js_source>"}}`.
   - If browser validation says `request: must be object` or shows `"request": "{...}"`, output STATUS=DEFERRED_TOOL_SCHEMA and STOP immediately (do not retry the same call).
   - File upload is NOT an `act` request: use browser `action=upload` with top-level `paths` + (`element` or `ref` or `inputRef`).
   - `action=evaluate` is invalid.
   - Never pass targetId.
   - If the same browser schema/validation error repeats twice, output STATUS=DEFERRED_TOOL_SCHEMA and STOP.
   - If browser tool returns timeout/unreachable/control-service error: output STATUS=DEFERRED_BROWSER_TIMEOUT and STOP immediately.
7) On confirmed submit only: exec: python3 scripts/mark-applied.py "<TARGET_URL>" "<Company>" "<Title>"
8) Terminal outcomes allowed: SUBMITTED / SKIPPED / DEFERRED. After one terminal outcome, STOP run.
FINALLY (even on error): exec: python3 scripts/subagent-lock.py unlock apply

After spawning, write guardrail log once:
exec: python3 scripts/log-orchestrator-cycle.py --ashby SKIPPED_NOT_CHOSEN --greenhouse SPAWNED --lever SKIPPED_NOT_CHOSEN --runid-greenhouse "<runid>"

ABSOLUTE RULES:
- SPAWN EXACTLY 1 GREENHOUSE SUBAGENT PER CYCLE, then STOP.
- Subagent must use only exec + browser + process during apply runs.
- Subagent must not call queue-summary more than once per run.
- Never read form-filler.js via `python -c`, `cat`, `sed`, `awk`, or `head`; only `python3 scripts/context-manifest.py read <*_form_filler> ... --raw` is allowed.
- Subagent must NEVER run `openclaw` commands of any kind during apply runs (especially `openclaw gateway *`).
- NEVER run any command matching "openclaw gateway*".
- NEVER read job-queue.md, dedup-index.md, or job-tracker.md into context."""


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
