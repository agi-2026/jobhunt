#!/usr/bin/env python3
"""
Refresh OpenClaw's OAuth token using the Anthropic refresh endpoint.

OpenClaw's auth-profiles.json stores an OAuth credential (type: "oauth") with
access, refresh, and expires fields. The gateway auto-refreshes when expired,
but the watchdog calls this as a safety net.

Three methods in priority order:
  1. Direct OAuth refresh via platform.claude.com (works from crontab)
  2. Keychain sync (only works with GUI session)
  3. Skip if token still valid

Usage:
  python3 scripts/sync-oauth-token.py          # Refresh if needed
  python3 scripts/sync-oauth-token.py --check  # Check without writing
  python3 scripts/sync-oauth-token.py --force  # Force refresh even if valid
"""
import json
import os
import subprocess
import ssl
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

AUTH_PROFILES = os.path.expanduser("~/.openclaw/agents/main/agent/auth-profiles.json")
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
REFRESH_BUFFER_MS = 10 * 60 * 1000  # Refresh 10 min before expiry


def load_profiles():
    with open(AUTH_PROFILES) as f:
        return json.load(f)


def save_profiles(data):
    with open(AUTH_PROFILES, "w") as f:
        json.dump(data, f, indent=2)


def get_current_creds():
    """Read current OAuth credentials from auth-profiles.json."""
    data = load_profiles()
    cred = data["profiles"]["anthropic:default"]
    if cred.get("type") == "oauth":
        return {
            "access": cred.get("access", ""),
            "refresh": cred.get("refresh", ""),
            "expires": cred.get("expires", 0),
        }
    elif cred.get("type") == "token":
        return {
            "access": cred.get("token", ""),
            "refresh": "",
            "expires": 0,
        }
    return None


def refresh_via_api(refresh_token):
    """Refresh token via Anthropic OAuth endpoint."""
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


def refresh_via_keychain():
    """Try to get fresh token from macOS Keychain (GUI session only)."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip())
        oauth = data.get("claudeAiOauth", {})
        if not oauth or not oauth.get("refreshToken"):
            return None
        return {
            "access": oauth.get("accessToken", ""),
            "refresh": oauth.get("refreshToken", ""),
            "expires": oauth.get("expiresAt", 0),
        }
    except Exception:
        return None


def update_auth_profiles(creds):
    """Write refreshed credentials to auth-profiles.json."""
    data = load_profiles()
    data["profiles"]["anthropic:default"] = {
        "type": "oauth",
        "provider": "anthropic",
        "access": creds["access"],
        "refresh": creds["refresh"],
        "expires": creds["expires"],
    }
    data["usageStats"]["anthropic:default"] = {"lastUsed": 0, "errorCount": 0}
    save_profiles(data)


def update_keychain(creds):
    """Update macOS Keychain with fresh credentials (best-effort)."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return
        data = json.loads(result.stdout.strip())
        data["claudeAiOauth"]["accessToken"] = creds["access"]
        data["claudeAiOauth"]["refreshToken"] = creds["refresh"]
        data["claudeAiOauth"]["expiresAt"] = creds["expires"]
        new_val = json.dumps(data)
        subprocess.run(
            ["security", "delete-generic-password", "-s", "Claude Code-credentials"],
            capture_output=True, timeout=5
        )
        subprocess.run(
            ["security", "add-generic-password", "-s", "Claude Code-credentials",
             "-a", "claude-code", "-w", new_val, "-U"],
            capture_output=True, timeout=5
        )
    except Exception:
        pass  # Keychain update is best-effort


def main():
    check_only = "--check" in sys.argv
    force = "--force" in sys.argv

    creds = get_current_creds()
    if not creds:
        print("ERROR: No credentials found in auth-profiles.json")
        sys.exit(1)

    now = int(time.time() * 1000)
    remaining_ms = creds["expires"] - now if creds["expires"] > 0 else -1
    remaining_min = remaining_ms / 60000

    masked = f"{creds['access'][:15]}...{creds['access'][-4:]}" if creds["access"] else "NONE"

    if remaining_ms > REFRESH_BUFFER_MS and not force:
        print(f"OK — {masked} valid for {remaining_min:.0f} min")
        sys.exit(0)

    if remaining_ms > 0:
        print(f"NEAR_EXPIRY — {masked} expires in {remaining_min:.0f} min, refreshing...")
    else:
        print(f"EXPIRED — {masked} expired {-remaining_min:.0f} min ago, refreshing...")

    if check_only:
        print("(check only, not writing)")
        sys.exit(1 if remaining_ms <= 0 else 0)

    # Method 1: Direct API refresh (works from crontab)
    refresh_token = creds.get("refresh", "")
    if refresh_token:
        try:
            new_creds = refresh_via_api(refresh_token)
            update_auth_profiles(new_creds)
            update_keychain(new_creds)
            new_masked = f"{new_creds['access'][:15]}...{new_creds['access'][-4:]}"
            new_remaining = (new_creds["expires"] - int(time.time() * 1000)) / 60000
            print(f"REFRESHED (API) — {new_masked} valid for {new_remaining:.0f} min")
            sys.exit(0)
        except Exception as e:
            print(f"WARNING: API refresh failed: {e}")

    # Method 2: Keychain sync (GUI session only)
    keychain_creds = refresh_via_keychain()
    if keychain_creds and keychain_creds["access"] != creds["access"]:
        if keychain_creds.get("expires", 0) > now:
            update_auth_profiles(keychain_creds)
            km = f"{keychain_creds['access'][:15]}...{keychain_creds['access'][-4:]}"
            kr = (keychain_creds["expires"] - now) / 60000
            print(f"REFRESHED (Keychain) — {km} valid for {kr:.0f} min")
            sys.exit(0)

    print("ERROR: All refresh methods failed")
    sys.exit(1)


if __name__ == "__main__":
    main()
