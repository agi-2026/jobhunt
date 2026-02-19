#!/usr/bin/env python3
"""
Check and refresh the Anthropic auth token in OpenClaw.

Supports both legacy "token" type and new "oauth" type profiles.
For OAuth profiles, uses the refresh token to get a new access token.

Usage:
  python3 scripts/refresh-token.py              # Check + auto-refresh if needed
  python3 scripts/refresh-token.py check        # Same as above
  python3 scripts/refresh-token.py refresh      # Force refresh via OAuth endpoint
"""
import sys
import os
import json
import time
import urllib.request
import urllib.error
import ssl

AUTH_PROFILES = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"


def load_profiles():
    with open(AUTH_PROFILES, "r") as f:
        return json.load(f)


def save_profiles(data):
    with open(AUTH_PROFILES, "w") as f:
        json.dump(data, f, indent=2)


def get_cred_info(profiles):
    """Extract credential info from auth profile."""
    cred = profiles["profiles"]["anthropic:default"]
    ctype = cred.get("type", "token")
    if ctype == "oauth":
        return {
            "type": "oauth",
            "access": cred.get("access", ""),
            "refresh": cred.get("refresh", ""),
            "expires": cred.get("expires", 0),
        }
    else:
        return {
            "type": "token",
            "access": cred.get("token", ""),
            "refresh": "",
            "expires": 0,
        }


def refresh_oauth(refresh_token):
    """Refresh token via Anthropic OAuth endpoint. Returns new creds dict."""
    payload = json.dumps({
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token,
    }).encode()

    ctx = ssl.create_default_context()
    req = urllib.request.Request(TOKEN_URL, data=payload, headers={
        "Content-Type": "application/json",
        "User-Agent": "claude-code/2.1.42",
    })

    resp = urllib.request.urlopen(req, timeout=15, context=ctx)
    body = json.loads(resp.read().decode())
    return {
        "access": body["access_token"],
        "refresh": body.get("refresh_token", refresh_token),
        "expires": int(time.time() * 1000) + (body.get("expires_in", 3600) * 1000) - (5 * 60 * 1000),
    }


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"

    if cmd in ("check", "refresh"):
        profiles = load_profiles()
        info = get_cred_info(profiles)
        masked = f"{info['access'][:15]}...{info['access'][-4:]}" if info["access"] else "NONE"

        print(f"Profile type: {info['type']}")
        print(f"Access token: {masked} ({len(info['access'])} chars)")

        now = int(time.time() * 1000)
        if info["expires"] > 0:
            remaining_ms = info["expires"] - now
            remaining_min = remaining_ms / 60000
            if remaining_ms > 0:
                print(f"Expires in: {remaining_min:.0f} min ({remaining_min/60:.1f}h)")
            else:
                print(f"EXPIRED: {-remaining_min:.0f} min ago")
        else:
            print("Expires: unknown (legacy token type)")

        has_refresh = bool(info.get("refresh"))
        print(f"Refresh token: {'present' if has_refresh else 'MISSING'}")

        # Check if we should refresh
        should_refresh = cmd == "refresh"
        if info["expires"] > 0 and info["expires"] - now < 10 * 60 * 1000:
            should_refresh = True
            print("\nToken near expiry or expired, auto-refreshing...")

        if should_refresh and has_refresh:
            try:
                new_creds = refresh_oauth(info["refresh"])
                profiles["profiles"]["anthropic:default"] = {
                    "type": "oauth",
                    "provider": "anthropic",
                    "access": new_creds["access"],
                    "refresh": new_creds["refresh"],
                    "expires": new_creds["expires"],
                }
                profiles["usageStats"]["anthropic:default"] = {"lastUsed": 0, "errorCount": 0}
                save_profiles(profiles)
                new_masked = f"{new_creds['access'][:15]}...{new_creds['access'][-4:]}"
                new_remaining = (new_creds["expires"] - int(time.time() * 1000)) / 60000
                print(f"\nREFRESHED: {new_masked} valid for {new_remaining:.0f} min")
                print("Gateway will pick up new token on next API call.")
            except Exception as e:
                print(f"\nREFRESH FAILED: {e}")
                sys.exit(1)
        elif should_refresh and not has_refresh:
            print("\nCannot refresh: no refresh token available")
            print("Re-authenticate: python3 scripts/sync-oauth-token.py --force")
            sys.exit(1)
        elif info["expires"] > 0 and info["expires"] - now > 10 * 60 * 1000:
            print(f"\nSTATUS: OK — token valid for {remaining_min:.0f} min")
        else:
            print("\nSTATUS: OK (legacy token, no expiry tracking)")

    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python3 scripts/refresh-token.py [check | refresh]")
        sys.exit(1)


if __name__ == "__main__":
    main()
