#!/usr/bin/env python3
"""
Full job board search — scrapes all sources, deduplicates, scores, and sorts queue.

Runs all search scripts in sequence:
  1. Ashby API      — ~101 companies
  2. Greenhouse API — ~60 companies
  3. Lever API      — ~34 companies
  4. VC Boards      — Sequoia, Greylock, Khosla, a16z, etc.

After all sources, optionally re-scores the full queue with Claude to remove
irrelevant jobs (--rescore flag). The queue is already sorted by score as jobs
are inserted via add-to-queue.py.

Usage:
  python3 scripts/search-all.py                   # run all sources, add to queue
  python3 scripts/search-all.py --dry-run          # show what would be added (no writes)
  python3 scripts/search-all.py --rescore          # also rescore+remove irrelevant after search
  python3 scripts/search-all.py --skip-lever       # skip Lever (hCaptcha issues)
  python3 scripts/search-all.py --only ashby       # run only one source
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

# ANSI colors for terminal output
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# Search sources in priority order
SOURCES = [
    {
        "id": "ashby",
        "name": "Ashby API (~101 companies)",
        "cmd": ["python3", os.path.join(SCRIPT_DIR, "search-ashby-api.py"), "--all"],
    },
    {
        "id": "greenhouse",
        "name": "Greenhouse API (~60 companies)",
        "cmd": ["python3", os.path.join(SCRIPT_DIR, "search-greenhouse-api.py"), "--all"],
    },
    {
        "id": "lever",
        "name": "Lever API (~34 companies)",
        "cmd": ["python3", os.path.join(SCRIPT_DIR, "search-lever-api.py"), "--all"],
    },
    {
        "id": "vc",
        "name": "VC Portfolio Boards (Sequoia, Greylock, Khosla, etc.)",
        "cmd": ["python3", os.path.join(SCRIPT_DIR, "search-vc-boards.py"), "--all"],
    },
]


def run_source(source: dict, add: bool, dry_run: bool) -> dict:
    """Run one search source and return result summary."""
    cmd = list(source["cmd"])
    if add and not dry_run:
        cmd.append("--add")

    print(f"\n{CYAN}{BOLD}▶ {source['name']}{RESET}")
    print(f"  {' '.join(cmd)}")

    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min per source
            cwd=os.path.dirname(SCRIPT_DIR),  # workspace root
        )
        elapsed = time.time() - t0

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        err_lines = result.stderr.strip().split("\n") if result.stderr.strip() else []

        # Parse stats from output (strip leading whitespace — some scripts indent ADDED lines)
        added = sum(1 for l in lines if l.lstrip().startswith("ADDED"))
        dupes = sum(1 for l in lines if l.lstrip().startswith("DUPLICATE"))
        skipped = sum(1 for l in lines if l.lstrip().startswith("SKIPPED") or l.lstrip().startswith("SKIP"))
        found = sum(1 for l in lines if l.lstrip().startswith("FOUND"))

        # Print output (trim long lists to keep screen readable)
        for line in lines[:60]:
            if line.startswith("ADDED"):
                print(f"  {GREEN}{line}{RESET}")
            elif line.startswith("DUPLICATE"):
                print(f"  {YELLOW}{line}{RESET}")
            elif line.startswith("ERROR") or line.startswith("FAIL"):
                print(f"  {RED}{line}{RESET}")
            elif line:
                print(f"  {line}")
        if len(lines) > 60:
            print(f"  ... ({len(lines) - 60} more lines)")

        if err_lines and result.returncode != 0:
            for line in err_lines[:10]:
                print(f"  {RED}ERR: {line}{RESET}")

        status = "ok" if result.returncode == 0 else "error"
        return {
            "id": source["id"],
            "name": source["name"],
            "status": status,
            "added": added,
            "dupes": dupes,
            "skipped": skipped,
            "found": found,
            "elapsed": elapsed,
        }

    except subprocess.TimeoutExpired:
        print(f"  {RED}TIMEOUT after 5 minutes{RESET}")
        return {"id": source["id"], "name": source["name"], "status": "timeout",
                "added": 0, "dupes": 0, "skipped": 0, "found": 0, "elapsed": 300}
    except Exception as e:
        print(f"  {RED}ERROR: {e}{RESET}")
        return {"id": source["id"], "name": source["name"], "status": "error",
                "added": 0, "dupes": 0, "skipped": 0, "found": 0, "elapsed": 0}


def run_rescore() -> None:
    """Re-score the full queue with Claude and remove irrelevant jobs."""
    print(f"\n{CYAN}{BOLD}▶ Rescoring queue with Claude (removing irrelevant jobs)...{RESET}")
    cmd = ["python3", os.path.join(SCRIPT_DIR, "rescore-queue.py"), "--remove"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        for line in lines:
            if "REMOVED" in line or "FAIL" in line:
                print(f"  {YELLOW}{line}{RESET}")
            elif line:
                print(f"  {line}")
        if result.returncode != 0 and result.stderr:
            print(f"  {RED}ERR: {result.stderr[:300]}{RESET}")
    except subprocess.TimeoutExpired:
        print(f"  {RED}Rescore timed out after 10 minutes{RESET}")
    except Exception as e:
        print(f"  {RED}Rescore error: {e}{RESET}")


def get_queue_stats() -> str:
    """Return a quick pending/applied count from queue-summary."""
    try:
        result = subprocess.run(
            ["python3", os.path.join(SCRIPT_DIR, "queue-summary.py"), "--actionable", "--top", "1"],
            capture_output=True, text=True, timeout=15
        )
        first_line = (result.stdout or "").strip().split("\n")[0]
        return first_line  # e.g. "QUEUE: 127 pending | 0 in_progress"
    except Exception:
        return "queue stats unavailable"


def main():
    parser = argparse.ArgumentParser(description="Run all job search sources and update queue")
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not write to queue — show what would be added")
    parser.add_argument("--rescore", action="store_true",
                        help="After search, rescore full queue and remove irrelevant jobs")
    parser.add_argument("--skip-lever", action="store_true",
                        help="Skip Lever (hCaptcha issues)")
    parser.add_argument("--only", choices=["ashby", "greenhouse", "lever", "vc"],
                        help="Run only one specific source")
    args = parser.parse_args()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Job Board Search — {datetime.now().strftime('%Y-%m-%d %H:%M')}{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")

    if args.dry_run:
        print(f"{YELLOW}  DRY RUN — no changes will be made to the queue{RESET}")

    before_stats = get_queue_stats()
    print(f"  Before: {before_stats}")

    # Filter sources
    sources_to_run = SOURCES
    if args.only:
        sources_to_run = [s for s in SOURCES if s["id"] == args.only]
    elif args.skip_lever:
        sources_to_run = [s for s in SOURCES if s["id"] != "lever"]

    results = []
    t_total = time.time()

    for source in sources_to_run:
        r = run_source(source, add=True, dry_run=args.dry_run)
        results.append(r)

    # Rescore after all sources if requested
    if args.rescore and not args.dry_run:
        run_rescore()

    # Summary
    elapsed_total = time.time() - t_total
    after_stats = get_queue_stats()

    print(f"\n{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  Summary{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"  Before: {before_stats}")
    print(f"  After:  {after_stats}")
    print()

    total_added = 0
    total_dupes = 0
    for r in results:
        icon = GREEN + "✓" + RESET if r["status"] == "ok" else RED + "✗" + RESET
        print(f"  {icon} {r['name']}: +{r['added']} new, {r['dupes']} dupes  ({r['elapsed']:.0f}s)")
        total_added += r["added"]
        total_dupes += r["dupes"]

    print()
    print(f"  {GREEN}{BOLD}Total new jobs added: {total_added}{RESET}")
    print(f"  Duplicates skipped:  {total_dupes}")
    print(f"  Total time: {elapsed_total:.0f}s")

    if args.dry_run:
        print(f"\n  {YELLOW}DRY RUN — run without --dry-run to actually add jobs{RESET}")
    elif not args.rescore:
        print(f"\n  Tip: run with --rescore to clean out irrelevant jobs from the full queue")

    print()


if __name__ == "__main__":
    main()
