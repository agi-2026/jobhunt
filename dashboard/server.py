#!/usr/bin/env python3
"""
Job Search Dashboard v3 — Simplified, focused UI
3 tabs: Pending Queue, Manual Apply, Applied (with search + inline stage update)
Run: python3 dashboard/server.py
Open: http://localhost:8765
"""

import http.server
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PORT = 8765
WORKSPACE = Path.home() / ".openclaw" / "workspace"
OPENCLAW_DIR = Path.home() / ".openclaw"
QUEUE_FILE = WORKSPACE / "job-queue.md"
TRACKER_FILE = WORKSPACE / "job-tracker.md"
DEDUP_FILE = WORKSPACE / "dedup-index.md"
MANUAL_APPLY_FILE = WORKSPACE / "manual-apply-priority.md"
JOBS_JSON = OPENCLAW_DIR / "cron" / "jobs.json"
SKIP_LIST_FILE = WORKSPACE / "skip-companies.json"

# H-1B deadlines
OFFER_DEADLINE = datetime(2026, 3, 6, 12, 0)   # Need offer by this date
H1B_REG_DEADLINE = datetime(2026, 3, 19, 12, 0) # Final registration deadline

NO_AUTO_COMPANIES = {"openai", "databricks", "waymo"}


def canonicalize_url(url: str) -> str:
    """Normalize URLs for consistent matching across files."""
    u = (url or "").strip()
    if not u:
        return ""
    u = u.rstrip("/")
    u = u.replace("/application", "")
    return u.rstrip("/")


def parse_queue(content: str) -> dict:
    """Parse job-queue.md into pending and manual_apply lists."""
    sections = {"pending": [], "manual_apply": []}
    current_section = None
    current_job = None

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped == "## PENDING (sorted by priority score, highest first)":
            current_section = "pending"
            continue
        elif stripped.startswith("## ") and "DO NOT AUTO-APPLY" in stripped:
            current_section = "pending_no_auto"
            continue
        elif stripped.startswith("## "):
            if current_job:
                target = "manual_apply" if current_job.get("no_auto") else current_job.get("_section", "pending")
                if target in sections:
                    sections[target].append(current_job)
                current_job = None
            current_section = None
            continue

        if current_section is None:
            continue

        effective_section = "pending" if current_section == "pending_no_auto" else current_section

        score_match = re.match(r"^###\s+\[(\d+)\]\s+(.+?)\s*—\s*(.+)$", stripped)
        if score_match:
            if current_job:
                target = "manual_apply" if current_job.get("no_auto") else current_job["_section"]
                if target in sections:
                    sections[target].append(current_job)
            current_job = {
                "_section": effective_section,
                "score": int(score_match.group(1)),
                "company": score_match.group(2).strip(),
                "title": score_match.group(3).strip(),
                "url": "", "location": "", "h1b": "",
                "no_auto": current_section == "pending_no_auto",
            }
            continue

        if current_job:
            if stripped.startswith("- **URL:**"):
                current_job["url"] = stripped.split("**URL:**")[1].strip()
            elif stripped.startswith("- **Location:**"):
                current_job["location"] = stripped.split("**Location:**")[1].strip()
            elif stripped.startswith("- **H-1B:**"):
                current_job["h1b"] = stripped.split("**H-1B:**")[1].strip()
            elif "OPENAI LIMIT" in stripped or "Auto-Apply: NO" in stripped or "DATABRICKS" in stripped:
                current_job["no_auto"] = True

    if current_job:
        target = "manual_apply" if current_job.get("no_auto") else current_job.get("_section", "pending")
        if target in sections:
            sections[target].append(current_job)

    # Company-level NO-AUTO
    new_pending = []
    for job in sections["pending"]:
        if job.get("company", "").lower() in NO_AUTO_COMPANIES:
            job["no_auto"] = True
            sections["manual_apply"].append(job)
        else:
            new_pending.append(job)
    sections["pending"] = new_pending

    for section in sections.values():
        for job in section:
            job.pop("_section", None)

    return sections


def parse_tracker(content: str) -> dict:
    """Parse job-tracker.md for pipeline stages and entries."""
    entries = []
    current_entry = None
    in_comment = False

    for line in content.split("\n"):
        stripped = line.strip()
        if "<!--" in stripped:
            in_comment = True
        if "-->" in stripped:
            in_comment = False
            continue
        if in_comment:
            continue
        entry_match = re.match(r"^###\s+(.+?)\s*—\s*(.+)$", stripped)
        if entry_match:
            if current_entry:
                entries.append(current_entry)
            current_entry = {
                "company": entry_match.group(1).strip(),
                "title": entry_match.group(2).strip(),
                "stage": "", "date_applied": "", "link": "",
            }
            continue

        if current_entry:
            if line.strip().startswith("- **Stage:**"):
                current_entry["stage"] = line.split("**Stage:**")[1].strip()
            elif line.strip().startswith("- **Date Applied:**"):
                current_entry["date_applied"] = line.split("**Date Applied:**")[1].strip()
            elif line.strip().startswith("- **Link:**"):
                current_entry["link"] = line.split("**Link:**")[1].strip()

    if current_entry:
        entries.append(current_entry)

    stage_order = ["Applied", "Phone Screen", "Technical Interview",
                   "Take Home", "Onsite/Final", "Offer", "Rejected"]
    # Normalize legacy stages
    stage_normalize = {"Confirmed": "Applied", "Discovered": "Applied",
                       "Response": "Applied", "Technical": "Technical Interview",
                       "Onsite": "Onsite/Final"}
    pipeline = {s: 0 for s in stage_order}
    for e in entries:
        stage = e.get("stage", "").strip()
        # Clean up variants like "Applied (pending verification)"
        if "(" in stage:
            stage = stage.split("(")[0].strip()
        stage = stage_normalize.get(stage, stage)
        e["stage"] = stage  # Update entry in-place for downstream use
        if stage in pipeline:
            pipeline[stage] += 1
        elif stage:
            for s in stage_order:
                if s.lower() in stage.lower():
                    pipeline[s] += 1
                    break

    return {"pipeline": pipeline, "entries": entries}


STAGE_NORMALIZE = {"Confirmed": "Applied", "Discovered": "Applied",
                   "Response": "Applied", "Technical": "Technical Interview",
                   "Onsite": "Onsite/Final"}


def normalize_stage(stage: str) -> str:
    """Normalize legacy stage names to current ones."""
    stage = stage.strip()
    if "(" in stage:
        stage = stage.split("(")[0].strip()
    return STAGE_NORMALIZE.get(stage, stage)


def sanitize_applied_date(raw: str) -> str:
    """Clamp future dates to today; preserve non-date strings."""
    value = (raw or "").strip()
    if not value:
        return ""
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", value)
    if not m:
        return value
    try:
        parsed = datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return value
    if parsed > datetime.now().date():
        return datetime.now().strftime("%Y-%m-%d")
    return value


def get_applied_jobs() -> list:
    """Get all applied jobs by merging dedup-index.md with tracker stages."""
    # Build stage/date lookup from tracker
    tracker_content = TRACKER_FILE.read_text() if TRACKER_FILE.exists() else ""
    tracker_data = parse_tracker(tracker_content)
    stage_by_url = {}
    date_by_url = {}
    for e in tracker_data["entries"]:
        url_raw = e.get("link", "").strip()
        url = canonicalize_url(url_raw)
        if url:
            stage_by_url[url] = normalize_stage(e.get("stage", "Applied"))
            date_by_url[url] = sanitize_applied_date(e.get("date_applied", ""))

    # Parse dedup for all APPLIED entries
    entries = []
    seen_urls = set()
    if DEDUP_FILE.exists():
        for line in DEDUP_FILE.read_text().split("\n"):
            if "| APPLIED" not in line:
                continue
            parts = line.split(" | ")
            if len(parts) < 4:
                continue
            url_raw = parts[0].strip()
            url = canonicalize_url(url_raw)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            company = parts[1].strip() if len(parts) > 1 else ""
            title = parts[2].strip() if len(parts) > 2 else ""
            date = sanitize_applied_date((parts[4].strip() if len(parts) > 4 else "") or date_by_url.get(url, ""))
            stage = stage_by_url.get(url, "Applied")
            entries.append({
                "url": url_raw, "company": company, "title": title,
                "date": date, "stage": stage,
            })

    # Also include tracker entries not in dedup
    for e in tracker_data["entries"]:
        url = e.get("link", "").strip()
        url_key = canonicalize_url(url)
        if url and url_key and url_key not in seen_urls:
            seen_urls.add(url_key)
            entries.append({
                "url": url, "company": e["company"], "title": e["title"],
                "date": sanitize_applied_date(e.get("date_applied", "")), "stage": normalize_stage(e.get("stage", "Applied")),
            })

    entries.sort(key=lambda x: x.get("date", ""), reverse=True)
    return entries


def parse_manual_apply() -> list:
    """Parse manual-apply-priority.md into entries for Manual Apply tab."""
    if not MANUAL_APPLY_FILE.exists():
        return []
    content = MANUAL_APPLY_FILE.read_text()
    entries = []
    current_tier = ""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("## TIER"):
            current_tier = stripped.split("—")[0].replace("## ", "").strip() if "—" in stripped else stripped.replace("## ", "").strip()
            continue
        if stripped.startswith("## SKIP") or stripped.startswith("## Strategy"):
            current_tier = ""
            continue
        if not current_tier or not stripped.startswith("- ["):
            continue
        checked = "[x]" in stripped
        if checked:
            continue  # Already applied, skip from manual list
        rest = stripped.split("] ", 1)[1] if "] " in stripped else ""
        company_match = re.match(r"\*\*(.+?)\*\*", rest)
        if not company_match:
            continue
        company = company_match.group(1)
        after_company = rest[company_match.end():].strip()
        parts = after_company.split(" — ", 1) if " — " in after_company else [after_company, ""]
        description = parts[0].strip().lstrip("— ") if parts[0] else ""
        url = parts[1].strip() if len(parts) > 1 else ""
        entries.append({
            "score": 0, "company": company,
            "title": description or "See careers page",
            "url": url, "location": current_tier,
            "h1b": "", "no_auto": True,
        })
    return entries


def get_agent_status() -> list:
    """Get agent status from jobs.json."""
    try:
        with open(JOBS_JSON, 'r') as f:
            data = json.load(f)
        agents = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        for job in data.get("jobs", []):
            if not job.get("enabled", True):
                continue
            state = job.get("state", {})
            running_ms = state.get("runningAtMs", 0)
            last_status = state.get("lastStatus", "")
            errors = state.get("consecutiveErrors", 0)
            if running_ms and (now_ms - running_ms) < 1800000:
                status = "running"
            elif last_status == "error":
                status = "error"
            elif last_status == "ok":
                status = "ok"
            else:
                status = "idle"
            agents.append({"name": job.get("name", "Unknown"), "status": status, "errors": errors})
        return agents
    except Exception:
        return []


def count_dedup_applied() -> int:
    """Count APPLIED entries in dedup-index.md."""
    if not DEDUP_FILE.exists():
        return 0
    return DEDUP_FILE.read_text().count("| APPLIED")


def mark_as_applied(url: str, company: str = "", title: str = "") -> dict:
    """Mark a job as applied: update queue, dedup, and tracker."""
    url = url.strip()
    if not url:
        return {"ok": False, "error": "URL is required"}

    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Update dedup-index.md
    if DEDUP_FILE.exists():
        dedup_content = DEDUP_FILE.read_text()
        url_base = url.replace("/application", "")
        if url not in dedup_content and url_base not in dedup_content:
            with open(DEDUP_FILE, "a") as f:
                f.write(f"{url} | {company or 'Manual'} | {title or 'Manual entry'} | APPLIED | {today}\n")
        else:
            lines = dedup_content.split("\n")
            updated = False
            for i, line in enumerate(lines):
                if (url in line or url_base in line) and "PENDING" in line:
                    parts = line.split(" | ")
                    if len(parts) >= 4:
                        parts[3] = "APPLIED"
                    if len(parts) >= 5:
                        parts[4] = f" {today}"
                    else:
                        parts.append(f" {today}")
                    lines[i] = " | ".join(parts)
                    updated = True
            if updated:
                DEDUP_FILE.write_text("\n".join(lines))
    else:
        DEDUP_FILE.write_text(f"# Dedup Index\n{url} | {company or 'Manual'} | {title or 'Manual entry'} | APPLIED | {today}\n")

    # 2. Remove from pending in job-queue.md
    if QUEUE_FILE.exists():
        content = QUEUE_FILE.read_text()
        lines = content.split("\n")
        url_variants = [url, url + "/application", url.replace("/application", "")]
        i = 0
        removed = False
        while i < len(lines):
            if lines[i].startswith("### "):
                block_start = i
                block_end = i + 1
                while block_end < len(lines) and not lines[block_end].startswith("### ") and not lines[block_end].startswith("## "):
                    block_end += 1
                block = "\n".join(lines[block_start:block_end])
                if any(v in block for v in url_variants):
                    del lines[block_start:block_end]
                    removed = True
                    continue
                i = block_end
            else:
                i += 1
        if removed:
            QUEUE_FILE.write_text("\n".join(lines))

    # 3. Add to job-tracker.md
    if TRACKER_FILE.exists():
        tracker_content = TRACKER_FILE.read_text()
        url_base = url.replace("/application", "")
        if url not in tracker_content and url_base not in tracker_content:
            entry = f"\n### {company or 'Manual'} — {title or 'Manual Entry'}\n"
            entry += f"- **Stage:** Applied\n"
            entry += f"- **Date Applied:** {today}\n"
            entry += f"- **Source:** Manual (Howard applied directly)\n"
            entry += f"- **Link:** {url}\n"
            entry += f"- **Notes:** Manually marked as applied via dashboard\n"
            if "## Priority Follow-ups" in tracker_content:
                tracker_content = tracker_content.replace(
                    "## Priority Follow-ups", entry + "\n## Priority Follow-ups"
                )
            else:
                tracker_content += entry
            TRACKER_FILE.write_text(tracker_content)

    return {"ok": True, "message": f"Marked {company or 'job'} — {title or 'unknown'} as applied"}


def delete_from_queue(url: str, company: str = "", title: str = "") -> dict:
    """Delete a job from queue and add to dedup as SKIPPED to prevent re-discovery."""
    url = url.strip()
    if not url:
        return {"ok": False, "error": "URL is required"}

    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Add/update dedup-index.md as SKIPPED
    if DEDUP_FILE.exists():
        dedup_content = DEDUP_FILE.read_text()
        url_base = url.replace("/application", "")
        if url not in dedup_content and url_base not in dedup_content:
            with open(DEDUP_FILE, "a") as f:
                f.write(f"{url} | {company or 'Unknown'} | {title or 'Deleted'} | SKIPPED | {today}\n")
        else:
            lines = dedup_content.split("\n")
            updated = False
            for i, line in enumerate(lines):
                if (url in line or url_base in line) and "PENDING" in line:
                    parts = line.split(" | ")
                    if len(parts) >= 4:
                        parts[3] = "SKIPPED"
                    if len(parts) >= 5:
                        parts[4] = f" {today}"
                    else:
                        parts.append(f" {today}")
                    lines[i] = " | ".join(parts)
                    updated = True
            if updated:
                DEDUP_FILE.write_text("\n".join(lines))
    else:
        DEDUP_FILE.write_text(f"# Dedup Index\n{url} | {company or 'Unknown'} | {title or 'Deleted'} | SKIPPED | {today}\n")

    # 2. Remove from pending in job-queue.md
    if QUEUE_FILE.exists():
        content = QUEUE_FILE.read_text()
        lines = content.split("\n")
        url_variants = [url, url + "/application", url.replace("/application", "")]
        i = 0
        removed = False
        while i < len(lines):
            if lines[i].startswith("### "):
                block_start = i
                block_end = i + 1
                while block_end < len(lines) and not lines[block_end].startswith("### ") and not lines[block_end].startswith("## "):
                    block_end += 1
                block = "\n".join(lines[block_start:block_end])
                if any(v in block for v in url_variants):
                    del lines[block_start:block_end]
                    removed = True
                    continue
                i = block_end
            else:
                i += 1
        if removed:
            QUEUE_FILE.write_text("\n".join(lines))

    return {"ok": True, "message": f"Deleted {company or 'job'} — {title or 'unknown'} (added to dedup as SKIPPED)"}


def update_stage(search_term: str, new_stage: str, url: str = "", company: str = "", title: str = "") -> dict:
    """Update a job's stage in the tracker. Searches by company name or URL."""
    valid_stages = ["Applied", "Phone Screen", "Technical Interview",
                    "Take Home", "Onsite/Final", "Offer", "Rejected"]
    if new_stage not in valid_stages:
        return {"ok": False, "error": f"Invalid stage. Valid: {', '.join(valid_stages)}"}

    if not TRACKER_FILE.exists():
        return {"ok": False, "error": "Tracker file not found"}

    content = TRACKER_FILE.read_text()
    lines = content.split('\n')
    search_lower = search_term.lower().strip()
    target_url = canonicalize_url(url or search_term)

    # Parse entries with line positions
    entries = []
    current = None
    for i, line in enumerate(lines):
        entry_match = re.match(r'^###\s+(.+?)\s*—\s*(.+)$', line.strip())
        if entry_match:
            if current:
                entries.append(current)
            current = {
                "company": entry_match.group(1).strip(),
                "title": entry_match.group(2).strip(),
                "link": "", "stage_line": None, "heading_line": i,
            }
            continue
        if current:
            if line.strip().startswith('- **Stage:**'):
                current["stage_line"] = i
            elif line.strip().startswith('- **Link:**'):
                current["link"] = line.split('**Link:**')[1].strip()
    if current:
        entries.append(current)

    # Find match by company, title, or URL
    match = None
    url_matches = []
    if target_url:
        for e in entries:
            if canonicalize_url(e.get("link", "")) == target_url:
                url_matches.append(e)
        if url_matches:
            match = url_matches[0]
    for e in entries:
        if match:
            break
        searchable = f"{e['company']} {e['title']} {e['link']}".lower()
        if search_lower in searchable:
            match = e
            break

    if not match:
        # Dedup-only applied jobs can appear in dashboard without tracker rows yet.
        # Create a tracker entry so stage updates are always possible from UI.
        safe_company = (company or "Unknown Company").strip()
        safe_title = (title or "Unknown Role").strip()
        safe_url = (url or search_term).strip()
        today = datetime.now().strftime("%Y-%m-%d")
        entry = [
            "",
            f"### {safe_company} — {safe_title}",
            f"- **Stage:** {new_stage}",
            f"- **Date Applied:** {today}",
            "- **Source:** Dashboard stage update (tracker backfill)",
            f"- **Link:** {safe_url}",
        ]
        TRACKER_FILE.write_text(content.rstrip() + "\n" + "\n".join(entry) + "\n")
        return {"ok": True, "message": f"{safe_company} — {safe_title}: created tracker entry -> {new_stage}"}

    if url_matches:
        changed = 0
        inserted = 0
        # Update from bottom to top so line inserts don't shift upcoming indexes.
        for e in sorted(url_matches, key=lambda x: x["heading_line"], reverse=True):
            if e["stage_line"] is None:
                insert_at = e["heading_line"] + 1
                lines.insert(insert_at, f"- **Stage:** {new_stage}")
                inserted += 1
            else:
                lines[e["stage_line"]] = f'- **Stage:** {new_stage}'
                changed += 1
        TRACKER_FILE.write_text('\n'.join(lines))
        label = f"{match['company']} — {match['title']}"
        details = f"updated {changed}"
        if inserted:
            details += f", inserted {inserted}"
        return {"ok": True, "message": f"{label}: {details} tracker row(s) -> {new_stage}"}

    if match["stage_line"] is None:
        insert_at = match["heading_line"] + 1
        lines.insert(insert_at, f"- **Stage:** {new_stage}")
        TRACKER_FILE.write_text('\n'.join(lines))
        return {"ok": True, "message": f"{match['company']} — {match['title']}: (missing stage) -> {new_stage}"}

    old_stage = lines[match["stage_line"]].split('**Stage:**')[1].strip()
    lines[match["stage_line"]] = f'- **Stage:** {new_stage}'
    TRACKER_FILE.write_text('\n'.join(lines))
    return {"ok": True, "message": f"{match['company']} — {match['title']}: {old_stage} -> {new_stage}"}


SCRIPTS_DIR = WORKSPACE / "scripts"


def extract_from_url(url: str) -> dict:
    """Extract company and ATS type from a job URL."""
    info = {"company": "", "title": "", "ats": ""}
    url_lower = url.lower()
    # Ashby
    m = re.search(r"jobs\.ashbyhq\.com/([^/]+)", url_lower)
    if m:
        info["company"] = m.group(1).replace("-", " ").title()
        info["ats"] = "ashby"
        return info
    # Greenhouse
    m = re.search(r"boards\.greenhouse\.io/([^/]+)", url_lower)
    if not m:
        m = re.search(r"job-boards\.greenhouse\.io/([^/]+)", url_lower)
    if m:
        info["company"] = m.group(1).replace("-", " ").title()
        info["ats"] = "greenhouse"
        return info
    # Lever
    m = re.search(r"jobs\.lever\.co/([^/]+)", url_lower)
    if m:
        info["company"] = m.group(1).replace("-", " ").title()
        info["ats"] = "lever"
        return info
    # Generic: use domain
    m = re.search(r"https?://(?:www\.)?([^/]+)", url_lower)
    if m:
        info["company"] = m.group(1).split(".")[0].replace("-", " ").title()
    return info


def add_job(url: str, destination: str = "queue") -> dict:
    """Add a job URL to queue or mark as applied. Runs preflight + add-to-queue."""
    import subprocess
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        return {"ok": False, "error": "URL must start with http"}

    info = extract_from_url(url)
    company = info["company"]

    # Check dedup first
    if DEDUP_FILE.exists():
        dedup_content = DEDUP_FILE.read_text()
        url_base = url.replace("/application", "")
        if url in dedup_content or url_base in dedup_content:
            return {"ok": False, "error": f"Already in system (dedup hit)"}

    if destination == "applied":
        return mark_as_applied(url, company, "Manual entry")

    # Run preflight check
    preflight = SCRIPTS_DIR / "preflight-check.py"
    try:
        result = subprocess.run(
            ["python3", str(preflight), url],
            capture_output=True, text=True, timeout=15
        )
        output = result.stdout.strip()
        if output.startswith("DEAD"):
            return {"ok": False, "error": f"Job posting is dead: {output}"}
    except Exception:
        pass  # Preflight failure is non-blocking

    # Add to queue via add-to-queue.py
    add_script = SCRIPTS_DIR / "add-to-queue.py"
    job_json = json.dumps({
        "score": 0,
        "company": company,
        "title": "Manually added — needs review",
        "url": url,
        "location": "Unknown",
        "source": "Dashboard manual add",
        "autoApply": True,
    })
    try:
        result = subprocess.run(
            ["python3", str(add_script), job_json],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout.strip()
        if "DUPLICATE" in output:
            return {"ok": False, "error": "Already in queue (duplicate)"}
        if "ADDED" in output:
            return {"ok": True, "message": output}
        return {"ok": False, "error": output or "Unknown error"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_skip_list() -> list:
    """Get the skip companies list."""
    try:
        with open(SKIP_LIST_FILE, 'r') as f:
            data = json.load(f)
        return data.get("companies", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add_to_skip_list(name: str, reason: str, category: str = "manual") -> dict:
    """Add a company to the skip list."""
    name = name.strip()
    if not name:
        return {"ok": False, "error": "Company name required"}
    try:
        with open(SKIP_LIST_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"companies": []}
    # Check duplicate
    for c in data["companies"]:
        if c["name"].lower() == name.lower():
            return {"ok": False, "error": f"{name} already in skip list"}
    data["companies"].append({"name": name, "reason": reason or "Manually added", "category": category})
    with open(SKIP_LIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return {"ok": True, "message": f"Added {name} to skip list"}


def remove_from_skip_list(name: str) -> dict:
    """Remove a company from the skip list."""
    try:
        with open(SKIP_LIST_FILE, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"ok": False, "error": "Skip list not found"}
    original = len(data.get("companies", []))
    data["companies"] = [c for c in data.get("companies", []) if c["name"].lower() != name.lower()]
    if len(data["companies"]) == original:
        return {"ok": False, "error": f"{name} not found in skip list"}
    with open(SKIP_LIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return {"ok": True, "message": f"Removed {name} from skip list"}


def build_api_response() -> dict:
    """Build full dashboard data."""
    queue_content = QUEUE_FILE.read_text() if QUEUE_FILE.exists() else ""
    queue_sections = parse_queue(queue_content)

    # Merge manual-apply-priority.md entries
    manual_entries = parse_manual_apply()
    queue_sections["manual_apply"].extend(manual_entries)

    applied_jobs = get_applied_jobs()
    agents = get_agent_status()
    dedup_applied = count_dedup_applied()

    # Pipeline from tracker
    tracker_content = TRACKER_FILE.read_text() if TRACKER_FILE.exists() else ""
    tracker_data = parse_tracker(tracker_content)

    now = datetime.now()
    offer_days = (OFFER_DEADLINE - now).days
    h1b_days = (H1B_REG_DEADLINE - now).days

    # Sort queues by score descending so highest-priority jobs appear first
    queue_sections["pending"].sort(key=lambda j: j.get("score", 0), reverse=True)
    queue_sections["manual_apply"].sort(key=lambda j: j.get("score", 0), reverse=True)

    return {
        "timestamp": now.isoformat(),
        "offer_days": offer_days,
        "h1b_days": h1b_days,
        "agents": agents,
        "pending": queue_sections["pending"],
        "manual_apply": queue_sections["manual_apply"],
        "applied": applied_jobs,
        "applied_count": dedup_applied,
        "pipeline": tracker_data["pipeline"],
        "skip_list": get_skip_list(),
    }


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Search Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; padding: 20px; }
  .header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
  .header h1 { color: #58a6ff; font-size: 22px; }
  .header .sub { font-size: 13px; color: #8b949e; margin-top: 4px; }
  .header .controls { text-align: right; }
  .header .timer { font-size: 12px; color: #8b949e; }
  .header button { padding: 4px 12px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; cursor: pointer; font-size: 12px; }
  .countdown { background: linear-gradient(135deg, #f8514922, #d2992222); border: 1px solid #f8514944; border-radius: 8px; padding: 14px 20px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }
  .countdown .days { font-size: 36px; font-weight: bold; color: #f85149; }
  .countdown .label { font-size: 12px; color: #8b949e; }
  .countdown .detail { font-size: 13px; color: #c9d1d9; }
  .stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px 16px; flex: 1; min-width: 90px; text-align: center; }
  .stat .value { font-size: 28px; font-weight: bold; }
  .stat .label { font-size: 11px; color: #8b949e; text-transform: uppercase; margin-top: 2px; }
  .v-yellow { color: #d29922; }
  .v-green { color: #3fb950; }
  .v-blue { color: #58a6ff; }
  .v-purple { color: #bc8cff; }
  .v-red { color: #f85149; }
  .agents-bar { display: flex; gap: 16px; margin-bottom: 16px; padding: 8px 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; font-size: 13px; align-items: center; }
  .agents-bar .lbl { color: #8b949e; font-size: 11px; text-transform: uppercase; margin-right: 4px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 6px; }
  .dot.ok, .dot.running { background: #3fb950; }
  .dot.running { animation: pulse 1.5s infinite; }
  .dot.error { background: #f85149; }
  .dot.idle { background: #8b949e; }
  @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
  .add-bar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
  .add-bar input { flex: 1; padding: 10px 14px; background: #0d1117; border: 1px solid #30363d; border-radius: 8px; color: #c9d1d9; font-size: 14px; }
  .add-bar input:focus { outline: none; border-color: #58a6ff; }
  .btn-add-queue { padding: 8px 16px; background: #1f6feb; border: 1px solid #1f6feb; border-radius: 6px; color: #fff; cursor: pointer; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .btn-add-queue:hover { background: #388bfd; }
  .btn-add-applied { padding: 8px 16px; background: #238636; border: 1px solid #238636; border-radius: 6px; color: #fff; cursor: pointer; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .btn-add-applied:hover { background: #2ea043; }
  .tabs { display: flex; gap: 2px; }
  .tab { padding: 8px 16px; background: #21262d; border-radius: 8px 8px 0 0; cursor: pointer; font-size: 13px; color: #8b949e; border: 1px solid transparent; border-bottom: none; }
  .tab.active { background: #161b22; color: #c9d1d9; border-color: #30363d; }
  .panel { display: none; background: #161b22; border: 1px solid #30363d; border-radius: 0 8px 8px 8px; padding: 16px; margin-bottom: 16px; max-height: calc(100vh - 340px); overflow-y: auto; }
  .panel.active { display: block; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px; color: #8b949e; font-size: 11px; text-transform: uppercase; border-bottom: 1px solid #30363d; }
  td { padding: 8px; border-bottom: 1px solid #21262d; }
  tr:hover { background: #1c2128; }
  .score { font-weight: bold; color: #d29922; }
  a { color: #58a6ff; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .url-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .btn-mark { padding: 4px 10px; background: #238636; border: 1px solid #238636; border-radius: 4px; color: #fff; cursor: pointer; font-size: 12px; font-weight: 600; white-space: nowrap; }
  .btn-mark:hover { background: #2ea043; }
  .btn-delete { padding: 4px 10px; background: #da3633; border: 1px solid #da3633; border-radius: 4px; color: #fff; cursor: pointer; font-size: 12px; font-weight: 600; white-space: nowrap; margin-left: 4px; }
  .btn-delete:hover { background: #f85149; }
  .btn-update { padding: 3px 8px; background: #1f6feb; border: 1px solid #1f6feb; border-radius: 4px; color: #fff; cursor: pointer; font-size: 11px; font-weight: 600; }
  .btn-update:hover { background: #388bfd; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .b-applied { background: #58a6ff22; color: #58a6ff; }
  .b-phone { background: #db6d2822; color: #db6d28; }
  .b-interview { background: #a371f722; color: #a371f7; }
  .b-takehome { background: #d2992222; color: #d29922; }
  .b-offer { background: #3fb95044; color: #3fb950; font-weight: bold; }
  .b-rejected { background: #f8514922; color: #f85149; }
  .b-csp { background: #f8514922; color: #f85149; }
  .b-limit { background: #d2992222; color: #d29922; }
  .b-technical { background: #a371f722; color: #a371f7; }
  .b-captcha { background: #db6d2822; color: #db6d28; }
  .b-manual { background: #8b949e22; color: #8b949e; }
  .btn-remove { padding: 3px 8px; background: #da3633; border: 1px solid #da3633; border-radius: 4px; color: #fff; cursor: pointer; font-size: 11px; font-weight: 600; }
  .btn-remove:hover { background: #f85149; }
  .skip-add-bar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
  .skip-add-bar input, .skip-add-bar select { padding: 8px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 13px; }
  .skip-add-bar input { flex: 1; }
  .skip-add-bar input:focus { outline: none; border-color: #58a6ff; }
  .btn-add-skip { padding: 8px 14px; background: #da3633; border: 1px solid #da3633; border-radius: 6px; color: #fff; cursor: pointer; font-size: 13px; font-weight: 600; white-space: nowrap; }
  .btn-add-skip:hover { background: #f85149; }
  .filter-bar { display: flex; gap: 8px; margin-bottom: 12px; align-items: center; }
  .filter-bar input { flex: 1; padding: 8px 12px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 14px; }
  .filter-bar input:focus { outline: none; border-color: #58a6ff; }
  .filter-bar select { padding: 8px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 13px; }
  .filter-bar .count { font-size: 12px; color: #8b949e; white-space: nowrap; }
  .stage-sel { padding: 2px 4px; background: #0d1117; border: 1px solid #30363d; border-radius: 4px; color: #c9d1d9; font-size: 11px; }
  .empty { padding: 20px; text-align: center; color: #8b949e; }
  .toast { position: fixed; bottom: 20px; right: 20px; background: #238636; color: #fff; padding: 12px 20px; border-radius: 8px; font-size: 14px; display: none; z-index: 100; }
  .toast.error { background: #f85149; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Job Search Dashboard</h1>
    <div class="sub" id="subtitle">Loading...</div>
  </div>
  <div class="controls">
    <div class="timer" id="timer">Refreshing in 30s</div>
    <button onclick="refresh()">Refresh Now</button>
  </div>
</div>

<div class="countdown" id="countdown"></div>
<div class="stats" id="stats"></div>
<div class="agents-bar" id="agents"></div>

<div class="add-bar">
  <input type="text" id="add-url" placeholder="Paste job URL to add..." />
  <button class="btn-add-queue" onclick="addJob('queue')">Add to Queue</button>
  <button class="btn-add-applied" onclick="addJob('applied')">Mark Applied</button>
</div>

<div class="tabs" id="tabs"></div>
<div class="panel active" id="p-pending"></div>
<div class="panel" id="p-manual"></div>
<div class="panel" id="p-applied"></div>
<div class="panel" id="p-skip"></div>

<div class="toast" id="toast"></div>

<script>
let D = null;
let cd = 30;
let activeTab = 'pending';
let searchQ = '';
let stageFilter = 'all';
let pendingSort = 'score';
let pendingTitleFilter = 'all';

async function refresh() {
  try {
    const r = await fetch('/api/data');
    D = await r.json();
    render();
    cd = 30;
  } catch(e) { toast('Failed to refresh: ' + e.message, 1); }
}

function render() {
  if (!D) return;

  document.getElementById('subtitle').textContent =
    'Howard Cheng | Auto-refresh 30s';

  // Countdown
  const urg = D.offer_days <= 7 ? 'CRITICAL' : D.offer_days <= 14 ? 'URGENT' : 'TIME-SENSITIVE';
  document.getElementById('countdown').innerHTML = `
    <div>
      <div class="label">${urg} — Need Offer for H-1B</div>
      <div class="detail">Must have offer by Mar 6 to start H-1B process</div>
    </div>
    <div style="text-align:center">
      <div class="days">${D.offer_days}</div>
      <div class="label">days to offer deadline</div>
    </div>
    <div style="text-align:right">
      <div style="color:#d29922;font-size:20px;font-weight:600">${D.h1b_days}d</div>
      <div class="label">H-1B reg deadline (Mar 19)</div>
    </div>`;

  // Stats
  const p = D.pipeline;
  const interviews = (D.applied || []).filter(j =>
    ['Phone Screen','Technical Interview','Take Home','Onsite/Final'].includes(j.stage)
  ).length;
  document.getElementById('stats').innerHTML = `
    <div class="stat"><div class="value v-yellow">${D.pending.length}</div><div class="label">Queue</div></div>
    <div class="stat"><div class="value v-green">${D.applied_count}</div><div class="label">Applied</div></div>
    <div class="stat"><div class="value v-purple">${interviews}</div><div class="label">Moved Forward</div></div>
    <div class="stat"><div class="value ${(p['Offer']||0)>0?'v-green':''}">${p['Offer']||0}</div><div class="label">Offers</div></div>
    <div class="stat"><div class="value v-red">${p['Rejected']||0}</div><div class="label">Rejected</div></div>`;

  // Agents
  document.getElementById('agents').innerHTML = '<span class="lbl">Agents:</span>' +
    D.agents.map(a => `<span><span class="dot ${a.status}"></span>${h(a.name)}${a.errors>0?' <span style="color:#f85149">('+a.errors+' err)</span>':''}</span>`).join('');

  // Tabs
  document.getElementById('tabs').innerHTML = `
    <div class="tab ${activeTab==='pending'?'active':''}" onclick="tab('pending')">Pending Queue (${D.pending.length})</div>
    <div class="tab ${activeTab==='manual'?'active':''}" onclick="tab('manual')">Manual Apply (${D.manual_apply.length})</div>
    <div class="tab ${activeTab==='applied'?'active':''}" onclick="tab('applied')">Applied (${D.applied_count})</div>
    <div class="tab ${activeTab==='skip'?'active':''}" onclick="tab('skip')">Skip List (${D.skip_list.length})</div>`;

  renderPending();
  renderManual();
  renderApplied();
  renderSkip();
}

function renderPending() {
  const el = document.getElementById('p-pending');
  let jobs = [...(D.pending || [])];
  const allTitles = [...new Set(jobs.map(j => j.title).filter(Boolean))].sort();
  if (pendingTitleFilter !== 'all') {
    jobs = jobs.filter(j => j.title === pendingTitleFilter);
  }
  if (pendingSort === 'company') {
    jobs.sort((a, b) => (a.company || '').localeCompare(b.company || ''));
  } else if (pendingSort === 'location') {
    jobs.sort((a, b) => (a.location || '').localeCompare(b.location || ''));
  } else {
    jobs.sort((a, b) => (b.score || 0) - (a.score || 0));
  }
  const filteredNote = pendingTitleFilter !== 'all' ? ` of ${D.pending.length}` : '';
  el.innerHTML = `
    <div class="filter-bar" style="display:flex;gap:8px;align-items:center;padding:8px 0;flex-wrap:wrap">
      <select onchange="pendingSort=this.value;renderPending()" style="padding:4px 8px;border-radius:4px;border:1px solid #444;background:#222;color:#e0e0e0">
        <option value="score" ${pendingSort==='score'?'selected':''}>Sort: Score ↓</option>
        <option value="company" ${pendingSort==='company'?'selected':''}>Sort: Company A→Z</option>
        <option value="location" ${pendingSort==='location'?'selected':''}>Sort: Location A→Z</option>
      </select>
      <select onchange="pendingTitleFilter=this.value;renderPending()" style="padding:4px 8px;border-radius:4px;border:1px solid #444;background:#222;color:#e0e0e0;max-width:300px">
        <option value="all" ${pendingTitleFilter==='all'?'selected':''}>All Titles</option>
        ${allTitles.map(t => `<option value="${h(t)}" ${pendingTitleFilter===t?'selected':''}>${h(t)}</option>`).join('')}
      </select>
      <span style="color:#888;font-size:13px">${jobs.length}${filteredNote} jobs</span>
    </div>
    ${jobs.length === 0 ? '<div class="empty">No matching jobs</div>' : `<table>
    <tr><th>Score</th><th>Company</th><th>Title</th><th>Location</th><th>H-1B</th><th>Link</th><th></th></tr>
    ${jobs.map(j => `<tr>
      <td class="score">${j.score}</td>
      <td>${h(j.company)}</td>
      <td>${h(j.title)}</td>
      <td>${h(j.location)}</td>
      <td>${h(j.h1b||'').substring(0,20)}</td>
      <td class="url-cell"><a href="${h(j.url)}" target="_blank">Open</a></td>
      <td style="white-space:nowrap"><button class="btn-mark" data-url="${h(j.url)}" data-company="${h(j.company)}" data-title="${h(j.title)}" onclick="markBtnPending(this)">Mark Applied</button><button class="btn-delete" data-url="${h(j.url)}" data-company="${h(j.company)}" data-title="${h(j.title)}" onclick="deleteBtnPending(this)">Delete</button></td>
    </tr>`).join('')}
    </table>`}`;
}

async function markBtnPending(btn) {
  const url = btn.dataset.url, company = btn.dataset.company, title = btn.dataset.title;
  if (!confirm(`Mark "${company} — ${title}" as applied?`)) return;
  btn.disabled = true; btn.textContent = '...';
  try {
    const r = await fetch('/api/mark-applied', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, company, title})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error || 'Failed', 1); btn.disabled = false; btn.textContent = 'Mark Applied'; }
  } catch(e) { toast('Error: ' + e.message, 1); btn.disabled = false; btn.textContent = 'Mark Applied'; }
}

async function deleteBtnPending(btn) {
  const url = btn.dataset.url, company = btn.dataset.company, title = btn.dataset.title;
  if (!confirm(`DELETE "${company} — ${title}"?\\n\\nThis removes it from the queue and permanently blocks re-adding.`)) return;
  btn.disabled = true; btn.textContent = '...';
  try {
    const r = await fetch('/api/delete-job', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, company, title})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error || 'Failed', 1); btn.disabled = false; btn.textContent = 'Delete'; }
  } catch(e) { toast('Error: ' + e.message, 1); btn.disabled = false; btn.textContent = 'Delete'; }
}

function renderManual() {
  const el = document.getElementById('p-manual');
  const jobs = D.manual_apply;
  if (!jobs.length) { el.innerHTML = '<div class="empty">No manual apply jobs</div>'; return; }
  el.innerHTML = `<table>
    <tr><th>Score</th><th>Company</th><th>Title</th><th>Location</th><th>Link</th><th></th></tr>
    ${jobs.map((j,i) => `<tr>
      <td class="score">${j.score||'-'}</td>
      <td>${h(j.company)}</td>
      <td>${h(j.title)}</td>
      <td>${h(j.location)}</td>
      <td class="url-cell"><a href="${h(j.url)}" target="_blank">Open</a></td>
      <td style="white-space:nowrap"><button class="btn-mark" data-i="${i}" data-t="manual" onclick="markBtn(this)">Mark Applied</button><button class="btn-delete" data-i="${i}" data-t="manual" onclick="deleteBtn(this)">Delete</button></td>
    </tr>`).join('')}
  </table>`;
}

function renderApplied() {
  const el = document.getElementById('p-applied');
  let jobs = D.applied;
  const activeEl = document.activeElement;
  const restoreSearchFocus = activeEl && activeEl.id === 'applied-search';
  const caretStart = restoreSearchFocus ? activeEl.selectionStart : null;
  const caretEnd = restoreSearchFocus ? activeEl.selectionEnd : null;

  if (searchQ) {
    const s = searchQ.toLowerCase();
    jobs = jobs.filter(j => j.company.toLowerCase().includes(s) || j.title.toLowerCase().includes(s));
  }
  if (stageFilter !== 'all') {
    jobs = jobs.filter(j => j.stage === stageFilter);
  }

  el.innerHTML = `
    <div class="filter-bar">
      <input type="text" id="applied-search" placeholder="Search company or title..." value="${h(searchQ)}" oninput="searchQ=this.value;renderApplied()" />
      <select onchange="stageFilter=this.value;renderApplied()">
        <option value="all" ${stageFilter==='all'?'selected':''}>All Stages</option>
        <option value="Applied" ${stageFilter==='Applied'?'selected':''}>Applied</option>
        <option value="Phone Screen" ${stageFilter==='Phone Screen'?'selected':''}>Phone Screen</option>
        <option value="Technical Interview" ${stageFilter==='Technical Interview'?'selected':''}>Technical Interview</option>
        <option value="Take Home" ${stageFilter==='Take Home'?'selected':''}>Take Home</option>
        <option value="Onsite/Final" ${stageFilter==='Onsite/Final'?'selected':''}>Onsite/Final</option>
        <option value="Offer" ${stageFilter==='Offer'?'selected':''}>Offer</option>
        <option value="Rejected" ${stageFilter==='Rejected'?'selected':''}>Rejected</option>
      </select>
      <span class="count">${jobs.length} jobs</span>
    </div>
    ${jobs.length === 0 ? '<div class="empty">No matching jobs</div>' : `<table>
    <tr><th>Company</th><th>Title</th><th>Date</th><th>Stage</th><th>Link</th><th>Update Stage</th></tr>
    ${jobs.map((j,i) => `<tr>
      <td>${h(j.company)}</td>
      <td>${h(j.title)}</td>
      <td>${h(j.date)}</td>
      <td><span class="badge ${bc(j.stage)}">${h(j.stage)}</span></td>
      <td class="url-cell"><a href="${h(j.url)}" target="_blank">Open</a></td>
      <td style="white-space:nowrap">
        <select class="stage-sel" id="ss-${i}">
          ${['Applied','Phone Screen','Technical Interview','Take Home','Onsite/Final','Offer','Rejected'].map(s =>
            '<option value="'+s+'" '+(j.stage===s?'selected':'')+'>'+s+'</option>'
          ).join('')}
        </select>
        <button class="btn-update" data-i="${i}" onclick="updateBtn(this)">Update</button>
      </td>
    </tr>`).join('')}
    </table>`}`;
  if (restoreSearchFocus) {
    const input = document.getElementById('applied-search');
    if (input) {
      input.focus();
      if (caretStart !== null && caretEnd !== null) {
        input.setSelectionRange(caretStart, caretEnd);
      }
    }
  }
}

function bc(stage) {
  const m = {'Applied':'b-applied','Phone Screen':'b-phone','Technical Interview':'b-interview',
    'Take Home':'b-takehome','Onsite/Final':'b-interview',
    'Offer':'b-offer','Rejected':'b-rejected'};
  return m[stage] || 'b-applied';
}

function tab(name) {
  activeTab = name;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(t => t.classList.remove('active'));
  const idx = {pending:0, manual:1, applied:2, skip:3}[name];
  document.querySelectorAll('.tab')[idx].classList.add('active');
  document.getElementById('p-' + name).classList.add('active');
}

async function markBtn(btn) {
  const type = btn.dataset.t;
  const idx = parseInt(btn.dataset.i);
  const job = type === 'pending' ? D.pending[idx] : D.manual_apply[idx];
  if (!job) return;
  if (!confirm('Mark "' + job.company + ' \u2014 ' + job.title + '" as applied?')) return;
  try {
    const r = await fetch('/api/mark-applied', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: job.url, company: job.company, title: job.title})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error || 'Failed', 1); }
  } catch(e) { toast('Error: ' + e.message, 1); }
}

async function deleteBtn(btn) {
  const type = btn.dataset.t;
  const idx = parseInt(btn.dataset.i);
  const job = type === 'pending' ? D.pending[idx] : D.manual_apply[idx];
  if (!job) return;
  if (!confirm('DELETE "' + job.company + ' \u2014 ' + job.title + '"?\n\nThis removes it from the queue and permanently blocks it from being re-added.')) return;
  try {
    const r = await fetch('/api/delete-job', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: job.url, company: job.company, title: job.title})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error || 'Failed', 1); }
  } catch(e) { toast('Error: ' + e.message, 1); }
}

async function updateBtn(btn) {
  const idx = parseInt(btn.dataset.i);
  const sel = document.getElementById('ss-' + idx);
  if (!sel) return;
  // Get the filtered list to find the right job
  let jobs = D.applied;
  if (searchQ) {
    const s = searchQ.toLowerCase();
    jobs = jobs.filter(j => j.company.toLowerCase().includes(s) || j.title.toLowerCase().includes(s));
  }
  if (stageFilter !== 'all') {
    jobs = jobs.filter(j => j.stage === stageFilter);
  }
  const job = jobs[idx];
  if (!job) return;
  // Use URL as search term for precision (unique per job)
  const searchKey = job.url || job.company;
  try {
    const r = await fetch('/api/stage', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({search: searchKey, stage: sel.value, url: job.url, company: job.company, title: job.title})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error, 1); }
  } catch(e) { toast('Error: ' + e.message, 1); }
}

async function addJob(dest) {
  const input = document.getElementById('add-url');
  const url = input.value.trim();
  if (!url) { toast('Paste a URL first', 1); return; }
  if (!url.startsWith('http')) { toast('URL must start with http', 1); return; }
  const action = dest === 'applied' ? 'Mark as applied' : 'Add to queue';
  if (!confirm(action + '?\n' + url)) return;
  try {
    const r = await fetch('/api/add-job', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url: url, destination: dest})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); input.value = ''; refresh(); }
    else { toast(res.error || 'Failed', 1); }
  } catch(e) { toast('Error: ' + e.message, 1); }
}

function renderSkip() {
  const el = document.getElementById('p-skip');
  const list = D.skip_list || [];
  const catBadge = c => ({csp:'b-csp',limit:'b-limit',technical:'b-technical',captcha:'b-captcha'}[c]||'b-manual');
  el.innerHTML = `
    <div class="skip-add-bar">
      <input type="text" id="skip-name" placeholder="Company name..." />
      <input type="text" id="skip-reason" placeholder="Reason (e.g. CSP blocks automation)" style="flex:2" />
      <select id="skip-cat">
        <option value="csp">CSP Block</option>
        <option value="limit">App Limit</option>
        <option value="technical">Technical</option>
        <option value="captcha">CAPTCHA</option>
        <option value="manual">Other</option>
      </select>
      <button class="btn-add-skip" onclick="addSkip()">Add to Skip List</button>
    </div>
    ${list.length === 0 ? '<div class="empty">No companies in skip list</div>' : `<table>
    <tr><th>Company</th><th>Category</th><th>Reason</th><th></th></tr>
    ${list.map(c => `<tr>
      <td><strong>${h(c.name)}</strong></td>
      <td><span class="badge ${catBadge(c.category)}">${h(c.category||'manual')}</span></td>
      <td>${h(c.reason)}</td>
      <td><button class="btn-remove" onclick="removeSkip('${h(c.name).replace(/'/g,"\\'")}')">Remove</button></td>
    </tr>`).join('')}
    </table>`}`;
}

async function addSkip() {
  const name = document.getElementById('skip-name').value.trim();
  const reason = document.getElementById('skip-reason').value.trim();
  const category = document.getElementById('skip-cat').value;
  if (!name) { toast('Enter a company name', 1); return; }
  try {
    const r = await fetch('/api/skip-list/add', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, reason, category})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error, 1); }
  } catch(e) { toast('Error: ' + e.message, 1); }
}

async function removeSkip(name) {
  if (!confirm('Remove "' + name + '" from skip list?')) return;
  try {
    const r = await fetch('/api/skip-list/remove', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name})
    });
    const res = await r.json();
    if (res.ok) { toast(res.message); refresh(); }
    else { toast(res.error, 1); }
  } catch(e) { toast('Error: ' + e.message, 1); }
}

function toast(msg, err) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (err ? ' error' : '');
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3000);
}

function h(s) { return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

refresh();
setInterval(() => {
  cd--;
  document.getElementById('timer').textContent = 'Refreshing in ' + cd + 's';
  if (cd <= 0) { refresh(); cd = 30; }
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
        if self.path == "/api/mark-applied":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = mark_as_applied(body.get("url", ""), body.get("company", ""), body.get("title", ""))
            self.send_json(result)

        elif self.path == "/api/stage":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = update_stage(
                body.get("search", ""),
                body.get("stage", ""),
                body.get("url", ""),
                body.get("company", ""),
                body.get("title", ""),
            )
            self.send_json(result)

        elif self.path == "/api/add-job":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = add_job(body.get("url", ""), body.get("destination", "queue"))
            self.send_json(result)

        elif self.path == "/api/delete-job":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = delete_from_queue(body.get("url", ""), body.get("company", ""), body.get("title", ""))
            self.send_json(result)

        elif self.path == "/api/skip-list/add":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = add_to_skip_list(body.get("name", ""), body.get("reason", ""), body.get("category", "manual"))
            self.send_json(result)

        elif self.path == "/api/skip-list/remove":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            result = remove_from_skip_list(body.get("name", ""))
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
    print(f"\n  Job Search Dashboard v3 running at http://localhost:{PORT}")
    print(f"  Workspace: {WORKSPACE}")
    print(f"  Press Ctrl+C to stop\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard.")
        server.server_close()
