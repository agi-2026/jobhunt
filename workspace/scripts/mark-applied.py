#!/usr/bin/env python3
"""
Mark a job as applied: updates queue status, dedup index, and verifies consistency.
Usage: python3 scripts/mark-applied.py "<url>" ["<company>"] ["<title>"]
"""
import sys
import re
import os
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE_PATH = os.path.join(WORKSPACE, "job-queue.md")
DEDUP_PATH = os.path.join(WORKSPACE, "dedup-index.md")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/mark-applied.py '<url>' ['<company>'] ['<title>']")
        sys.exit(1)
    
    url = sys.argv[1].strip().rstrip("/")
    company = sys.argv[2] if len(sys.argv) > 2 else ""
    title = sys.argv[3] if len(sys.argv) > 3 else ""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 1. Update job-queue.md: REMOVE the entry from PENDING section entirely
    queue_updated = False
    with open(QUEUE_PATH, "r") as f:
        content = f.read()
    
    lines = content.split('\n')
    url_variants = [url, url + "/application", url.replace("/application", "")]
    i = 0
    while i < len(lines):
        if lines[i].startswith('### '):
            block_start = i
            block_end = i + 1
            while block_end < len(lines) and not lines[block_end].startswith('### ') and not lines[block_end].startswith('## '):
                block_end += 1
            block = '\n'.join(lines[block_start:block_end])
            if any(v in block for v in url_variants) and 'PENDING' in block:
                del lines[block_start:block_end]
                queue_updated = True
                continue
            i = block_end
        else:
            i += 1
    
    if queue_updated:
        with open(QUEUE_PATH, "w") as f:
            f.write('\n'.join(lines))
        print(f"QUEUE: Marked COMPLETED")
    else:
        print(f"QUEUE: Already COMPLETED or not found")
    
    # 2. Update dedup-index.md: change PENDING → APPLIED
    dedup_updated = False
    url_variants = [url, url + "/application", url.replace("/application", "")]
    
    with open(DEDUP_PATH, "r") as f:
        dedup_lines = f.readlines()
    
    seen_urls = set()
    new_dedup_lines = []
    for line in dedup_lines:
        matched = False
        for variant in url_variants:
            if variant in line:
                matched = True
                if "PENDING" in line or "| APPLIED" not in line:
                    # Update to APPLIED
                    parts = line.strip().split(" | ")
                    if len(parts) >= 4:
                        parts[3] = "APPLIED"
                    if len(parts) >= 5:
                        parts[4] = f" {datetime.now().strftime('%Y-%m-%d')}"
                    new_line = " | ".join(parts) + "\n"
                    norm_url = variant.replace("/application", "")
                    if norm_url not in seen_urls:
                        new_dedup_lines.append(new_line)
                        seen_urls.add(norm_url)
                        dedup_updated = True
                else:
                    norm_url = variant.replace("/application", "")
                    if norm_url not in seen_urls:
                        new_dedup_lines.append(line)
                        seen_urls.add(norm_url)
                break
        if not matched:
            new_dedup_lines.append(line)
    
    # If URL not in dedup at all, add it
    norm_url = url.replace("/application", "")
    if norm_url not in seen_urls:
        new_entry = f"{url} | {company} | {title} | APPLIED | {datetime.now().strftime('%Y-%m-%d')}\n"
        new_dedup_lines.append(new_entry)
        dedup_updated = True
    
    if dedup_updated:
        with open(DEDUP_PATH, "w") as f:
            f.writelines(new_dedup_lines)
        print(f"DEDUP: Updated to APPLIED")
    else:
        print(f"DEDUP: Already APPLIED")
    
    print(f"DONE: {company} — {title}")

if __name__ == "__main__":
    main()
