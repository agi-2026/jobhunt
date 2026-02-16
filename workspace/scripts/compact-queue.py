#!/usr/bin/env python3
"""
Compact job-queue.md:
1. Parse ALL entries from the file
2. Check each entry's Status field (COMPLETED/SKIPPED/PENDING)
3. Archive COMPLETED and SKIPPED entries to job-queue-archive.md
4. Keep only genuinely PENDING + IN PROGRESS entries
5. Preserve header, DO NOT AUTO-APPLY section, format comments
Runs every 30 min via launchd.
"""
import re
import os
from datetime import datetime

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
QUEUE_FILE = os.path.join(WORKSPACE, "job-queue.md")
ARCHIVE_FILE = os.path.join(WORKSPACE, "job-queue-archive.md")
LOG_FILE = "/tmp/openclaw/compaction.log"

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] {msg}\n")

def classify_entry(entry_text):
    """Determine if an entry is COMPLETED, SKIPPED, or PENDING based on its Status field."""
    # Check Status field
    status_match = re.search(r"\*\*Status:\*\*\s*(\w+)", entry_text)
    if status_match:
        status = status_match.group(1).upper()
        if status == "COMPLETED":
            return "completed"
        elif status == "SKIPPED":
            return "skipped"
        elif status == "PENDING":
            return "pending"

    # Check for applied/reason markers (entries without explicit Status field)
    if re.search(r"\*\*Applied:\*\*", entry_text):
        return "completed"
    if re.search(r"\*\*Reason:\*\*", entry_text):
        return "skipped"

    # Default to pending
    return "pending"

def main():
    if not os.path.exists(QUEUE_FILE):
        log("ERROR: job-queue.md not found")
        return

    with open(QUEUE_FILE, "r") as f:
        content = f.read()

    original_size = len(content)

    # Extract the preamble (everything before the first ### entry)
    # This includes: # Job Priority Queue, ## Queue Stats, ## DO NOT AUTO-APPLY, ## IN PROGRESS, ## PENDING header, etc.
    lines = content.split("\n")

    preamble_lines = []
    entry_start_idx = None
    for i, line in enumerate(lines):
        if line.startswith("### ["):
            entry_start_idx = i
            break
        preamble_lines.append(line)

    if entry_start_idx is None:
        log("No entries found in queue. Nothing to compact.")
        return

    # Extract all entries (### [...] blocks)
    entries = []
    current_entry_lines = []
    for i in range(entry_start_idx, len(lines)):
        line = lines[i]
        if line.startswith("### ["):
            if current_entry_lines:
                entries.append("\n".join(current_entry_lines))
            current_entry_lines = [line]
        elif line.startswith("## "):
            # Section header between entries (e.g., ## COMPLETED, ## SKIPPED, ## COMPLETED (last 24h))
            # Save current entry if any
            if current_entry_lines:
                entries.append("\n".join(current_entry_lines))
                current_entry_lines = []
            # Skip section headers — we'll reorganize ourselves
        elif line.startswith("<!-- ") and not current_entry_lines:
            # HTML comment not part of an entry — skip
            pass
        else:
            if current_entry_lines:
                current_entry_lines.append(line)

    if current_entry_lines:
        entries.append("\n".join(current_entry_lines))

    # Classify each entry
    pending = []
    completed = []
    skipped = []

    for entry in entries:
        status = classify_entry(entry)
        if status == "completed":
            completed.append(entry)
        elif status == "skipped":
            skipped.append(entry)
        else:
            pending.append(entry)

    to_archive = completed + skipped
    if not to_archive:
        log(f"No entries to archive. {len(pending)} pending entries. Queue at {original_size} bytes.")
        return

    # Append to archive
    archive_text = f"\n\n## Archived {datetime.now().strftime('%Y-%m-%d %H:%M CT')}\n\n"
    if completed:
        archive_text += f"### COMPLETED ({len(completed)} entries)\n\n"
        for entry in completed:
            archive_text += entry.strip() + "\n\n"
    if skipped:
        archive_text += f"### SKIPPED ({len(skipped)} entries)\n\n"
        for entry in skipped:
            archive_text += entry.strip() + "\n\n"

    with open(ARCHIVE_FILE, "a") as f:
        f.write(archive_text)

    # Rebuild preamble — extract header, scoring formula, and DO NOT AUTO-APPLY
    # Find key section starts in the preamble
    header_lines = []
    scoring_lines = []
    do_not_apply_lines = []
    current_preamble_section = "header"

    for line in preamble_lines:
        stripped = line.strip()
        if stripped.startswith("## Scoring Formula"):
            current_preamble_section = "scoring"
            scoring_lines.append(line)
        elif stripped.startswith("## ⛔ DO NOT AUTO-APPLY"):
            current_preamble_section = "do_not_apply"
            do_not_apply_lines.append(line)
        elif stripped.startswith("## IN PROGRESS") or stripped.startswith("## COMPLETED") or stripped.startswith("## PENDING") or stripped.startswith("## SKIPPED"):
            current_preamble_section = "other"
        elif current_preamble_section == "header":
            header_lines.append(line)
        elif current_preamble_section == "scoring":
            scoring_lines.append(line)
        elif current_preamble_section == "do_not_apply":
            do_not_apply_lines.append(line)

    # Build the new queue
    new_queue_parts = []

    # Header with updated stats
    new_queue_parts.append("# Job Priority Queue")
    new_queue_parts.append("## Queue Stats")
    new_queue_parts.append(f"- Pending: {len(pending)} | In Progress: 0 | Last compaction: {datetime.now().strftime('%Y-%m-%d %H:%M CT')}")
    # Preserve the Last Search and Last Application Cycle lines from original header
    for line in header_lines:
        if "Last Search:" in line or "Last Application Cycle:" in line:
            new_queue_parts.append(line)
    new_queue_parts.append("")

    # Scoring Formula section
    if scoring_lines:
        new_queue_parts.append("\n".join(scoring_lines))
    new_queue_parts.append("")

    # DO NOT AUTO-APPLY section
    if do_not_apply_lines:
        new_queue_parts.append("\n".join(do_not_apply_lines))
    new_queue_parts.append("")

    # IN PROGRESS
    new_queue_parts.append("## IN PROGRESS")
    new_queue_parts.append("")
    new_queue_parts.append("(none)")
    new_queue_parts.append("")

    # PENDING — only genuinely pending entries
    new_queue_parts.append("## PENDING (sorted by priority score, highest first)")
    new_queue_parts.append("")
    for entry in pending:
        # Strip trailing whitespace and HTML comments
        clean = re.sub(r"\n*<!--.*?-->\n*", "\n", entry).strip()
        new_queue_parts.append(clean)
        new_queue_parts.append("")

    new_content = "\n".join(new_queue_parts).strip() + "\n"

    with open(QUEUE_FILE, "w") as f:
        f.write(new_content)

    new_size = len(new_content)
    log(f"Compacted: archived {len(to_archive)} entries ({len(completed)} completed, {len(skipped)} skipped). "
        f"Queue: {original_size} → {new_size} bytes ({original_size - new_size} saved). "
        f"{len(pending)} pending entries remain.")

if __name__ == "__main__":
    main()