#!/usr/bin/env python3
"""Background watchdog for application stability and streak tracking.

Stops automatically after TARGET_STREAK successful apply marks in a row.
"""

import argparse
import fcntl
import glob
import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import time
from datetime import datetime


WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
OPENCLAW_DIR = os.path.expanduser("~/Desktop/Job Search/openclaw")
LOG_DIR = os.path.join(WORKSPACE, "logs")
STATE_PATH = os.path.join(LOG_DIR, "apply-watchdog-state.json")
RUN_LOG_PATH = os.path.join(LOG_DIR, "apply-watchdog.log")
GUARD_LOG_PATH = os.path.join(LOG_DIR, "subagent-guardrails.jsonl")
INSTANCE_LOCK_PATH = os.path.join(LOG_DIR, ".apply-watchdog.lock")
SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
# Track active transcripts only; deleted snapshots can cause duplicate counting.
SESSION_GLOBS = ("*.jsonl",)

ORCH_ID = "b2a0f25e-bd8a-43de-bf77-68802c7c9a0f"
TARGET_STREAK = 10
POLL_SECONDS = 30
TRIGGER_SECONDS = 120
SESSION_TRACK_WINDOW_SECONDS = 18 * 3600
MAX_TRACKED_SESSION_FILES = 300
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 18789
SUCCESS_MARKER = "QUEUE: Marked COMPLETED"
FAIL_MARKER_RE = re.compile(r"\bSTATUS=(DEFERRED|SKIPPED)\b")
MARK_APPLIED_REFUSAL = "ERROR: Refusing to mark APPLIED"
FORBIDDEN_GATEWAY_CMD_RE = re.compile(r"\bopenclaw\s+gateway\b", re.IGNORECASE)
FORM_FILLER_FILE_RE = re.compile(r"form-filler\.js", re.IGNORECASE)
SUBAGENT_PROMPT_RE = re.compile(
    r"(you are a subagent|subagent-lock\.py lock apply|apply to (ashby|greenhouse|lever) jobs)",
    re.IGNORECASE,
)

CANONICAL_FORM_FILLER_RELATIVE = {
    "skills/apply-ashby/scripts/form-filler.js",
    "skills/apply-greenhouse/scripts/form-filler.js",
    "skills/apply-lever/scripts/form-filler.js",
}
CANONICAL_FORM_FILLER_ABSOLUTE = {
    os.path.normpath(os.path.join(WORKSPACE, rel))
    for rel in CANONICAL_FORM_FILLER_RELATIVE
}

SUBAGENT_RUNS_PATH = os.path.expanduser("~/.openclaw/subagents/runs.json")
SESSION_STORE_PATH = os.path.expanduser("~/.openclaw/agents/main/sessions/sessions.json")
ORPHAN_GRACE_SECONDS = 90
RUN_HEARTBEAT_TIMEOUT_SECONDS = 180
RUN_STALE_SECONDS = 20 * 60


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log(msg: str) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    line = f"[{now_iso()}] {msg}\n"
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="")


def load_state() -> dict:
    now_ts = int(time.time())
    if not os.path.exists(STATE_PATH):
        return {
            "started_at": now_iso(),
            "started_epoch": now_ts,
            "streak": 0,
            "success_total": 0,
            "last_trigger_ts": 0,
            "session_offsets": {},
            "session_offsets_initialized": False,
            "session_guard": {},
            "guard_violation_ids": [],
            "guard_violation_total": 0,
        }
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        state = json.load(f)
    state.setdefault("started_at", now_iso())
    state.setdefault("started_epoch", now_ts)
    state.setdefault("streak", 0)
    state.setdefault("success_total", 0)
    state.setdefault("last_trigger_ts", 0)
    state.setdefault("session_offsets", {})
    state.setdefault("session_offsets_initialized", False)
    state.setdefault("counted_success_sessions", [])
    state.setdefault("session_guard", {})
    state.setdefault("guard_violation_ids", [])
    state.setdefault("guard_violation_total", 0)
    return state


def save_state(state: dict) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def run_cmd(argv: list[str], cwd: str | None = None, timeout: int = 90) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as e:
        return 127, "", str(e)


def _load_openclaw_config() -> dict:
    path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def cron_scheduler_enabled() -> bool:
    cfg = _load_openclaw_config()
    cron = cfg.get("cron")
    return isinstance(cron, dict) and bool(cron.get("enabled", False))


def cron_daemon_running() -> bool:
    # Modern OpenClaw runs cron scheduling inside the gateway process.
    if gateway_ok(GATEWAY_HOST, GATEWAY_PORT):
        return True
    # Backward-compat fallback for legacy standalone cron daemon setups.
    rc, out, _ = run_cmd(["pgrep", "-f", "openclaw-cron"], timeout=5)
    return rc == 0 and bool((out or "").strip())


def gateway_ok(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def recover_gateway_if_needed(host: str, port: int) -> None:
    if gateway_ok(host, port):
        return
    log(f"Gateway not reachable on {host}:{port}; restarting gateway.")
    rc, out, err = run_cmd(["pnpm", "-s", "openclaw", "gateway", "restart"], cwd=OPENCLAW_DIR, timeout=90)
    log(f"gateway restart rc={rc} out={out or '-'} err={err or '-'}")


def ensure_single_instance() -> object | None:
    os.makedirs(LOG_DIR, exist_ok=True)
    lockf = open(INSTANCE_LOCK_PATH, "w", encoding="utf-8")
    try:
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    lockf.write(str(os.getpid()))
    lockf.flush()
    return lockf


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _last_session_heartbeat_sec(run: dict, session_store: dict, now_sec: float) -> float | None:
    child_key = str(run.get("childSessionKey") or "")
    if not child_key:
        return None

    entry = session_store.get(child_key) if isinstance(session_store, dict) else None
    if not isinstance(entry, dict):
        return None

    candidates: list[float] = []
    updated_ms = entry.get("updatedAt")
    if isinstance(updated_ms, (int, float)):
        candidates.append(float(updated_ms) / 1000.0)

    session_id = entry.get("sessionId")
    if isinstance(session_id, str) and session_id:
        transcript = os.path.join(SESSION_DIR, f"{session_id}.jsonl")
        if os.path.exists(transcript):
            try:
                candidates.append(float(os.path.getmtime(transcript)))
            except OSError:
                pass

    if not candidates:
        return None
    return min(now_sec, max(candidates))


def cleanup_orphan_runs() -> int:
    runs_data = _load_json(SUBAGENT_RUNS_PATH)
    runs = runs_data.get("runs", {})
    if not isinstance(runs, dict):
        return 0

    sessions = _load_json(SESSION_STORE_PATH)
    now_sec = time.time()
    now_ms = int(now_sec * 1000)
    touched = False
    cleaned = 0

    for run in runs.values():
        if not isinstance(run, dict):
            continue
        if run.get("endedAt"):
            continue

        label = str(run.get("label", "")).lower()
        task = str(run.get("task", "")).lower()
        if not (label.startswith("apply-") or "subagent-lock.py lock apply" in task):
            continue

        started_ms = run.get("startedAt") or run.get("createdAt") or 0
        try:
            run_age_sec = max(0.0, now_sec - float(started_ms) / 1000.0)
        except (TypeError, ValueError):
            run_age_sec = 0.0

        cleanup_reason = ""
        if run_age_sec > RUN_STALE_SECONDS:
            cleanup_reason = "orphan-run-stale-ttl"
        else:
            last_heartbeat = _last_session_heartbeat_sec(run, sessions, now_sec)
            if last_heartbeat is None:
                if run_age_sec > ORPHAN_GRACE_SECONDS:
                    cleanup_reason = "orphan-missing-session-heartbeat"
            else:
                heartbeat_age = max(0.0, now_sec - last_heartbeat)
                if run_age_sec > ORPHAN_GRACE_SECONDS and heartbeat_age > RUN_HEARTBEAT_TIMEOUT_SECONDS:
                    cleanup_reason = f"orphan-heartbeat-timeout-{int(heartbeat_age)}s"

        if cleanup_reason:
            run["endedAt"] = now_ms
            run["outcome"] = {"status": "error", "error": cleanup_reason}
            run["cleanupHandled"] = True
            run["cleanupCompletedAt"] = now_ms
            cleaned += 1
            touched = True

    if touched:
        try:
            with open(SUBAGENT_RUNS_PATH, "w", encoding="utf-8") as f:
                json.dump(runs_data, f, indent=2)
                f.write("\n")
        except OSError:
            return 0

        # Also trigger lock self-heal path.
        run_cmd(["python3", "scripts/subagent-lock.py", "check", "apply"], cwd=WORKSPACE, timeout=30)
    return cleaned


def _session_id_for_child_key(session_store: dict, child_session_key: str) -> str:
    if not isinstance(session_store, dict) or not child_session_key:
        return ""
    entry = session_store.get(child_session_key)
    if not isinstance(entry, dict):
        return ""
    sid = entry.get("sessionId")
    return str(sid) if isinstance(sid, str) else ""


def terminate_subagent_run_for_session(session_id: str, reason: str) -> bool:
    """Force-end an active apply subagent run for a specific session id.

    This is used as a hard guardrail when we detect forbidden commands in a
    subagent transcript.
    """
    if not session_id:
        return False

    runs_data = _load_json(SUBAGENT_RUNS_PATH)
    runs = runs_data.get("runs", {})
    if not isinstance(runs, dict):
        return False

    session_store = _load_json(SESSION_STORE_PATH)
    now_ms = int(time.time() * 1000)
    touched = False
    terminated_run_ids: list[str] = []

    for run_id, run in runs.items():
        if not isinstance(run, dict):
            continue
        if run.get("endedAt"):
            continue

        label = str(run.get("label", "")).lower()
        task = str(run.get("task", "")).lower()
        if not (label.startswith("apply-") or "subagent-lock.py lock apply" in task):
            continue

        child_key = str(run.get("childSessionKey") or "")
        child_session_id = _session_id_for_child_key(session_store, child_key)
        if child_session_id != session_id:
            continue

        run["endedAt"] = now_ms
        run["outcome"] = {"status": "error", "error": reason[:600]}
        run["cleanupHandled"] = True
        run["cleanupCompletedAt"] = now_ms
        touched = True
        terminated_run_ids.append(str(run_id))

    if not touched:
        return False

    try:
        with open(SUBAGENT_RUNS_PATH, "w", encoding="utf-8") as f:
            json.dump(runs_data, f, indent=2)
            f.write("\n")
    except OSError:
        return False

    # Release global apply lock so orchestrator is not starved.
    run_cmd(["python3", "scripts/subagent-lock.py", "unlock", "apply"], cwd=WORKSPACE, timeout=30)
    log(
        "Force-terminated subagent run(s) for forbidden command "
        f"session={session_id} runIds={','.join(terminated_run_ids)}"
    )
    return True


def _extract_message_payload(obj: dict) -> tuple[str, str, list[dict]]:
    if obj.get("type") != "message":
        return "", "", []
    msg = obj.get("message") or {}
    role = str(msg.get("role") or "")
    parts = msg.get("content")
    if not isinstance(parts, list):
        return role, "", []
    texts = []
    tool_calls: list[dict] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        ptype = str(part.get("type") or "")
        if ptype == "text":
            txt = part.get("text")
            if isinstance(txt, str) and txt:
                texts.append(txt)
        elif ptype == "toolCall":
            tool_calls.append(
                {
                    "id": str(part.get("id") or ""),
                    "name": str(part.get("name") or ""),
                    "arguments": part.get("arguments"),
                }
            )
    return role, "\n".join(texts), tool_calls


def _normalize_cmd_text(value: str) -> str:
    return value.replace("\\ ", " ").replace('"', "").replace("'", "").strip().lower()


def _is_canonical_form_filler_path(path: str) -> bool:
    if not path:
        return False
    expanded = os.path.expanduser(path.strip().strip('"').strip("'"))
    if os.path.isabs(expanded):
        candidate = os.path.normpath(expanded)
    else:
        candidate = os.path.normpath(os.path.join(WORKSPACE, expanded))
    return candidate in CANONICAL_FORM_FILLER_ABSOLUTE


def _command_uses_canonical_form_filler(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        if FORM_FILLER_FILE_RE.search(token) and _is_canonical_form_filler_path(token):
            return True
    return False


def _looks_like_form_filler_script(script: str) -> bool:
    lower = script.lower()
    return "const profile" in lower and ("detectats" in lower or "firstName".lower() in lower)


def _extract_exec_command(arguments: object) -> str:
    if not isinstance(arguments, dict):
        return ""
    for key in ("command", "cmd"):
        val = arguments.get(key)
        if isinstance(val, str):
            return val
    return ""


def _extract_read_path(arguments: object) -> str:
    if not isinstance(arguments, dict):
        return ""
    for key in ("file_path", "path"):
        val = arguments.get(key)
        if isinstance(val, str):
            return val
    return ""


def _extract_browser_evaluate_script(arguments: object) -> str:
    if not isinstance(arguments, dict):
        return ""
    request = arguments.get("request")
    if not isinstance(request, dict):
        request = arguments
    kind = str(request.get("kind") or "")
    if kind != "evaluate":
        return ""
    script = request.get("script")
    if isinstance(script, str) and script:
        return script
    fn = request.get("fn")
    if isinstance(fn, str):
        return fn
    return ""


def _browser_request_is_stringified(arguments: object) -> bool:
    if not isinstance(arguments, dict):
        return False
    request = arguments.get("request")
    if not isinstance(request, str):
        return False
    payload = request.strip().lower()
    return "\"kind\"" in payload and "evaluate" in payload


def _append_guard_entry(entry: dict) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(GUARD_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=True) + "\n")


def _record_guard_violation(
    state: dict,
    seen_guard_violations: set[str],
    *,
    session_id: str,
    session_file: str,
    rule: str,
    detail: str,
) -> None:
    digest = hashlib.sha1(f"{session_id}|{rule}|{detail}".encode("utf-8", errors="ignore")).hexdigest()
    if digest in seen_guard_violations:
        return
    seen_guard_violations.add(digest)
    state["guard_violation_total"] = int(state.get("guard_violation_total", 0)) + 1
    entry = {
        "timestamp_iso": now_iso(),
        "session_id": session_id,
        "session_file": os.path.basename(session_file),
        "rule": rule,
        "detail": detail[:800],
    }
    _append_guard_entry(entry)
    log(f"GUARD VIOLATION [{rule}] session={os.path.basename(session_file)} detail={detail[:180]}")
    if int(state.get("streak", 0)) != 0:
        log("Guard violation observed. Resetting success streak to 0.")
    state["streak"] = 0


def _session_files() -> list[str]:
    paths: list[str] = []
    for pattern in SESSION_GLOBS:
        paths.extend(glob.glob(os.path.join(SESSION_DIR, pattern)))
    return paths


def _session_identity(path: str) -> str:
    base = os.path.basename(path)
    if ".jsonl" in base:
        return base.split(".jsonl", 1)[0]
    return base


def _initialize_session_offsets(state: dict) -> None:
    if state.get("session_offsets_initialized"):
        return
    now_ts = int(time.time())
    candidates = []
    for path in _session_files():
        try:
            mtime = int(os.path.getmtime(path))
            candidates.append((mtime, path))
        except OSError:
            continue
    candidates.sort(reverse=True)
    offsets = {}
    for mtime, path in candidates:
        if len(offsets) >= MAX_TRACKED_SESSION_FILES:
            break
        if now_ts - mtime > SESSION_TRACK_WINDOW_SECONDS:
            continue
        try:
            offsets[path] = os.path.getsize(path)
        except OSError:
            continue
    state["session_offsets"] = offsets
    state["session_offsets_initialized"] = True
    log(f"Initialized transcript offsets for {len(offsets)} session files.")


def process_new_session_events(state: dict) -> None:
    _initialize_session_offsets(state)

    now_ts = int(time.time())
    recent_files = set()
    for path in _session_files():
        try:
            if now_ts - int(os.path.getmtime(path)) <= SESSION_TRACK_WINDOW_SECONDS:
                recent_files.add(path)
        except OSError:
            continue

    offsets = state.setdefault("session_offsets", {})
    counted_success = set(state.setdefault("counted_success_sessions", []))
    session_guard = state.setdefault("session_guard", {})
    seen_guard_violations = set(state.setdefault("guard_violation_ids", []))
    current_files = set(offsets.keys()) | recent_files
    started_epoch = int(state.get("started_epoch", int(time.time())))

    for known in list(offsets.keys()):
        if known not in recent_files:
            offsets.pop(known, None)

    def _safe_mtime(path: str) -> float:
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0.0

    tracked = sorted(current_files, key=_safe_mtime)
    if len(tracked) > MAX_TRACKED_SESSION_FILES:
        tracked = tracked[-MAX_TRACKED_SESSION_FILES:]
    for path in tracked:
        try:
            size = os.path.getsize(path)
            mtime = int(os.path.getmtime(path))
        except OSError:
            continue

        prev = offsets.get(path)
        if prev is None:
            prev = 0 if mtime >= started_epoch else size
        if size < int(prev):
            prev = 0
        if size == int(prev):
            offsets[path] = size
            continue

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(int(prev))
                session_id = _session_identity(path)
                guard = session_guard.setdefault(
                    session_id,
                    {
                        "is_subagent": False,
                        "canonical_form_filler_seen": False,
                        "last_seen_ts": now_ts,
                    },
                )
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    role, text, tool_calls = _extract_message_payload(obj)
                    guard["last_seen_ts"] = now_ts

                    if role == "user" and text:
                        text_l = text.lstrip().lower()
                        if (not text_l.startswith("[cron:")) and SUBAGENT_PROMPT_RE.search(text):
                            guard["is_subagent"] = True

                    if text and role == "toolResult" and SUCCESS_MARKER in text:
                        if session_id not in counted_success:
                            counted_success.add(session_id)
                            state["streak"] = int(state.get("streak", 0)) + 1
                            state["success_total"] = int(state.get("success_total", 0)) + 1
                            log(
                                "SUCCESS event detected "
                                f"({os.path.basename(path)}). streak={state['streak']} total={state['success_total']}"
                            )
                        continue

                    if text:
                        failed = False
                        if MARK_APPLIED_REFUSAL in text:
                            failed = True
                        elif role == "assistant" and FAIL_MARKER_RE.search(text):
                            failed = True

                        if failed:
                            if int(state.get("streak", 0)) != 0:
                                log(f"Failure/defer event in {os.path.basename(path)}. Resetting streak to 0.")
                            state["streak"] = 0

                    for tool_call in tool_calls:
                        tool_name = str(tool_call.get("name") or "")
                        arguments = tool_call.get("arguments")
                        is_subagent = bool(guard.get("is_subagent"))

                        if tool_name == "read":
                            read_path = _extract_read_path(arguments)
                            if read_path and FORM_FILLER_FILE_RE.search(read_path):
                                if _is_canonical_form_filler_path(read_path):
                                    guard["canonical_form_filler_seen"] = True
                                elif is_subagent:
                                    _record_guard_violation(
                                        state,
                                        seen_guard_violations,
                                        session_id=session_id,
                                        session_file=path,
                                        rule="NON_CANONICAL_FORM_FILLER_PATH",
                                        detail=read_path,
                                    )
                            continue

                        if tool_name == "exec":
                            command = _extract_exec_command(arguments)
                            if not command:
                                continue

                            if FORM_FILLER_FILE_RE.search(command):
                                if _command_uses_canonical_form_filler(command):
                                    guard["canonical_form_filler_seen"] = True
                                elif is_subagent:
                                    _record_guard_violation(
                                        state,
                                        seen_guard_violations,
                                        session_id=session_id,
                                        session_file=path,
                                        rule="NON_CANONICAL_FORM_FILLER_PATH",
                                        detail=command,
                                    )
                                    terminate_subagent_run_for_session(
                                        session_id,
                                        f"NON_CANONICAL_FORM_FILLER_PATH: {command[:300]}",
                                    )

                            if is_subagent and FORBIDDEN_GATEWAY_CMD_RE.search(command):
                                _record_guard_violation(
                                    state,
                                    seen_guard_violations,
                                    session_id=session_id,
                                    session_file=path,
                                    rule="FORBIDDEN_GATEWAY_COMMAND",
                                    detail=command,
                                )
                                terminate_subagent_run_for_session(
                                    session_id,
                                    f"FORBIDDEN_GATEWAY_COMMAND: {command[:300]}",
                                )
                            continue

                        if tool_name == "browser" and is_subagent:
                            if _browser_request_is_stringified(arguments):
                                _record_guard_violation(
                                    state,
                                    seen_guard_violations,
                                    session_id=session_id,
                                    session_file=path,
                                    rule="BROWSER_REQUEST_STRINGIFIED",
                                    detail='browser request was a JSON string (expected object request={...})',
                                )
                                terminate_subagent_run_for_session(
                                    session_id,
                                    "BROWSER_REQUEST_STRINGIFIED: request must be object",
                                )
                                continue
                            script = _extract_browser_evaluate_script(arguments)
                            if script and _looks_like_form_filler_script(script):
                                if not bool(guard.get("canonical_form_filler_seen")):
                                    _record_guard_violation(
                                        state,
                                        seen_guard_violations,
                                        session_id=session_id,
                                        session_file=path,
                                        rule="NON_CANONICAL_FORM_FILLER_SCRIPT",
                                        detail="evaluate script looked like full form filler without canonical path read",
                                    )
                offsets[path] = f.tell()
        except OSError:
            continue

    # Keep bounded history to avoid unbounded state growth.
    state["counted_success_sessions"] = sorted(counted_success)[-2000:]
    state["guard_violation_ids"] = sorted(seen_guard_violations)[-5000:]
    if len(session_guard) > 2000:
        survivors = sorted(
            session_guard.items(),
            key=lambda kv: int((kv[1] or {}).get("last_seen_ts", 0)),
            reverse=True,
        )[:2000]
        state["session_guard"] = {k: v for k, v in survivors}


def trigger_orchestrator(state: dict, orchestrator_id: str, trigger_seconds: int) -> None:
    # Use direct trigger fallback when cron is configured but daemon is not running.
    scheduler_enabled = cron_scheduler_enabled()
    daemon_running = cron_daemon_running()
    if scheduler_enabled and daemon_running:
        return

    now_ts = int(time.time())
    if scheduler_enabled and not daemon_running:
        last_warn = int(state.get("last_cron_warn_ts", 0))
        if now_ts - last_warn >= 300:
            log("Cron is enabled but daemon is not running; using direct trigger fallback.")
            state["last_cron_warn_ts"] = now_ts

    if now_ts - int(state.get("last_trigger_ts", 0)) < trigger_seconds:
        return
    rc, out, err = run_cmd(
        [
            "pnpm",
            "-s",
            "openclaw",
            "cron",
            "run",
            orchestrator_id,
            "--timeout",
            "120000",
        ],
        cwd=OPENCLAW_DIR,
        timeout=150,
    )
    state["last_trigger_ts"] = now_ts
    out_short = (out or "-").replace("\n", " ")[:280]
    err_short = (err or "-").replace("\n", " ")[:280]
    log(f"orchestrator trigger rc={rc} out={out_short} err={err_short}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run apply watchdog until streak target is reached.")
    p.add_argument("--target-streak", type=int, default=TARGET_STREAK)
    p.add_argument("--poll-seconds", type=int, default=POLL_SECONDS)
    p.add_argument("--trigger-seconds", type=int, default=TRIGGER_SECONDS)
    p.add_argument("--gateway-host", default=GATEWAY_HOST)
    p.add_argument("--gateway-port", type=int, default=GATEWAY_PORT)
    p.add_argument("--orchestrator-id", default=ORCH_ID)
    p.add_argument("--reset-state", action="store_true", help="Reset persisted streak state before run.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.target_streak <= 0:
        print("ERROR: --target-streak must be > 0")
        return 2
    if args.poll_seconds <= 0:
        print("ERROR: --poll-seconds must be > 0")
        return 2
    if args.trigger_seconds <= 0:
        print("ERROR: --trigger-seconds must be > 0")
        return 2

    lockf = ensure_single_instance()
    if lockf is None:
        print("ERROR: apply-watchdog is already running (instance lock held).")
        return 2

    state = load_state()
    if args.reset_state:
        now_ts = int(time.time())
        state = {
            "started_at": now_iso(),
            "started_epoch": now_ts,
            "streak": 0,
            "success_total": 0,
            "last_trigger_ts": 0,
            "session_offsets": {},
            "session_offsets_initialized": False,
            "counted_success_sessions": [],
            "session_guard": {},
            "guard_violation_ids": [],
            "guard_violation_total": 0,
        }

    try:
        log(
            "Watchdog started. "
            f"target_streak={args.target_streak} started_at={state.get('started_at')} "
            f"current_streak={state.get('streak', 0)} gateway={args.gateway_host}:{args.gateway_port}"
        )
        save_state(state)

        while int(state.get("streak", 0)) < args.target_streak:
            recover_gateway_if_needed(args.gateway_host, args.gateway_port)
            cleaned = cleanup_orphan_runs()
            if cleaned:
                log(f"Cleaned {cleaned} orphan subagent run(s).")
            process_new_session_events(state)
            trigger_orchestrator(state, args.orchestrator_id, args.trigger_seconds)
            save_state(state)
            if int(state.get("streak", 0)) >= args.target_streak:
                break
            time.sleep(args.poll_seconds)

        log(
            "Target streak reached. "
            f"streak={state.get('streak', 0)} total_success={state.get('success_total', 0)}"
        )
        save_state(state)
        return 0
    except Exception as e:
        log(f"Watchdog crashed: {e!r}")
        save_state(state)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
