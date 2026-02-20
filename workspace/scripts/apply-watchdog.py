#!/usr/bin/env python3
"""Background watchdog for application stability and streak tracking.

Stops automatically after TARGET_STREAK successful apply marks in a row.
"""

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
SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
SESSION_GLOBS = ("*.jsonl", "*.jsonl.deleted.*")

ORCH_ID = "b2a0f25e-bd8a-43de-bf77-68802c7c9a0f"
TARGET_STREAK = 5
POLL_SECONDS = 30
TRIGGER_SECONDS = 120
SESSION_TRACK_WINDOW_SECONDS = 18 * 3600
MAX_TRACKED_SESSION_FILES = 300
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 18790
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


def gateway_ok() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.5)
    try:
        s.connect((GATEWAY_HOST, GATEWAY_PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def recover_gateway_if_needed() -> None:
    if gateway_ok():
        return
    log("Gateway not reachable on 127.0.0.1:18790; restarting gateway.")
    rc, out, err = run_cmd(["pnpm", "-s", "openclaw", "gateway", "restart"], cwd=OPENCLAW_DIR, timeout=90)
    log(f"gateway restart rc={rc} out={out or '-'} err={err or '-'}")


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

                            if is_subagent and FORBIDDEN_GATEWAY_CMD_RE.search(command):
                                _record_guard_violation(
                                    state,
                                    seen_guard_violations,
                                    session_id=session_id,
                                    session_file=path,
                                    rule="FORBIDDEN_GATEWAY_COMMAND",
                                    detail=command,
                                )
                            continue

                        if tool_name == "browser" and is_subagent:
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


def trigger_orchestrator(state: dict) -> None:
    now_ts = int(time.time())
    if now_ts - int(state.get("last_trigger_ts", 0)) < TRIGGER_SECONDS:
        return
    rc, out, err = run_cmd(
        [
            "pnpm",
            "-s",
            "openclaw",
            "cron",
            "run",
            ORCH_ID,
            "--timeout",
            "120000",
        ],
        cwd=OPENCLAW_DIR,
        timeout=150,
    )
    state["last_trigger_ts"] = now_ts
    log(f"orchestrator trigger rc={rc} out={out or '-'} err={err or '-'}")


def main() -> int:
    state = load_state()
    try:
        log(
            "Watchdog started. "
            f"target_streak={TARGET_STREAK} started_at={state.get('started_at')} "
            f"current_streak={state.get('streak', 0)}"
        )
        save_state(state)

        while int(state.get("streak", 0)) < TARGET_STREAK:
            recover_gateway_if_needed()
            process_new_session_events(state)
            trigger_orchestrator(state)
            save_state(state)
            if int(state.get("streak", 0)) >= TARGET_STREAK:
                break
            time.sleep(POLL_SECONDS)

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
