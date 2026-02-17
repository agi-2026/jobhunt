#!/usr/bin/env python3
"""
Refresh the Anthropic auth token in OpenClaw.
Validates the current token, and if expired, accepts a new one.

Usage:
  python3 scripts/refresh-token.py              # Check current token health
  python3 scripts/refresh-token.py check        # Same as above
  python3 scripts/refresh-token.py set <token>  # Set a new token (joins multi-line)

Tip: If the token wraps across lines, quote it:
  python3 scripts/refresh-token.py set "sk-ant-oat01-...full...token"

After setting a new token, restart the gateway:
  kill $(lsof -ti :18789) && pnpm openclaw gateway --port 18789
"""
import sys
import os
import json
import urllib.request
import urllib.error
import ssl

AUTH_PROFILES = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
GATEWAY_PORT = 18789


def load_profiles():
    with open(AUTH_PROFILES, "r") as f:
        return json.load(f)


def save_profiles(data):
    with open(AUTH_PROFILES, "w") as f:
        json.dump(data, f, indent=2)
    print(f"SAVED: {AUTH_PROFILES}")


def check_token(token: str) -> tuple:
    """Check if a token is valid. Tries Bearer auth (OAuth/setup-token) then x-api-key."""
    ctx = ssl.create_default_context()
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}]
    }).encode()

    # Try both auth methods — setup-tokens use Bearer, API keys use x-api-key
    auth_methods = [
        ("Bearer (OAuth)", {"Authorization": f"Bearer {token}"}),
        ("x-api-key", {"x-api-key": token}),
    ]

    last_error = ""
    for method_name, auth_headers in auth_methods:
        try:
            headers = {
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
                **auth_headers,
            }
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload, headers=headers,
            )
            urllib.request.urlopen(req, timeout=10, context=ctx)
            return True, f"Valid ({method_name})"
        except urllib.error.HTTPError as e:
            if e.code in (400, 429):
                # Auth succeeded but request had issues — token is valid
                return True, f"Valid ({method_name})"
            elif e.code == 401:
                body = e.read().decode("utf-8", errors="ignore")
                try:
                    detail = json.loads(body)
                    last_error = detail.get("error", {}).get("message", "Auth failed")
                except Exception:
                    last_error = "Auth failed"
                continue  # Try next method
            else:
                body = e.read().decode("utf-8", errors="ignore")
                return False, f"HTTP {e.code}: {body[:200]}"
        except Exception as e:
            return False, f"Connection error: {e}"

    return False, f"EXPIRED (401): {last_error}"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd == "check":
        profiles = load_profiles()
        token = profiles["profiles"]["anthropic:default"]["token"]
        masked = token[:15] + "..." + token[-4:]
        print(f"Current token: {masked}")
        print(f"Length: {len(token)} chars")
        ok, msg = check_token(token)
        if ok:
            print(f"STATUS: OK — {msg}")
        else:
            print(f"STATUS: FAILED — {msg}")
            print("\nTo fix:")
            print('  python3 scripts/refresh-token.py set "sk-ant-oat01-...full-token..."')
            sys.exit(1)

    elif cmd == "set":
        if len(sys.argv) < 3:
            print('Usage: python3 scripts/refresh-token.py set "sk-ant-oat01-..."')
            sys.exit(1)
        # Join all remaining args (handles tokens split across shell args)
        new_token = "".join(sys.argv[2:]).strip()
        if len(new_token) < 80:
            print(f"ERROR: Token too short ({len(new_token)} chars, need 80+)")
            print("Tip: The token may have wrapped across lines. Quote it:")
            print('  python3 scripts/refresh-token.py set "sk-ant-oat01-...full...token"')
            sys.exit(1)

        masked = new_token[:15] + "..." + new_token[-4:]
        print(f"New token: {masked} ({len(new_token)} chars)")

        # Validate
        print("Validating...")
        ok, msg = check_token(new_token)
        if not ok:
            print(f"WARNING: Validation failed — {msg}")
            print("Saving anyway (OpenClaw may use different auth flow)...")

        profiles = load_profiles()
        profiles["profiles"]["anthropic:default"]["token"] = new_token
        profiles["usageStats"]["anthropic:default"] = {
            "lastUsed": 0, "errorCount": 0
        }
        save_profiles(profiles)
        print(f"\nSUCCESS: Token updated.")
        print("Now restart gateway:")
        print(f"  kill $(lsof -ti :{GATEWAY_PORT}) 2>/dev/null; cd ~/Desktop/Job\\ Search/openclaw && pnpm openclaw gateway --port {GATEWAY_PORT}")

    else:
        print(f"Unknown command: {cmd}")
        print('Usage: python3 scripts/refresh-token.py [check | set "token"]')
        sys.exit(1)


if __name__ == "__main__":
    main()
