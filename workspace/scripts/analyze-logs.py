#!/usr/bin/env python3
"""
analyze-logs.py — Analyze application outcomes and subagent performance.

Sources:
  1. workspace/logs/applications.jsonl  — per-job structured outcomes
  2. ~/.openclaw/subagents/runs.json    — subagent run durations + orphan errors
  3. ~/.openclaw/agents/main/sessions/  — recent session files for error detail

Usage:
  python3 scripts/analyze-logs.py                    # Today's analysis
  python3 scripts/analyze-logs.py --hours 6          # Last N hours
  python3 scripts/analyze-logs.py --summary          # Compact summary

Output: Markdown report with actionable insights
"""
import sys
import os
import json
import re
import datetime
from collections import defaultdict

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
OPENCLAW_DIR = os.path.expanduser("~/.openclaw")
APP_LOG = os.path.join(WORKSPACE, "logs", "applications.jsonl")
RUNS_FILE = os.path.join(OPENCLAW_DIR, "subagents", "runs.json")
SESSIONS_DIR = os.path.join(OPENCLAW_DIR, "agents", "main", "sessions")
ANALYSIS_DIR = os.path.join(WORKSPACE, "analysis")


def load_app_log(since_dt=None):
    """Load structured application log entries."""
    entries = []
    if not os.path.exists(APP_LOG):
        return entries
    with open(APP_LOG) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if since_dt:
                    ts = datetime.datetime.fromisoformat(e.get("ts", "").replace("Z", "+00:00"))
                    if ts < since_dt:
                        continue
                entries.append(e)
            except Exception:
                pass
    return entries


def load_subagent_runs(since_dt=None):
    """Load subagent run records from runs.json."""
    if not os.path.exists(RUNS_FILE):
        return []
    with open(RUNS_FILE) as f:
        data = json.load(f)
    runs = list(data.get("runs", {}).values())

    result = []
    for r in runs:
        started = r.get("startedAt")
        ended = r.get("endedAt")
        label = r.get("label", "?")
        outcome = r.get("outcome")

        # Parse timestamps (may be ms ints or ISO strings)
        start_dt = None
        end_dt = None
        try:
            if isinstance(started, (int, float)):
                start_dt = datetime.datetime.fromtimestamp(started / 1000, tz=datetime.timezone.utc)
            elif started:
                start_dt = datetime.datetime.fromisoformat(str(started).replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            if isinstance(ended, (int, float)):
                end_dt = datetime.datetime.fromtimestamp(ended / 1000, tz=datetime.timezone.utc)
            elif ended:
                end_dt = datetime.datetime.fromisoformat(str(ended).replace("Z", "+00:00"))
        except Exception:
            pass

        if since_dt and start_dt and start_dt < since_dt:
            continue

        duration_s = None
        if start_dt and end_dt:
            duration_s = int((end_dt - start_dt).total_seconds())

        # Extract error type
        error = None
        status = None
        if isinstance(outcome, dict):
            status = outcome.get("status", "?")
            error = outcome.get("error", "")
        elif outcome is None:
            status = "running"

        result.append({
            "label": label,
            "start": start_dt,
            "end": end_dt,
            "duration_s": duration_s,
            "status": status,
            "error": error,
        })

    result.sort(key=lambda r: r.get("start") or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc))
    return result


def scan_recent_sessions(since_dt=None, max_sessions=20):
    """Scan recent session files for browser errors and outcomes."""
    if not os.path.exists(SESSIONS_DIR):
        return []

    files = []
    for fname in os.listdir(SESSIONS_DIR):
        if not fname.endswith(".jsonl") or ".lock" in fname or ".deleted" in fname:
            continue
        fpath = os.path.join(SESSIONS_DIR, fname)
        mtime = os.path.getmtime(fpath)
        files.append((mtime, fpath))

    files.sort(reverse=True)
    files = files[:max_sessions]

    results = []
    for mtime, fpath in files:
        if since_dt:
            mtime_dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
            if mtime_dt < since_dt:
                continue
        try:
            with open(fpath) as f:
                lines = f.readlines()

            # Get session ID and start time from first line
            first = json.loads(lines[0]) if lines else {}
            session_id = first.get("id", os.path.basename(fpath).replace(".jsonl", ""))
            session_ts = first.get("timestamp", "")

            # Find initial prompt (task type)
            task_label = ""
            browser_errors = 0
            browser_timeouts = 0
            last_action = ""

            for line in lines:
                try:
                    ev = json.loads(line)
                    msg = ev.get("message", {})
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        for c in content:
                            if not isinstance(c, dict):
                                continue
                            text = c.get("text", "")
                            if not task_label and text and "Apply up to" in text:
                                # Extract ATS type from first line
                                m = re.search(r"Apply up to \d+ (\w+) jobs", text)
                                if m:
                                    task_label = m.group(1).lower()
                            if c.get("type") == "tool_result":
                                res = c.get("content", "")
                                if isinstance(res, list):
                                    for r in res:
                                        if isinstance(r, dict):
                                            t = r.get("text", "")
                                            if "Can't reach the OpenClaw browser control service" in t:
                                                browser_errors += 1
                                            if "timed out after" in t.lower():
                                                browser_timeouts += 1
                                            if t.strip():
                                                last_action = t.strip()[:100]
                            if c.get("type") == "text" and c.get("text"):
                                last_action = c["text"].strip()[:100]
                except Exception:
                    pass

            results.append({
                "session_id": session_id[:8],
                "ts": session_ts[:19],
                "ats": task_label or "?",
                "events": len(lines),
                "browser_errors": browser_errors,
                "browser_timeouts": browser_timeouts,
                "last_action": last_action,
            })
        except Exception:
            pass

    return results


def generate_report(hours, app_entries, runs, sessions):
    """Generate markdown analysis report."""
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    report = [f"# Application Pipeline Analysis — {date_str} (last {hours}h)"]
    report.append(f"Generated: {now.strftime('%Y-%m-%d %H:%M')}\n")

    # --- Application outcomes ---
    report.append("## Application Outcomes (from applications.jsonl)")
    if not app_entries:
        report.append("- No structured application log entries yet.")
        report.append("  (Subagents will log here via: exec: python3 scripts/log-application.py ...)")
    else:
        by_outcome = defaultdict(list)
        by_ats = defaultdict(lambda: defaultdict(int))
        for e in app_entries:
            by_outcome[e.get("outcome", "?")].append(e)
            by_ats[e.get("ats", "?")][e.get("outcome", "?")] += 1

        for outcome, entries in sorted(by_outcome.items()):
            report.append(f"- **{outcome}**: {len(entries)} jobs")
            for e in entries[:5]:
                report.append(f"  - {e.get('company','?')} — {e.get('title','?')} [{e.get('ats','?')}]")

        report.append("")
        report.append("### By ATS")
        for ats, outcomes in sorted(by_ats.items()):
            parts = ", ".join(f"{k}:{v}" for k, v in sorted(outcomes.items()))
            report.append(f"- {ats.upper()}: {parts}")
    report.append("")

    # --- Subagent run analysis ---
    report.append("## Subagent Run Analysis (from runs.json)")
    if not runs:
        report.append("- No subagent runs in period.")
    else:
        by_status = defaultdict(list)
        for r in runs:
            by_status[r.get("status", "?")].append(r)

        by_ats = defaultdict(lambda: {"ok": 0, "err": 0, "running": 0, "durations": []})
        for r in runs:
            label = r.get("label", "")
            ats = "?"
            for a in ["greenhouse", "ashby", "lever"]:
                if a in label:
                    ats = a
                    break
            status = r.get("status", "?")
            if "ok" in str(status):
                by_ats[ats]["ok"] += 1
            elif "error" in str(status):
                by_ats[ats]["err"] += 1
            elif status == "running":
                by_ats[ats]["running"] += 1
            dur = r.get("duration_s")
            if dur:
                by_ats[ats]["durations"].append(dur)

        for ats, stats in sorted(by_ats.items()):
            durs = stats["durations"]
            avg_dur = f"{sum(durs)//len(durs)}s" if durs else "?"
            report.append(f"- **{ats.upper()}**: ok={stats['ok']} err={stats['err']} running={stats['running']} avg_dur={avg_dur}")

        # Error breakdown
        orphan_runs = [r for r in runs if "orphan-heartbeat-timeout" in str(r.get("error", ""))]
        if orphan_runs:
            timeouts = [int(re.search(r"orphan-heartbeat-timeout-(\d+)s", str(r["error"])).group(1))
                        for r in orphan_runs if re.search(r"orphan-heartbeat-timeout-(\d+)s", str(r.get("error", "")))]
            report.append(f"\n⚠️  **orphan-heartbeat-timeout**: {len(orphan_runs)} sessions killed")
            if timeouts:
                report.append(f"   Timeout values: {sorted(timeouts, reverse=True)[:8]}")
                report.append(f"   ↳ Decreasing pattern = too many concurrent sessions overloading gateway")
                report.append(f"   ↳ Fix: single-spawn mode (max 1 subagent at a time)")

        other_errors = [r for r in runs if "error" in str(r.get("status", "")) and "orphan" not in str(r.get("error", ""))]
        if other_errors:
            err_types = defaultdict(int)
            for r in other_errors:
                err_types[str(r.get("error", "?"))[:60]] += 1
            report.append(f"\nOther errors: {len(other_errors)}")
            for err, count in sorted(err_types.items(), key=lambda x: -x[1])[:5]:
                report.append(f"  - ({count}x) {err}")
    report.append("")

    # --- Session scan ---
    report.append("## Recent Session Details")
    if not sessions:
        report.append("- No recent sessions found.")
    else:
        browser_err_total = sum(s["browser_errors"] for s in sessions)
        browser_to_total = sum(s["browser_timeouts"] for s in sessions)
        report.append(f"- Sessions scanned: {len(sessions)}")
        report.append(f"- Total browser 'Can't reach' errors: {browser_err_total}")
        report.append(f"- Total browser timeout events: {browser_to_total}")
        if browser_err_total > 0:
            report.append(f"  ↳ Browser control service overwhelmed — too many concurrent sessions")
        report.append("")
        report.append("| Session | Time | ATS | Events | BrowserErr |")
        report.append("|---------|------|-----|--------|------------|")
        for s in sessions[:15]:
            report.append(f"| {s['session_id']} | {s['ts'][11:16]} | {s['ats']} | {s['events']} | {s['browser_errors']} |")
    report.append("")

    # --- Recommendations ---
    report.append("## Recommendations")
    recs = []
    orphan_count = len([r for r in runs if "orphan" in str(r.get("error", ""))])
    browser_err_total = sum(s["browser_errors"] for s in sessions) if sessions else 0

    if orphan_count > 3:
        recs.append(f"🔴 **{orphan_count} orphan-heartbeat-timeouts** — spawning too many concurrent sessions. "
                    "Use single-spawn mode (`*/2 * * * *` interval, spawn only first ready ATS).")
    if browser_err_total > 5:
        recs.append(f"🔴 **{browser_err_total} browser control timeouts** — concurrent sessions overloading gateway browser. "
                    "Reduce to 1 concurrent subagent.")
    submitted = len([e for e in app_entries if e.get("outcome") == "SUBMITTED"])
    if submitted > 0:
        recs.append(f"✅ {submitted} applications submitted in last {hours}h.")
    if not recs:
        recs.append("✅ System appears stable. Monitor for orphan timeouts.")
    for r in recs:
        report.append(f"- {r}")

    return "\n".join(report)


def generate_summary(hours, app_entries, runs, sessions):
    """Compact summary for WhatsApp."""
    submitted = len([e for e in app_entries if e.get("outcome") == "SUBMITTED"])
    skipped = len([e for e in app_entries if e.get("outcome") == "SKIPPED"])
    deferred = len([e for e in app_entries if e.get("outcome") in ("DEFERRED", "ERROR")])
    orphans = len([r for r in runs if "orphan" in str(r.get("error", ""))])
    browser_errs = sum(s.get("browser_errors", 0) for s in sessions)

    lines = [f"Pipeline ({hours}h):"]
    lines.append(f"✅ {submitted} submitted | ⏭ {skipped} skipped | ⚠ {deferred} deferred")
    if orphans:
        lines.append(f"💀 {orphans} orphan-timeout (too many concurrent sessions)")
    if browser_errs:
        lines.append(f"🌐 {browser_errs} browser errors")
    if orphans == 0 and browser_errs == 0:
        lines.append("System running cleanly!")
    return "\n".join(lines)


def main():
    hours = 24
    summary_mode = False
    date_str = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--hours" and i + 1 < len(args):
            hours = int(args[i + 1])
            i += 2
        elif args[i] == "--date" and i + 1 < len(args):
            date_str = args[i + 1]
            i += 2
        elif args[i] == "--summary":
            summary_mode = True
            i += 1
        else:
            i += 1

    since_dt = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(hours=hours)
    if date_str:
        # Use full day from the given date
        since_dt = datetime.datetime.fromisoformat(date_str).replace(tzinfo=datetime.timezone.utc)

    app_entries = load_app_log(since_dt)
    runs = load_subagent_runs(since_dt)
    sessions = scan_recent_sessions(since_dt)

    if summary_mode:
        print(generate_summary(hours, app_entries, runs, sessions))
        return

    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    report = generate_report(hours, app_entries, runs, sessions)

    report_path = os.path.join(ANALYSIS_DIR, f"daily-report-{datetime.datetime.now().strftime('%Y-%m-%d')}.md")
    with open(report_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\nSaved to: {report_path}")


if __name__ == "__main__":
    main()
