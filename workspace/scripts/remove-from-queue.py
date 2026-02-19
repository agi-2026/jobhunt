#!/usr/bin/env python3
"""
Remove a job from the queue and add to dedup as SKIPPED or APPLIED.

Usage:
  python3 scripts/remove-from-queue.py "<url>" [--applied]
  python3 scripts/remove-from-queue.py "<company>" "<title>" [--applied]
  python3 scripts/remove-from-queue.py --search "<keyword>"    # search and list matches

--applied: mark as APPLIED in dedup (default: SKIPPED)
--search: list matching jobs without removing
"""
import sys, os, re, fcntl
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
QUEUE_PATH = os.path.join(WORKSPACE, "job-queue.md")
DEDUP_PATH = os.path.join(WORKSPACE, "dedup-index.md")
LOCK_PATH = os.path.join(WORKSPACE, ".queue.lock")

def search_queue(keyword):
    with open(QUEUE_PATH) as f:
        lines = f.read().split('\n')
    results = []
    i = 0
    while i < len(lines):
        if lines[i].startswith('### '):
            end = i + 1
            while end < len(lines) and not lines[end].startswith('### ') and not lines[end].startswith('## '):
                end += 1
            block = '\n'.join(lines[i:end])
            if keyword.lower() in block.lower() and 'COMPLETED' not in block and 'SKIPPED' not in block:
                title = lines[i].replace('### ', '').strip()
                url_match = re.search(r'URL:\*\* (https?://\S+)', block)
                url = url_match.group(1) if url_match else 'no-url'
                results.append((title, url))
            i = end
        else:
            i += 1
    return results

def remove_job(identifier, identifier2=None, mark_applied=False):
    with open(QUEUE_PATH) as f:
        lines = f.read().split('\n')
    
    status = "APPLIED" if mark_applied else "SKIPPED"
    removed_info = None
    i = 0
    while i < len(lines):
        if lines[i].startswith('### '):
            end = i + 1
            while end < len(lines) and not lines[end].startswith('### ') and not lines[end].startswith('## '):
                end += 1
            block = '\n'.join(lines[i:end])
            
            match = False
            if identifier.startswith('http') and identifier in block:
                match = True
            elif identifier2:
                # company + title match
                if identifier.lower() in block.lower() and identifier2.lower() in block.lower():
                    match = True
            elif not identifier.startswith('http') and identifier.lower() in lines[i].lower():
                match = True
            
            if match and 'COMPLETED' not in block and 'SKIPPED' not in block:
                title = lines[i].replace('### ', '').strip()
                url_match = re.search(r'URL:\*\* (https?://\S+)', block)
                url = url_match.group(1) if url_match else ''
                removed_info = (title, url)
                del lines[i:end]
                break
            i = end
        else:
            i += 1
    
    if not removed_info:
        print(f"NOT FOUND in queue: {identifier}")
        return False
    
    with open(QUEUE_PATH, 'w') as f:
        f.write('\n'.join(lines))
    
    # Add to dedup
    title, url = removed_info
    if url:
        with open(DEDUP_PATH, 'a') as f:
            f.write(f"{url} | {title} | {status} | {datetime.now().strftime('%Y-%m-%d')}\n")
    
    print(f"REMOVED: {title}")
    print(f"DEDUP: Marked {status}")
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 scripts/remove-from-queue.py '<url>' [--applied]")
        print("  python3 scripts/remove-from-queue.py '<company>' '<title>' [--applied]")
        print("  python3 scripts/remove-from-queue.py --search '<keyword>'")
        sys.exit(1)
    
    args = sys.argv[1:]
    mark_applied = '--applied' in args
    if mark_applied:
        args.remove('--applied')
    
    if args[0] == '--search':
        keyword = args[1] if len(args) > 1 else ''
        results = search_queue(keyword)
        print(f"Found {len(results)} matches for '{keyword}':")
        for title, url in results:
            print(f"  {title}")
            print(f"    {url}")
        return

    # Acquire exclusive lock for write operations
    with open(LOCK_PATH, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            if len(args) >= 2 and not args[0].startswith('http'):
                remove_job(args[0], args[1], mark_applied)
            else:
                remove_job(args[0], mark_applied=mark_applied)
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)

if __name__ == "__main__":
    main()
