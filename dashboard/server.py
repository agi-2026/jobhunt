#!/usr/bin/env python3
"""
Job Search Dashboard v2 — Local HTTP server
Fixed: pipeline counts computed from actual entries, agent status from jobs.json,
stage updates via API, health monitoring.
Run: python3 dashboard/server.py
Open: http://localhost:8765
"""

import http.server
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

PORT = 8765
WORKSPACE = Path.home() / ".openclaw" / "workspace"
OPENCLAW_DIR = Path.home() / ".openclaw"
QUEUE_FILE = WORKSPACE / "job-queue.md"
TRACKER_FILE = WORKSPACE / "job-tracker.md"
MANUAL_DEDUP_FILE = WORKSPACE / "manual-dedup.md"
JOBS_JSON = OPENCLAW_DIR / "cron" / "jobs.json"

H1B_DEADLINE = datetime(2026, 3, 15)
OPT_EXPIRY = datetime(2026, 5, 31)


def parse_queue(content: str) -> dict:
    """Parse job-queue.md into structured sections."""
    sections = {"pending": [], "manual_apply": [], "in_progress": [], "completed": [], "skipped": []}
    stats_line = ""
    current_section = None
    current_job = None

    for line in content.split("\n"):
        if line.startswith("- Pending:"):
            stats_line = line.strip("- ")

        stripped = line.strip()
        if stripped == "## PENDING (sorted by priority score, highest first)":
            current_section = "pending"
            continue
        elif stripped == "## IN PROGRESS":
            current_section = "in_progress"
            continue
        elif stripped.startswith("## COMPLETED"):
            current_section = "completed"
            continue
        elif stripped == "## SKIPPED":
            current_section = "skipped"
            continue
        elif stripped.startswith("## ") and "DO NOT AUTO-APPLY" not in stripped:
            if current_section and current_section != "pending":
                current_section = None
            continue

        # Capture DO NOT AUTO-APPLY section header (must start with ##)
        if stripped.startswith("## ") and "DO NOT AUTO-APPLY" in stripped:
            current_section = "pending_no_auto"
            continue

        if current_section in (None,):
            continue

        effective_section = "pending" if current_section == "pending_no_auto" else current_section

        score_match = re.match(r"^###\s+\[(\d+)\]\s+(.+?)\s*—\s*(.+)$", stripped)
        if score_match:
            if current_job:
                target = "manual_apply" if current_job.get("no_auto") else current_job["_section"]
                sections[target].append(current_job)
            current_job = {
                "_section": effective_section,
                "score": int(score_match.group(1)),
                "company": score_match.group(2).strip(),
                "title": score_match.group(3).strip(),
                "url": "", "location": "", "salary": "", "h1b": "",
                "status_detail": "", "discovered": "", "applied": "",
                "no_auto": current_section == "pending_no_auto",
            }
            continue

        if current_job:
            if stripped.startswith("- **URL:**"):
                current_job["url"] = stripped.split("**URL:**")[1].strip()
            elif stripped.startswith("- **Location:**"):
                current_job["location"] = stripped.split("**Location:**")[1].strip()
            elif stripped.startswith("- **Salary:**"):
                current_job["salary"] = stripped.split("**Salary:**")[1].strip()
            elif stripped.startswith("- **H-1B:**"):
                current_job["h1b"] = stripped.split("**H-1B:**")[1].strip()
            elif stripped.startswith("- **Status:**"):
                current_job["status_detail"] = stripped.split("**Status:**")[1].strip()
            elif stripped.startswith("- **Discovered:**"):
                current_job["discovered"] = stripped.split("**Discovered:**")[1].strip()
            elif stripped.startswith("- **Applied:**"):
                current_job["applied"] = stripped.split("**Applied:**")[1].strip()
            elif "OPENAI LIMIT" in stripped or "Auto-Apply: NO" in stripped or "DATABRICKS" in stripped:
                current_job["no_auto"] = True

    if current_job:
        target = "manual_apply" if current_job.get("no_auto") else current_job["_section"]
        sections[target].append(current_job)

    for section in sections.values():
        for job in section:
            job.pop("_section", None)

    return {"stats": stats_line, "sections": sections}


def parse_tracker(content: str) -> dict:
    """Parse job-tracker.md — compute pipeline from actual entries."""
    entries = []
    current_entry = None
    daily_stats = []

    for line in content.split("\n"):
        # Parse daily stats
        daily_match = re.match(
            r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
            line,
        )
        if daily_match:
            daily_stats.append({
                "date": daily_match.group(1),
                "found": int(daily_match.group(2)),
                "applied": int(daily_match.group(3)),
                "responses": int(daily_match.group(4)),
                "interviews": int(daily_match.group(5)),
            })

        # Parse application entries
        entry_match = re.match(r"^###\s+(.+?)\s*—\s*(.+)$", line.strip())
        if entry_match:
            if current_entry:
                entries.append(current_entry)
            current_entry = {
                "company": entry_match.group(1).strip(),
                "title": entry_match.group(2).strip(),
                "stage": "", "date_applied": "", "link": "",
                "h1b": "", "notes": "",
            }
            continue

        if current_entry:
            if line.strip().startswith("- **Stage:**"):
                current_entry["stage"] = line.split("**Stage:**")[1].strip()
            elif line.strip().startswith("- **Date Applied:**"):
                current_entry["date_applied"] = line.split("**Date Applied:**")[1].strip()
            elif line.strip().startswith("- **Link:**"):
                current_entry["link"] = line.split("**Link:**")[1].strip()
            elif line.strip().startswith("- **H-1B Status:**"):
                current_entry["h1b"] = line.split("**H-1B Status:**")[1].strip()
            elif line.strip().startswith("- **Notes:**"):
                current_entry["notes"] = line.split("**Notes:**")[1].strip()[:200]

    if current_entry:
        entries.append(current_entry)

    # Compute pipeline from ACTUAL entries (not the manually maintained table)
    stage_order = [
        "Discovered", "Applied", "Confirmed", "Response",
        "Phone Screen", "Technical Interview", "Onsite/Final",
        "Offer", "Rejected"
    ]
    pipeline = {s: 0 for s in stage_order}
    for e in entries:
        stage = e.get("stage", "").strip()
        if stage in pipeline:
            pipeline[stage] += 1
        elif stage:
            # Handle variations
            stage_lower = stage.lower()
            for s in stage_order:
                if s.lower() in stage_lower:
                    pipeline[s] += 1
                    break

    return {"pipeline": pipeline, "daily_stats": daily_stats, "entries": entries}


def get_dedup_urls(tracker_entries: list, queue_data: dict) -> list:
    """Build complete dedup list from tracker + queue completed/skipped + manual."""
    urls = set()
    entries = []

    for e in tracker_entries:
        url = e.get("link", "")
        if url:
            urls.add(url)
            entries.append({
                "url": url, "company": e["company"],
                "title": e["title"], "source": "tracker",
                "stage": e.get("stage", ""),
            })

    for section_name in ["completed", "skipped"]:
        for job in queue_data["sections"].get(section_name, []):
            url = job.get("url", "")
            if url and url not in urls:
                urls.add(url)
                entries.append({
                    "url": url, "company": job["company"],
                    "title": job["title"], "source": f"queue-{section_name}",
                    "stage": section_name,
                })

    if MANUAL_DEDUP_FILE.exists():
        for line in MANUAL_DEDUP_FILE.read_text().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                parts = line[2:].split(" | ", 2)
                url = parts[0].strip()
                if url and url not in urls:
                    urls.add(url)
                    entries.append({
                        "url": url,
                        "company": parts[1].strip() if len(parts) > 1 else "Manual",
                        "title": parts[2].strip() if len(parts) > 2 else "",
                        "source": "manual", "stage": "manual",
                    })

    return entries


def get_agent_status() -> list:
    """Get agent status directly from jobs.json (no CLI timeout issues)."""
    try:
        with open(JOBS_JSON, 'r') as f:
            data = json.load(f)

        agents = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        for job in data.get("jobs", []):
            state = job.get("state", {})
            last_run_ms = state.get("lastRunAtMs", 0)
            running_ms = state.get("runningAtMs", 0)
            next_run_ms = state.get("nextRunAtMs", 0)
            last_status = state.get("lastStatus", "")
            last_duration_ms = state.get("lastDurationMs", 0)
            consecutive_errors = state.get("consecutiveErrors", 0)

            # Determine status
            if running_ms and (now_ms - running_ms) < 1800000:  # 30 min
                status = "running"
            elif last_status == "error":
                status = "error"
            elif last_status == "ok":
                status = "ok"
            else:
                status = "idle"

            # Format times
            def format_ago(ms):
                if not ms:
                    return "-"
                diff_s = (now_ms - ms) / 1000
                if diff_s < 60:
                    return "<1m ago"
                elif diff_s < 3600:
                    return f"{int(diff_s/60)}m ago"
                elif diff_s < 86400:
                    return f"{diff_s/3600:.1f}h ago"
                else:
                    return f"{int(diff_s/86400)}d ago"

            def format_until(ms):
                if not ms:
                    return "-"
                diff_s = (ms - now_ms) / 1000
                if diff_s < 0:
                    return "overdue"
                elif diff_s < 60:
                    return "in <1m"
                elif diff_s < 3600:
                    return f"in {int(diff_s/60)}m"
                else:
                    return f"in {diff_s/3600:.1f}h"

            agents.append({
                "id": job["id"][:8],
                "name": job.get("name", "Unknown"),
                "status": status,
                "enabled": job.get("enabled", True),
                "last_run": format_ago(last_run_ms),
                "next_run": format_until(next_run_ms),
                "last_duration": f"{last_duration_ms/1000:.0f}s" if last_duration_ms else "-",
                "consecutive_errors": consecutive_errors,
                "schedule": job.get("schedule", {}).get("expr", ""),
            })

        return agents
    except Exception as e:
        return [{"id": "", "name": "Error loading jobs.json", "status": str(e),
                 "last_run": "-", "next_run": "-", "last_duration": "-",
                 "consecutive_errors": 0, "schedule": "", "enabled": False}]


def add_manual_dedup(url: str, company: str = "", title: str = "") -> bool:
    """Add a URL to the manual dedup file and also add to job-tracker.md."""
    url = url.strip()
    if not url:
        return False

    if not MANUAL_DEDUP_FILE.exists():
        MANUAL_DEDUP_FILE.write_text("# Manual Dedup List\n# URLs added manually to prevent duplicate applications\n\n")

    content = MANUAL_DEDUP_FILE.read_text()
    if url in content:
        return False

    with open(MANUAL_DEDUP_FILE, "a") as f:
        f.write(f"- {url} | {company or 'Manual'} | {title or 'Manual entry'}\n")

    tracker_content = TRACKER_FILE.read_text()
    if url not in tracker_content:
        entry = f"""
### {company or 'Manual'} — {title or 'Manual Entry'}
- **Stage:** Applied
- **Date Applied:** {datetime.now().strftime('%Y-%m-%d')}
- **Source:** Manual (Howard applied directly)
- **Link:** {url}
- **Notes:** Manually added to tracker to prevent duplicate application by agent.
- **Follow-up Due:** {datetime.now().strftime('%Y-%m-%d')}
"""
        if "## Priority Follow-ups" in tracker_content:
            tracker_content = tracker_content.replace(
                "## Priority Follow-ups", entry + "\n## Priority Follow-ups"
            )
        else:
            tracker_content += entry
        TRACKER_FILE.write_text(tracker_content)

    return True


def update_stage(search_term: str, new_stage: str, notes: str = "") -> dict:
    """Update a job's stage in the tracker. Returns {ok, message}."""
    valid_stages = [
        "Discovered", "Applied", "Confirmed", "Response",
        "Phone Screen", "Technical Interview", "Onsite/Final",
        "Offer", "Rejected"
    ]
    if new_stage not in valid_stages:
        return {"ok": False, "error": f"Invalid stage. Valid: {', '.join(valid_stages)}"}

    content = TRACKER_FILE.read_text()
    lines = content.split('\n')
    search_lower = search_term.lower().strip()
    found = False
    old_stage = ''
    company = ''
    title = ''
    in_target = False

    for i, line in enumerate(lines):
        entry_match = re.match(r'^###\s+(.+?)\s*—\s*(.+)$', line.strip())
        if entry_match:
            in_target = False
            c = entry_match.group(1).strip()
            t = entry_match.group(2).strip()
            if search_lower in line.lower() or search_lower in c.lower():
                in_target = True
                company = c
                title = t
                found = True
            continue

        if in_target:
            if line.strip().startswith('- **Stage:**'):
                old_stage = line.split('**Stage:**')[1].strip()
                lines[i] = f'- **Stage:** {new_stage}'
                in_target = False

    if not found:
        return {"ok": False, "error": f"No entry matching '{search_term}'"}

    # Recompute pipeline counts in the table
    stage_counts = {s: 0 for s in valid_stages}
    for line in lines:
        if line.strip().startswith('- **Stage:**'):
            sv = line.split('**Stage:**')[1].strip()
            if sv in stage_counts:
                stage_counts[sv] += 1

    content_new = '\n'.join(lines)
    for stage_name, count in stage_counts.items():
        content_new = re.sub(
            rf'\|\s*{re.escape(stage_name)}\s*\|\s*\d+\s*\|',
            f'| {stage_name} | {count} |',
            content_new
        )

    TRACKER_FILE.write_text(content_new)
    return {"ok": True, "message": f"{company} — {title}: {old_stage} -> {new_stage}"}


def build_api_response() -> dict:
    """Build full dashboard data."""
    queue_content = QUEUE_FILE.read_text() if QUEUE_FILE.exists() else ""
    tracker_content = TRACKER_FILE.read_text() if TRACKER_FILE.exists() else ""

    queue_data = parse_queue(queue_content)
    tracker_data = parse_tracker(tracker_content)
    dedup_list = get_dedup_urls(tracker_data["entries"], queue_data)
    agents = get_agent_status()

    now = datetime.now()
    h1b_days = (H1B_DEADLINE - now).days
    opt_days = (OPT_EXPIRY - now).days

    return {
        "timestamp": now.isoformat(),
        "h1b_days": h1b_days,
        "opt_days": opt_days,
        "agents": agents,
        "queue": queue_data,
        "tracker": tracker_data,
        "dedup": dedup_list,
        "dedup_count": len(dedup_list),
    }


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Search Command Center</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
  h1 { color: #58a6ff; margin-bottom: 4px; font-size: 24px; }
  h2 { color: #8b949e; font-size: 14px; margin-bottom: 20px; font-weight: normal; }
  h3 { color: #58a6ff; font-size: 16px; margin: 16px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #21262d; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .stat-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .stat { background: #21262d; border-radius: 6px; padding: 12px 16px; flex: 1; min-width: 100px; text-align: center; }
  .stat .value { font-size: 28px; font-weight: bold; color: #58a6ff; }
  .stat .label { font-size: 11px; color: #8b949e; text-transform: uppercase; margin-top: 2px; }
  .stat.green .value { color: #3fb950; }
  .stat.yellow .value { color: #d29922; }
  .stat.red .value { color: #f85149; }
  .stat.purple .value { color: #bc8cff; }
  .stat.orange .value { color: #db6d28; }
  .agent { display: flex; align-items: center; gap: 12px; padding: 10px; border-radius: 6px; margin-bottom: 6px; background: #21262d; }
  .agent .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .dot.running { background: #3fb950; animation: pulse 1.5s infinite; }
  .dot.ok { background: #3fb950; }
  .dot.error { background: #f85149; }
  .dot.idle { background: #8b949e; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  .agent .name { font-weight: 600; flex: 1; }
  .agent .meta { font-size: 12px; color: #8b949e; }
  .agent .errors { color: #f85149; font-size: 11px; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px; color: #8b949e; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #30363d; }
  td { padding: 8px; border-bottom: 1px solid #21262d; }
  tr:hover { background: #1c2128; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .badge.pending { background: #1f6feb33; color: #58a6ff; }
  .badge.applied { background: #23883333; color: #3fb950; }
  .badge.skipped, .badge.rejected { background: #f8514933; color: #f85149; }
  .badge.confirmed, .badge.response { background: #d2992233; color: #d29922; }
  .badge.in-progress { background: #bc8cff33; color: #bc8cff; }
  .badge.phone-screen { background: #db6d2833; color: #db6d28; }
  .badge.technical-interview, .badge.onsite\/final { background: #a371f733; color: #a371f7; }
  .badge.offer { background: #3fb95033; color: #3fb950; font-size: 13px; }
  .badge.manual { background: #8b949e33; color: #8b949e; }
  .score { font-weight: bold; color: #d29922; }
  a { color: #58a6ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .url-cell { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .form-row { display: flex; gap: 8px; margin-top: 12px; }
  .form-row input, .form-row select { flex: 1; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 14px; }
  .form-row input:focus, .form-row select:focus { outline: none; border-color: #58a6ff; }
  .form-row button { padding: 8px 20px; background: #238636; border: none; border-radius: 6px; color: #fff; font-weight: 600; cursor: pointer; font-size: 14px; white-space: nowrap; }
  .form-row button:hover { background: #2ea043; }
  .refresh-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
  .refresh-bar .timer { font-size: 12px; color: #8b949e; }
  .refresh-bar button { padding: 4px 12px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; cursor: pointer; font-size: 12px; }
  .toast { position: fixed; bottom: 20px; right: 20px; background: #238636; color: #fff; padding: 12px 20px; border-radius: 8px; font-size: 14px; display: none; z-index: 100; }
  .toast.error { background: #f85149; }
  .countdown-banner { background: linear-gradient(135deg, #f8514922, #d2992222); border: 1px solid #f8514944; border-radius: 8px; padding: 12px 20px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
  .countdown-banner .days { font-size: 32px; font-weight: bold; color: #f85149; }
  .countdown-banner .label { font-size: 12px; color: #8b949e; }
  .pipeline-bar { display: flex; gap: 2px; margin-top: 8px; height: 6px; border-radius: 3px; overflow: hidden; }
  .pipeline-bar .seg { height: 100%; min-width: 2px; }
  .tabs { display: flex; gap: 2px; margin-bottom: 12px; }
  .tab { padding: 6px 14px; background: #21262d; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 13px; color: #8b949e; }
  .tab.active { background: #30363d; color: #c9d1d9; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .openai-warn { color: #d29922; font-size: 11px; }
  .stage-btn { padding: 2px 6px; background: #21262d; border: 1px solid #30363d; border-radius: 4px; color: #8b949e; cursor: pointer; font-size: 11px; }
  .stage-btn:hover { background: #30363d; color: #c9d1d9; }
</style>
</head>
<body>

<div class="refresh-bar">
  <div>
    <h1>Job Search Command Center</h1>
    <h2 id="subtitle">Loading...</h2>
  </div>
  <div style="text-align:right">
    <div class="timer" id="timer">Refreshing in 30s</div>
    <button onclick="refresh()">Refresh Now</button>
  </div>
</div>

<div class="countdown-banner" id="countdown-banner"></div>
<div class="stat-row" id="stats-row"></div>

<div class="grid">
  <div class="card">
    <h3>Agent Status</h3>
    <div id="agents"></div>
  </div>
  <div class="card">
    <h3>Pipeline (computed from entries)</h3>
    <div id="pipeline"></div>
    <div class="pipeline-bar" id="pipeline-bar"></div>
  </div>
</div>

<div class="card" style="margin-bottom:16px">
  <h3>Update Stage</h3>
  <p style="font-size:12px;color:#8b949e;margin-bottom:8px">Update a job's stage (e.g. when you get a phone screen). Search by company name or URL.</p>
  <div class="form-row">
    <input type="text" id="stage-search" placeholder="Company name or URL substring..." />
    <select id="stage-select">
      <option value="Confirmed">Confirmed</option>
      <option value="Response">Response</option>
      <option value="Phone Screen">Phone Screen</option>
      <option value="Technical Interview">Technical Interview</option>
      <option value="Onsite/Final">Onsite/Final</option>
      <option value="Offer">Offer</option>
      <option value="Rejected">Rejected</option>
    </select>
    <button onclick="updateStage()">Update Stage</button>
  </div>
</div>

<div class="card" style="margin-bottom:16px">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('pending')">Pending Queue</div>
    <div class="tab" onclick="switchTab('manual')">Manual Apply</div>
    <div class="tab" onclick="switchTab('progress')">In Progress</div>
    <div class="tab" onclick="switchTab('completed')">Completed</div>
    <div class="tab" onclick="switchTab('skipped')">Skipped</div>
  </div>
  <div class="tab-content active" id="tab-pending"></div>
  <div class="tab-content" id="tab-manual"></div>
  <div class="tab-content" id="tab-progress"></div>
  <div class="tab-content" id="tab-completed"></div>
  <div class="tab-content" id="tab-skipped"></div>
</div>

<div class="card" style="margin-bottom:16px">
  <h3>Dedup List (<span id="dedup-count">0</span> URLs)</h3>
  <p style="font-size:12px;color:#8b949e;margin-bottom:8px">All applied/tracked URLs. Agents check this before applying.</p>
  <div class="form-row">
    <input type="url" id="dedup-url" placeholder="https://jobs.ashbyhq.com/company/..." />
    <input type="text" id="dedup-company" placeholder="Company name" style="max-width:160px" />
    <input type="text" id="dedup-title" placeholder="Job title" style="max-width:200px" />
    <button onclick="addDedup()">Add to Dedup</button>
  </div>
  <div style="margin-top:12px;max-height:300px;overflow-y:auto" id="dedup-table"></div>
</div>

<div class="card">
  <h3>Application Tracker</h3>
  <div style="max-height:500px;overflow-y:auto" id="tracker-table"></div>
</div>

<div class="toast" id="toast"></div>

<script>
let data = null;
let countdown = 30;

async function refresh() {
  try {
    const resp = await fetch('/api/data');
    data = await resp.json();
    render();
    countdown = 30;
  } catch(e) {
    showToast('Failed to refresh: ' + e.message, true);
  }
}

function render() {
  if (!data) return;

  // Subtitle with dynamic H-1B countdown
  document.getElementById('subtitle').textContent =
    `JobHunt Agent | Deadline: ${data.h1b_days}d | Auto-refresh 30s`;

  // Countdown banner
  const urgency = data.h1b_days <= 14 ? 'CRITICAL' : data.h1b_days <= 21 ? 'URGENT' : 'IMPORTANT';
  document.getElementById('countdown-banner').innerHTML = `
    <div>
      <div class="label">${urgency} — H-1B Registration Deadline</div>
      <div style="color:#c9d1d9;font-size:13px;margin-top:4px">Need employer to file by mid-March 2026</div>
    </div>
    <div style="text-align:center">
      <div class="days">${data.h1b_days}</div>
      <div class="label">days left</div>
    </div>
    <div style="text-align:right">
      <div style="color:#d29922;font-size:16px;font-weight:600">OPT: ${data.opt_days}d</div>
      <div class="label">until expiry</div>
    </div>
  `;

  // Stats row — computed from actual data
  const q = data.queue.sections;
  const pipe = data.tracker.pipeline;
  const phoneScreens = pipe['Phone Screen'] || 0;
  const interviews = (pipe['Technical Interview'] || 0) + (pipe['Onsite/Final'] || 0);
  const offers = pipe['Offer'] || 0;
  const totalApplied = (pipe['Applied'] || 0) + (pipe['Confirmed'] || 0) + (pipe['Response'] || 0)
    + phoneScreens + interviews + offers;

  document.getElementById('stats-row').innerHTML = `
    <div class="stat yellow"><div class="value">${q.pending.length}</div><div class="label">Queue</div></div>
    <div class="stat green"><div class="value">${totalApplied}</div><div class="label">Applied</div></div>
    <div class="stat"><div class="value">${pipe['Confirmed'] || 0}</div><div class="label">Confirmed</div></div>
    <div class="stat orange"><div class="value">${phoneScreens}</div><div class="label">Phone Screens</div></div>
    <div class="stat purple"><div class="value">${interviews}</div><div class="label">Interviews</div></div>
    <div class="stat ${offers > 0 ? 'green' : ''}"><div class="value">${offers}</div><div class="label">Offers</div></div>
    <div class="stat red"><div class="value">${pipe['Rejected'] || 0}</div><div class="label">Rejected</div></div>
    <div class="stat"><div class="value">${data.dedup_count}</div><div class="label">Total Tracked</div></div>
  `;

  // Agents
  document.getElementById('agents').innerHTML = data.agents.map(a => `
    <div class="agent">
      <div class="dot ${a.status}"></div>
      <div class="name">${esc(a.name)} ${!a.enabled ? '<span style="color:#f85149;font-size:11px">(DISABLED)</span>' : ''}</div>
      <div class="meta">
        ${a.status.toUpperCase()}
        | Last: ${a.last_run} (${a.last_duration})
        | Next: ${a.next_run}
        | ${a.schedule}
        ${a.consecutive_errors > 0 ? `<span class="errors"> | ${a.consecutive_errors} errors</span>` : ''}
      </div>
    </div>
  `).join('');

  // Pipeline with visual bar
  const pipeColors = {
    'Discovered': '#8b949e', 'Applied': '#58a6ff', 'Confirmed': '#3fb950',
    'Response': '#d29922', 'Phone Screen': '#db6d28', 'Technical Interview': '#a371f7',
    'Onsite/Final': '#bc8cff', 'Offer': '#3fb950', 'Rejected': '#f85149'
  };
  const pipeEntries = Object.entries(pipe).filter(([,v]) => v > 0);
  const pipeTotal = Object.values(pipe).reduce((a,b) => a+b, 0) || 1;

  document.getElementById('pipeline').innerHTML = Object.entries(pipe).map(([k,v]) => `
    <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #21262d">
      <span style="color:${pipeColors[k] || '#c9d1d9'}">${k}</span>
      <span style="font-weight:bold;color:${v > 0 ? pipeColors[k] : '#8b949e'}">${v}</span>
    </div>
  `).join('');

  document.getElementById('pipeline-bar').innerHTML = pipeEntries.map(([k,v]) =>
    `<div class="seg" style="width:${v/pipeTotal*100}%;background:${pipeColors[k]}" title="${k}: ${v}"></div>`
  ).join('');

  // Queue tabs
  const manualJobs = q.manual_apply || [];
  document.querySelector('[onclick="switchTab(\'pending\')"]').textContent = `Pending Queue (${q.pending.length})`;
  document.querySelector('[onclick="switchTab(\'manual\')"]').textContent = `Manual Apply (${manualJobs.length})`;
  renderJobTable('tab-pending', q.pending, true);
  renderJobTable('tab-manual', manualJobs, true);
  renderJobTable('tab-progress', q.in_progress, true);
  renderJobTable('tab-completed', q.completed, false);
  renderJobTable('tab-skipped', q.skipped, false);

  // Dedup
  document.getElementById('dedup-count').textContent = data.dedup_count;
  document.getElementById('dedup-table').innerHTML = `<table>
    <tr><th>Company</th><th>Title</th><th>Stage</th><th>Source</th><th>URL</th></tr>
    ${data.dedup.slice(0, 100).map(d => `<tr>
      <td>${esc(d.company)}</td>
      <td>${esc(d.title)}</td>
      <td><span class="badge ${(d.stage||'').toLowerCase().replace(/[\s/]/g,'-')}">${esc(d.stage)}</span></td>
      <td>${esc(d.source)}</td>
      <td class="url-cell"><a href="${esc(d.url)}" target="_blank">${esc(d.url.substring(0,50))}...</a></td>
    </tr>`).join('')}
  </table>`;

  // Tracker with stage badges + dedup button
  document.getElementById('tracker-table').innerHTML = `<table>
    <tr><th>Company</th><th>Title</th><th>Stage</th><th>Applied</th><th>H-1B</th><th></th></tr>
    ${data.tracker.entries.map(e => `<tr>
      <td>${esc(e.company)}</td>
      <td>${esc(e.title)}</td>
      <td><span class="badge ${(e.stage||'').toLowerCase().replace(/[\s/]/g,'-')}">${esc(e.stage)}</span></td>
      <td>${esc(e.date_applied)}</td>
      <td>${esc(e.h1b)}</td>
      <td><button class="stage-btn" onclick="addJobToDedup('${esc(e.link)}','${esc(e.company)}','${esc(e.title)}')">+ Dedup</button></td>
    </tr>`).join('')}
  </table>`;
}

function renderJobTable(id, jobs, showScore) {
  document.getElementById(id).innerHTML = jobs.length === 0
    ? '<p style="color:#8b949e;padding:12px">No jobs in this section</p>'
    : `<table>
    <tr>${showScore ? '<th>Score</th>' : ''}<th>Company</th><th>Title</th><th>Location</th><th>Salary</th><th>H-1B</th><th>Link</th><th></th></tr>
    ${jobs.map(j => `<tr>
      ${showScore ? `<td class="score">${j.score}</td>` : ''}
      <td>${esc(j.company)}</td>
      <td>${esc(j.title)}</td>
      <td>${esc(j.location)}</td>
      <td>${esc(j.salary)}</td>
      <td>${esc(j.h1b).substring(0,20)}</td>
      <td class="url-cell"><a href="${esc(j.url)}" target="_blank">Apply</a></td>
      <td><button class="stage-btn" onclick="addJobToDedup('${esc(j.url)}','${esc(j.company)}','${esc(j.title)}')">+ Dedup</button></td>
    </tr>`).join('')}
  </table>`;
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  const map = {pending: 0, progress: 1, completed: 2, skipped: 3};
  document.querySelectorAll('.tab')[map[name]].classList.add('active');
  document.getElementById('tab-' + (name === 'progress' ? 'progress' : name)).classList.add('active');
}

async function addDedup() {
  const url = document.getElementById('dedup-url').value.trim();
  const company = document.getElementById('dedup-company').value.trim();
  const title = document.getElementById('dedup-title').value.trim();
  if (!url) { showToast('URL is required', true); return; }
  try {
    const resp = await fetch('/api/dedup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, company, title})
    });
    const result = await resp.json();
    if (result.ok) {
      showToast('Added to dedup list + tracker');
      document.getElementById('dedup-url').value = '';
      document.getElementById('dedup-company').value = '';
      document.getElementById('dedup-title').value = '';
      refresh();
    } else {
      showToast(result.error || 'Already exists', true);
    }
  } catch(e) { showToast('Error: ' + e.message, true); }
}

async function updateStage() {
  const search = document.getElementById('stage-search').value.trim();
  const stage = document.getElementById('stage-select').value;
  if (!search) { showToast('Enter a company name or URL', true); return; }
  try {
    const resp = await fetch('/api/stage', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({search, stage})
    });
    const result = await resp.json();
    if (result.ok) {
      showToast(result.message);
      document.getElementById('stage-search').value = '';
      refresh();
    } else {
      showToast(result.error, true);
    }
  } catch(e) { showToast('Error: ' + e.message, true); }
}

async function addJobToDedup(url, company, title) {
  if (!url) { showToast('No URL for this job', true); return; }
  try {
    const resp = await fetch('/api/dedup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, company, title})
    });
    const result = await resp.json();
    if (result.ok) {
      showToast(`${company || 'Job'} added to dedup`);
      refresh();
    } else {
      showToast(result.error || 'Already in dedup', true);
    }
  } catch(e) { showToast('Error: ' + e.message, true); }
}

function showToast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' error' : '');
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function esc(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

refresh();
setInterval(() => {
  countdown--;
  document.getElementById('timer').textContent = `Refreshing in ${countdown}s`;
  if (countdown <= 0) { refresh(); countdown = 30; }
}, 1000);
</script>
</body>
</html>
"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        elif self.path == "/api/data":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(build_api_response()).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/dedup":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            success = add_manual_dedup(body.get("url", ""), body.get("company", ""), body.get("title", ""))
            self.send_json({"ok": success} if success else {"ok": False, "error": "Already exists or empty URL"})

        elif self.path == "/api/stage":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = update_stage(body.get("search", ""), body.get("stage", ""), body.get("notes", ""))
            self.send_json(result)
        else:
            self.send_response(404)
            self.end_headers()

    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


if __name__ == "__main__":
    server = http.server.HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    print(f"\n  Job Search Dashboard v2 running at http://localhost:{PORT}")
    print(f"  Workspace: {WORKSPACE}")
    print(f"  Queue:     {QUEUE_FILE}")
    print(f"  Tracker:   {TRACKER_FILE}")
    print(f"  Agents:    {JOBS_JSON}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard.")
        server.server_close()
