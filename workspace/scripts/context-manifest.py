#!/usr/bin/env python3
"""Metadata-first context index for orchestrator/subagent runs.

This script gives agents a cheap catalog view before reading full files.

Usage:
  python3 scripts/context-manifest.py build
  python3 scripts/context-manifest.py list --profile orchestrator --limit 20
  python3 scripts/context-manifest.py read lever_skill --section "Phase 2" --max-lines 180
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional


WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DEFAULT_MANIFEST_PATH = os.path.join(WORKSPACE, "config", "context-manifest.json")


CURATED_FILES: List[Dict[str, Any]] = [
    {
        "id": "orchestrator_mode_script",
        "path": "scripts/set-orchestrator-mode.py",
        "purpose": "Builds orchestrator runtime prompt templates and mode toggles.",
        "profiles": ["orchestrator"],
        "tags": ["orchestrator", "prompt-template"],
    },
    {
        "id": "dispatch_script",
        "path": "scripts/orchestrator-dispatch.py",
        "purpose": "Computes READY ATS and top-score candidates.",
        "profiles": ["orchestrator"],
        "tags": ["orchestrator", "dispatch", "queue"],
    },
    {
        "id": "batch_preflight_script",
        "path": "scripts/batch-preflight.py",
        "purpose": "Preflight validates queue URLs and removes dead jobs.",
        "profiles": ["orchestrator"],
        "tags": ["orchestrator", "preflight"],
    },
    {
        "id": "queue_summary_script",
        "path": "scripts/queue-summary.py",
        "purpose": "Returns top actionable jobs by ATS without loading queue markdown.",
        "profiles": ["orchestrator", "apply-common"],
        "tags": ["queue", "selection"],
    },
    {
        "id": "preflight_check_script",
        "path": "scripts/preflight-check.py",
        "purpose": "Single-URL liveness check for application targets.",
        "profiles": ["apply-common"],
        "tags": ["preflight", "ats"],
    },
    {
        "id": "subagent_lock_script",
        "path": "scripts/subagent-lock.py",
        "purpose": "Global apply lock check/lock/unlock.",
        "profiles": ["orchestrator", "apply-common"],
        "tags": ["locking", "concurrency"],
    },
    {
        "id": "log_orchestrator_cycle_script",
        "path": "scripts/log-orchestrator-cycle.py",
        "purpose": "Cycle status logging and freshness checks.",
        "profiles": ["orchestrator"],
        "tags": ["monitoring", "logging"],
    },
    {
        "id": "tool_menu_script",
        "path": "scripts/tool-menu.py",
        "purpose": "Canonical browser-tool action schema and invalid call examples.",
        "profiles": ["orchestrator", "apply-common"],
        "tags": ["tools", "schema", "guardrail"],
    },
    {
        "id": "ashby_skill",
        "path": "skills/apply-ashby/SKILL.md",
        "purpose": "Ashby single-job runbook and correction flow.",
        "profiles": ["apply-ashby"],
        "tags": ["skill", "ashby"],
    },
    {
        "id": "greenhouse_skill",
        "path": "skills/apply-greenhouse/SKILL.md",
        "purpose": "Greenhouse runbook including verification code flow.",
        "profiles": ["apply-greenhouse"],
        "tags": ["skill", "greenhouse"],
    },
    {
        "id": "lever_skill",
        "path": "skills/apply-lever/SKILL.md",
        "purpose": "Lever runbook including hCaptcha and upload checks.",
        "profiles": ["apply-lever"],
        "tags": ["skill", "lever"],
    },
    {
        "id": "ashby_form_filler",
        "path": "skills/apply-ashby/scripts/form-filler.js",
        "purpose": "Canonical Ashby form filler evaluate script.",
        "profiles": ["apply-ashby"],
        "tags": ["filler", "ashby", "js"],
    },
    {
        "id": "greenhouse_form_filler",
        "path": "skills/apply-greenhouse/scripts/form-filler.js",
        "purpose": "Canonical Greenhouse form filler evaluate script.",
        "profiles": ["apply-greenhouse"],
        "tags": ["filler", "greenhouse", "js"],
    },
    {
        "id": "lever_form_filler",
        "path": "skills/apply-lever/scripts/form-filler.js",
        "purpose": "Canonical Lever form filler evaluate script.",
        "profiles": ["apply-lever"],
        "tags": ["filler", "lever", "js"],
    },
    {
        "id": "ashby_custom_answers",
        "path": "skills/apply-ashby/scripts/fill-custom-answers.js",
        "purpose": "Ashby custom question injector script.",
        "profiles": ["apply-ashby"],
        "tags": ["custom-answers", "ashby", "js"],
    },
    {
        "id": "ashby_verify_upload",
        "path": "skills/apply-ashby/scripts/verify-upload.js",
        "purpose": "Ashby upload verification helper script.",
        "profiles": ["apply-ashby"],
        "tags": ["upload", "verify", "ashby", "js"],
    },
    {
        "id": "greenhouse_custom_answers",
        "path": "skills/apply-greenhouse/scripts/fill-custom-answers.js",
        "purpose": "Greenhouse custom question injector script.",
        "profiles": ["apply-greenhouse"],
        "tags": ["custom-answers", "greenhouse", "js"],
    },
    {
        "id": "greenhouse_verify_upload",
        "path": "skills/apply-greenhouse/scripts/verify-upload.js",
        "purpose": "Greenhouse upload verification helper script.",
        "profiles": ["apply-greenhouse"],
        "tags": ["upload", "verify", "greenhouse", "js"],
    },
    {
        "id": "lever_custom_answers",
        "path": "skills/apply-lever/scripts/fill-custom-answers.js",
        "purpose": "Lever custom question injector script.",
        "profiles": ["apply-lever"],
        "tags": ["custom-answers", "lever", "js"],
    },
    {
        "id": "lever_verify_upload",
        "path": "skills/apply-lever/scripts/verify-upload.js",
        "purpose": "Lever upload verification helper script.",
        "profiles": ["apply-lever"],
        "tags": ["upload", "verify", "lever", "js"],
    },
    {
        "id": "greenhouse_verify_code",
        "path": "scripts/greenhouse-verify-code.js",
        "purpose": "Atomic fill for Greenhouse email verification code inputs.",
        "profiles": ["apply-greenhouse"],
        "tags": ["verification", "greenhouse", "js"],
    },
    {
        "id": "lever_detect_hcaptcha",
        "path": "skills/apply-lever/scripts/detect-hcaptcha.js",
        "purpose": "Detect hCaptcha challenge in Lever flows.",
        "profiles": ["apply-lever"],
        "tags": ["captcha", "lever", "js"],
    },
    {
        "id": "lever_solve_hcaptcha_audio",
        "path": "scripts/solve-hcaptcha-audio.py",
        "purpose": "Solve hCaptcha via audio challenge + Whisper ASR. Run as exec: python3 scripts/solve-hcaptcha-audio.py. Exit 0 = prints digit answer to stdout. Exit 1 = failure.",
        "profiles": ["apply-lever"],
        "tags": ["captcha", "lever", "whisper", "audio"],
    },
    {
        "id": "mark_applied_script",
        "path": "scripts/mark-applied.py",
        "purpose": "Marks applied status in queue and tracker.",
        "profiles": ["apply-common"],
        "tags": ["tracking", "status"],
    },
    {
        "id": "answers_bank",
        "path": "config/answers-bank.md",
        "purpose": "Pre-written answers for common custom application questions (work auth, salary, essays, demographics).",
        "profiles": ["apply-ashby", "apply-greenhouse", "apply-lever"],
        "tags": ["answers", "custom-questions", "application"],
    },
    {
        "id": "soul_context",
        "path": "SOUL.md",
        "purpose": "Howard's persona, role-specific narrative answers, achievements, and communication guidelines.",
        "profiles": ["apply-ashby", "apply-greenhouse", "apply-lever"],
        "tags": ["persona", "essays", "narrative", "application"],
    },
]


def _sha256_head(path: str, max_bytes: int = 64 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(max_bytes))
    return h.hexdigest()


def _collect_headings(lines: List[str], max_count: int = 30) -> List[str]:
    headings: List[str] = []
    for line in lines:
        if line.startswith("#"):
            headings.append(line.strip())
            if len(headings) >= max_count:
                break
    return headings


def _markdown_sections(lines: List[str]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    pattern = re.compile(r"^(#{1,6})\s+(.*)\s*$")
    for idx, raw in enumerate(lines):
        m = pattern.match(raw)
        if not m:
            continue
        sections.append(
            {
                "heading": m.group(2).strip(),
                "level": len(m.group(1)),
                "line": idx + 1,
            }
        )
    return sections


def _build_entry(spec: Dict[str, Any]) -> Dict[str, Any]:
    rel_path = spec["path"]
    abs_path = os.path.join(WORKSPACE, rel_path)
    entry: Dict[str, Any] = {
        "id": spec["id"],
        "path": rel_path,
        "purpose": spec["purpose"],
        "profiles": spec["profiles"],
        "tags": spec["tags"],
        "exists": os.path.exists(abs_path),
        "is_markdown": rel_path.endswith(".md"),
        "is_code": rel_path.endswith((".py", ".js", ".ts", ".mjs", ".sh")),
    }

    if not entry["exists"]:
        entry["error"] = "missing"
        return entry

    stat = os.stat(abs_path)
    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    entry["size_bytes"] = stat.st_size
    entry["mtime_unix"] = int(stat.st_mtime)
    entry["line_count"] = len(lines)
    entry["sha256_head"] = _sha256_head(abs_path)
    entry["headings"] = _collect_headings(lines)
    if entry["is_markdown"]:
        entry["sections"] = _markdown_sections(lines)
    else:
        entry["sections"] = []
    return entry


def build_manifest(output_path: str) -> Dict[str, Any]:
    entries = [_build_entry(spec) for spec in CURATED_FILES]
    manifest = {
        "generated_at_unix": int(time.time()),
        "workspace": WORKSPACE,
        "count": len(entries),
        "entries": entries,
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return manifest


def load_manifest(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return build_manifest(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_entries(manifest: Dict[str, Any], profile: Optional[str], limit: int) -> int:
    entries = manifest.get("entries", [])
    if profile:
        entries = [e for e in entries if profile in e.get("profiles", [])]

    entries = sorted(entries, key=lambda e: e["id"])
    if limit > 0:
        entries = entries[:limit]

    print(
        "ID\tPATH\tLINES\tPROFILES\tPURPOSE",
        flush=True,
    )
    for e in entries:
        line_count = str(e.get("line_count", 0) if e.get("exists") else "-")
        profiles = ",".join(e.get("profiles", []))
        purpose = e.get("purpose", "")
        print(f"{e['id']}\t{e['path']}\t{line_count}\t{profiles}\t{purpose}", flush=True)
    return 0


def _resolve_entry(manifest: Dict[str, Any], entry_id: str) -> Dict[str, Any]:
    for e in manifest.get("entries", []):
        if e.get("id") == entry_id:
            return e
    raise KeyError(f"entry id not found: {entry_id}")


def _find_markdown_section_bounds(lines: List[str], section: str) -> Optional[tuple[int, int]]:
    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)\s*$")
    section_lower = section.strip().lower()
    start_idx = -1
    start_level = 0

    for i, raw in enumerate(lines):
        m = heading_pattern.match(raw)
        if not m:
            continue
        title = m.group(2).strip().lower()
        if section_lower in title:
            start_idx = i
            start_level = len(m.group(1))
            break
    if start_idx < 0:
        return None

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        m = heading_pattern.match(lines[j])
        if not m:
            continue
        if len(m.group(1)) <= start_level:
            end_idx = j
            break
    return start_idx, end_idx


def read_entry(
    manifest: Dict[str, Any],
    entry_id: str,
    section: Optional[str],
    max_lines: int,
    with_line_numbers: bool,
    raw_output: bool,
) -> int:
    try:
        entry = _resolve_entry(manifest, entry_id)
    except KeyError as e:
        print(str(e), file=sys.stderr)
        return 2

    abs_path = os.path.join(WORKSPACE, entry["path"])
    if not os.path.exists(abs_path):
        print(f"missing file: {entry['path']}", file=sys.stderr)
        return 2

    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    slice_start = 0
    slice_end = len(lines)
    if section:
        bounds = _find_markdown_section_bounds(lines, section)
        if bounds:
            slice_start, slice_end = bounds
        else:
            print(
                f"section not found in {entry_id}: {section!r} (printing head)",
                file=sys.stderr,
            )
            slice_end = min(len(lines), max_lines)

    selected = lines[slice_start:slice_end]
    if max_lines > 0:
        selected = selected[:max_lines]

    if not raw_output:
        print(
            json.dumps(
                {
                    "entry_id": entry_id,
                    "path": entry["path"],
                    "purpose": entry["purpose"],
                    "section": section or "",
                    "start_line": slice_start + 1,
                    "line_count": len(selected),
                },
                ensure_ascii=True,
            )
        )

    if with_line_numbers:
        for idx, line in enumerate(selected, start=slice_start + 1):
            sys.stdout.write(f"{idx:>5} {line}")
    else:
        sys.stdout.writelines(selected)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Metadata-first context manifest helper")
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST_PATH,
        help=f"Manifest path (default: {DEFAULT_MANIFEST_PATH})",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Build/update manifest file")
    p_build.add_argument("--quiet", action="store_true", help="Suppress summary output")

    p_list = sub.add_parser("list", help="List manifest entries")
    p_list.add_argument("--profile", default="", help="Profile filter (e.g. orchestrator, apply-lever)")
    p_list.add_argument("--limit", type=int, default=50, help="Maximum entries to print")

    p_read = sub.add_parser("read", help="Read one entry (optionally by markdown section)")
    p_read.add_argument("entry_id", help="Manifest entry id")
    p_read.add_argument("--section", default="", help="Markdown heading substring")
    p_read.add_argument("--max-lines", type=int, default=180, help="Maximum lines to print")
    p_read.add_argument(
        "--line-numbers",
        action="store_true",
        help="Prefix output lines with 1-based line numbers",
    )
    p_read.add_argument(
        "--raw",
        action="store_true",
        help="Print selected lines only (no JSON metadata header)",
    )

    args = parser.parse_args()

    if args.cmd == "build":
        manifest = build_manifest(args.manifest)
        if not args.quiet:
            print(
                json.dumps(
                    {
                        "manifest": args.manifest,
                        "count": manifest["count"],
                        "generated_at_unix": manifest["generated_at_unix"],
                    },
                    ensure_ascii=True,
                )
            )
        return 0

    manifest = load_manifest(args.manifest)
    if args.cmd == "list":
        profile = args.profile.strip() or None
        return list_entries(manifest, profile, args.limit)

    if args.cmd == "read":
        section = args.section.strip() or None
        return read_entry(
            manifest=manifest,
            entry_id=args.entry_id,
            section=section,
            max_lines=args.max_lines,
            with_line_numbers=args.line_numbers,
            raw_output=args.raw,
        )

    print(f"unknown command: {args.cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
