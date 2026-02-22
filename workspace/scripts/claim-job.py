#!/usr/bin/env python3
"""Atomic job claim/release — prevents two parallel Ashby subagents applying to the same job.

Usage:
  python3 scripts/claim-job.py claim "<url>"    → CLAIMED | CLAIMED_BY_OTHER
  python3 scripts/claim-job.py release "<url>"  → RELEASED | NOT_FOUND
  python3 scripts/claim-job.py list             → list active claims with ages
"""
import sys
import os
import fcntl
import time
import hashlib
import json

WORKSPACE = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
CLAIMS_DIR = os.path.join(WORKSPACE, '.locks', 'claims')
CLAIMS_LOCK = os.path.join(WORKSPACE, '.locks', 'claims.lock')

# 40 min TTL — subagent timeout is 30 min, +10 min buffer for crash recovery
CLAIM_TTL_SECONDS = 40 * 60


def url_key(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def claim(url: str):
    os.makedirs(CLAIMS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CLAIMS_LOCK), exist_ok=True)
    claim_path = os.path.join(CLAIMS_DIR, f'{url_key(url)}.claim')

    with open(CLAIMS_LOCK, 'w') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            if os.path.exists(claim_path):
                age = time.time() - os.path.getmtime(claim_path)
                if age < CLAIM_TTL_SECONDS:
                    print('CLAIMED_BY_OTHER')
                    return
                # expired — reclaim it
            with open(claim_path, 'w') as f:
                json.dump({'url': url, 'pid': os.getpid(), 'claimed_at': time.time()}, f)
            print('CLAIMED')
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def release(url: str):
    claim_path = os.path.join(CLAIMS_DIR, f'{url_key(url)}.claim')
    if os.path.exists(claim_path):
        try:
            os.remove(claim_path)
            print('RELEASED')
        except OSError:
            print('NOT_FOUND')
    else:
        print('NOT_FOUND')


def list_claims():
    if not os.path.isdir(CLAIMS_DIR):
        print('No claims directory')
        return
    now = time.time()
    found = False
    for fname in sorted(os.listdir(CLAIMS_DIR)):
        if not fname.endswith('.claim'):
            continue
        found = True
        path = os.path.join(CLAIMS_DIR, fname)
        try:
            with open(path) as f:
                data = json.load(f)
            age = int(now - data.get('claimed_at', 0))
            expired = ' [EXPIRED]' if age > CLAIM_TTL_SECONDS else ''
            print(f"  {age}s{expired} | pid={data.get('pid', '?')} | {data.get('url', '?')}")
        except Exception:
            print(f"  ??? {fname}")
    if not found:
        print('No active claims')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: claim-job.py claim <url> | release <url> | list')
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'claim':
        if len(sys.argv) < 3:
            print('claim requires <url>', file=sys.stderr)
            sys.exit(1)
        claim(sys.argv[2])
    elif cmd == 'release':
        if len(sys.argv) < 3:
            print('release requires <url>', file=sys.stderr)
            sys.exit(1)
        release(sys.argv[2])
    elif cmd == 'list':
        list_claims()
    else:
        print(f'Unknown command: {cmd}', file=sys.stderr)
        sys.exit(1)
