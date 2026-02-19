#!/usr/bin/env python3
"""
Defer a job to mandatory manual apply flow.

This script performs an atomic queue + dedup + manual-list update:
1) Remove job from queue (pending/in-progress sections)
2) Mark dedup status as MANUAL_REQUIRED
3) Append checklist entry to manual-apply-required.md
4) Append URL to manual-dedup.md

Usage:
  python3 scripts/defer-manual-apply.py "<url>" "<company>" "<title>" "<ats>" --reason "<text>"
"""
import argparse
import fcntl
import os
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
QUEUE_PATH = os.path.join(WORKSPACE, "job-queue.md")
DEDUP_PATH = os.path.join(WORKSPACE, "dedup-index.md")
LOCK_PATH = os.path.join(WORKSPACE, ".queue.lock")
MANUAL_REQUIRED_PATH = os.path.join(WORKSPACE, "manual-apply-required.md")
MANUAL_DEDUP_PATH = os.path.join(WORKSPACE, "manual-dedup.md")


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def url_variants(url: str):
    base = normalize_url(url)
    variants = {base, f"{base}/"}
    if base.endswith("/application"):
        variants.add(base[: -len("/application")])
    else:
        variants.add(f"{base}/application")
    return variants


def remove_from_queue(url: str) -> bool:
    if not os.path.exists(QUEUE_PATH):
        return False

    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    variants = url_variants(url)
    removed = False
    i = 0
    while i < len(lines):
        if lines[i].startswith("### "):
            block_start = i
            block_end = i + 1
            while block_end < len(lines) and not lines[block_end].startswith("### ") and not lines[block_end].startswith("## "):
                block_end += 1
            block = "\n".join(lines[block_start:block_end])
            if any(v in block for v in variants):
                del lines[block_start:block_end]
                removed = True
                continue
            i = block_end
        else:
            i += 1

    if removed:
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    return removed


def upsert_dedup(url: str, company: str, title: str):
    today = datetime.now().strftime("%Y-%m-%d")
    variants = url_variants(url)
    normalized = normalize_url(url).replace("/application", "")
    new_line = f"{normalize_url(url)} | {company} | {title} | MANUAL_REQUIRED | {today}\n"

    dedup_lines = []
    if os.path.exists(DEDUP_PATH):
        with open(DEDUP_PATH, "r", encoding="utf-8") as f:
            dedup_lines = f.readlines()

    found = False
    out_lines = []
    seen_norm = set()

    for raw in dedup_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            out_lines.append(raw)
            continue

        parts = [p.strip() for p in raw.strip().split("|")]
        if len(parts) < 4:
            out_lines.append(raw)
            continue

        row_url = parts[0].rstrip("/")
        row_norm = row_url.replace("/application", "")

        if row_norm in seen_norm:
            continue

        if row_url in {v.rstrip("/") for v in variants}:
            found = True
            out_lines.append(new_line)
            seen_norm.add(normalized)
        else:
            out_lines.append(raw if raw.endswith("\n") else raw + "\n")
            seen_norm.add(row_norm)

    if not found and normalized not in seen_norm:
        out_lines.append(new_line)

    with open(DEDUP_PATH, "w", encoding="utf-8") as f:
        f.writelines(out_lines)


def append_manual_required(url: str, company: str, title: str, ats: str, reason: str):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")
    entry = (
        f"- [ ] **{company}** — {title} | ATS: {ats} | Deferred: {date} {time} | Reason: {reason} | URL: {normalize_url(url)}\n"
    )

    if not os.path.exists(MANUAL_REQUIRED_PATH):
        with open(MANUAL_REQUIRED_PATH, "w", encoding="utf-8") as f:
            f.write("# Mandatory Manual Apply List\n\n")
            f.write("Jobs deferred by automation and must be applied manually.\n\n")
            f.write("## Deferred Jobs\n")

    with open(MANUAL_REQUIRED_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if normalize_url(url) in content:
        return False

    with open(MANUAL_REQUIRED_PATH, "a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            f.write("\n")
        f.write(entry)
    return True


def append_manual_dedup(url: str, company: str, title: str):
    line = f"- {normalize_url(url)} | {company} | {title}\n"

    if not os.path.exists(MANUAL_DEDUP_PATH):
        with open(MANUAL_DEDUP_PATH, "w", encoding="utf-8") as f:
            f.write("# Manual Dedup List\n")
            f.write("# URLs added manually to prevent duplicate applications\n")
            f.write("# Format: - URL | Company | Title\n\n")

    with open(MANUAL_DEDUP_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if normalize_url(url) in content:
        return False

    with open(MANUAL_DEDUP_PATH, "a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            f.write("\n")
        f.write(line)
    return True


def main():
    parser = argparse.ArgumentParser(description="Defer job to mandatory manual apply list.")
    parser.add_argument("url")
    parser.add_argument("company")
    parser.add_argument("title")
    parser.add_argument("ats")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    with open(LOCK_PATH, "w", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            removed = remove_from_queue(args.url)
            upsert_dedup(args.url, args.company, args.title)
            added_required = append_manual_required(args.url, args.company, args.title, args.ats, args.reason)
            added_dedup = append_manual_dedup(args.url, args.company, args.title)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)

    print(f"QUEUE_REMOVED: {'yes' if removed else 'no'}")
    print("DEDUP_STATUS: MANUAL_REQUIRED")
    print(f"MANUAL_REQUIRED_ADDED: {'yes' if added_required else 'no'}")
    print(f"MANUAL_DEDUP_ADDED: {'yes' if added_dedup else 'no'}")
    print("DONE")


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Defer a job to mandatory manual apply flow.

This script performs an atomic queue + dedup + manual-list update:
1) Remove job from queue (pending/in-progress sections)
2) Mark dedup status as MANUAL_REQUIRED
3) Append checklist entry to manual-apply-required.md
4) Append URL to manual-dedup.md

Usage:
  python3 scripts/defer-manual-apply.py "<url>" "<company>" "<title>" "<ats>" --reason "<text>"
"""
import argparse
import fcntl
import os
import re
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
QUEUE_PATH = os.path.join(WORKSPACE, "job-queue.md")
DEDUP_PATH = os.path.join(WORKSPACE, "dedup-index.md")
LOCK_PATH = os.path.join(WORKSPACE, ".queue.lock")
MANUAL_REQUIRED_PATH = os.path.join(WORKSPACE, "manual-apply-required.md")
MANUAL_DEDUP_PATH = os.path.join(WORKSPACE, "manual-dedup.md")


def normalize_url(url: str) -> str:
    return url.strip().rstrip("/")


def url_variants(url: str):
    base = normalize_url(url)
    variants = {base, f"{base}/"}
    if base.endswith("/application"):
        variants.add(base[: -len("/application")])
    else:
        variants.add(f"{base}/application")
    return variants


def remove_from_queue(url: str) -> bool:
    if not os.path.exists(QUEUE_PATH):
        return False

    with open(QUEUE_PATH, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")

    variants = url_variants(url)
    removed = False
    i = 0
    while i < len(lines):
        if lines[i].startswith("### "):
            block_start = i
            block_end = i + 1
            while block_end < len(lines) and not lines[block_end].startswith("### ") and not lines[block_end].startswith("## "):
                block_end += 1
            block = "\n".join(lines[block_start:block_end])
            if any(v in block for v in variants):
                del lines[block_start:block_end]
                removed = True
                continue
            i = block_end
        else:
            i += 1

    if removed:
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    return removed


def upsert_dedup(url: str, company: str, title: str):
    today = datetime.now().strftime("%Y-%m-%d")
    variants = url_variants(url)
    normalized = normalize_url(url).replace("/application", "")
    new_line = f"{normalize_url(url)} | {company} | {title} | MANUAL_REQUIRED | {today}\n"

    dedup_lines = []
    if os.path.exists(DEDUP_PATH):
        with open(DEDUP_PATH, "r", encoding="utf-8") as f:
            dedup_lines = f.readlines()

    found = False
    out_lines = []
    seen_norm = set()

    for raw in dedup_lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            out_lines.append(raw)
            continue

        parts = [p.strip() for p in raw.strip().split("|")]
        if len(parts) < 4:
            out_lines.append(raw)
            continue

        row_url = parts[0].rstrip("/")
        row_norm = row_url.replace("/application", "")

        if row_norm in seen_norm:
            continue

        if row_url in {v.rstrip("/") for v in variants}:
            found = True
            out_lines.append(new_line)
            seen_norm.add(normalized)
        else:
            out_lines.append(raw if raw.endswith("\n") else raw + "\n")
            seen_norm.add(row_norm)

    if not found and normalized not in seen_norm:
        out_lines.append(new_line)

    with open(DEDUP_PATH, "w", encoding="utf-8") as f:
        f.writelines(out_lines)


def append_manual_required(url: str, company: str, title: str, ats: str, reason: str):
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")
    entry = (
        f"- [ ] **{company}** — {title} | ATS: {ats} | Deferred: {date} {time} | Reason: {reason} | URL: {normalize_url(url)}\n"
    )

    if not os.path.exists(MANUAL_REQUIRED_PATH):
        with open(MANUAL_REQUIRED_PATH, "w", encoding="utf-8") as f:
            f.write("# Mandatory Manual Apply List\n\n")
            f.write("Jobs deferred by automation and must be applied manually.\n\n")
            f.write("## Deferred Jobs\n")

    with open(MANUAL_REQUIRED_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if normalize_url(url) in content:
        return False

    with open(MANUAL_REQUIRED_PATH, "a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            f.write("\n")
        f.write(entry)
    return True


def append_manual_dedup(url: str, company: str, title: str):
    line = f"- {normalize_url(url)} | {company} | {title}\n"

    if not os.path.exists(MANUAL_DEDUP_PATH):
        with open(MANUAL_DEDUP_PATH, "w", encoding="utf-8") as f:
            f.write("# Manual Dedup List\n")
            f.write("# URLs added manually to prevent duplicate applications\n")
            f.write("# Format: - URL | Company | Title\n\n")

    with open(MANUAL_DEDUP_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if normalize_url(url) in content:
        return False

    with open(MANUAL_DEDUP_PATH, "a", encoding="utf-8") as f:
        if not content.endswith("\n"):
            f.write("\n")
        f.write(line)
    return True


def main():
    parser = argparse.ArgumentParser(description="Defer job to mandatory manual apply list.")
    parser.add_argument("url")
    parser.add_argument("company")
    parser.add_argument("title")
    parser.add_argument("ats")
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()

    with open(LOCK_PATH, "w", encoding="utf-8") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            removed = remove_from_queue(args.url)
            upsert_dedup(args.url, args.company, args.title)
            added_required = append_manual_required(args.url, args.company, args.title, args.ats, args.reason)
            added_dedup = append_manual_dedup(args.url, args.company, args.title)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)

    print(f"QUEUE_REMOVED: {'yes' if removed else 'no'}")
    print("DEDUP_STATUS: MANUAL_REQUIRED")
    print(f"MANUAL_REQUIRED_ADDED: {'yes' if added_required else 'no'}")
    print(f"MANUAL_DEDUP_ADDED: {'yes' if added_dedup else 'no'}")
    print("DONE")


if __name__ == "__main__":
    main()
