#!/usr/bin/env python3
"""Shared Outlook auth helper for Microsoft Graph API.

Cross-platform (macOS/Windows/Linux). Uses only Python stdlib.

Imported by all outlook-* scripts:
    from outlook_auth import ensure_valid_token, graph_request

Token storage: ~/.outlook-assistant/credentials.json
Config: ~/.outlook-assistant/config.json
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CONFIG_DIR = os.path.expanduser("~/.outlook-assistant")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
CREDS_PATH = os.path.join(CONFIG_DIR, "credentials.json")
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
DEFAULT_SCOPES = "Mail.ReadWrite Mail.Send User.Read offline_access"


def _ssl_ctx():
    return ssl.create_default_context()


def load_config():
    """Load Azure app config. Raises if missing."""
    if not os.path.isfile(CONFIG_PATH):
        print(f"ERROR: Config not found at {CONFIG_PATH}", file=sys.stderr)
        print("Run: python3 skills/outlook-assistant/scripts/outlook-setup.py", file=sys.stderr)
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_credentials():
    """Load access/refresh tokens. Returns None if missing."""
    if not os.path.isfile(CREDS_PATH):
        return None
    with open(CREDS_PATH) as f:
        return json.load(f)


def save_credentials(creds):
    """Atomic write of credentials."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CREDS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(creds, f, indent=2)
    os.replace(tmp, CREDS_PATH)
    os.chmod(CREDS_PATH, 0o600)


def refresh_token(config, creds):
    """Exchange refresh token for new access token via Microsoft token endpoint.

    Microsoft requires application/x-www-form-urlencoded (not JSON).
    """
    tenant = config.get("tenant_id", "consumers")
    scopes = config.get("scopes", DEFAULT_SCOPES)
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": config["client_id"],
        "refresh_token": creds["refresh_token"],
        "scope": scopes,
    }).encode()
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=_ssl_ctx())
        body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"ERROR: Token refresh failed ({e.code}): {err_body}", file=sys.stderr)
        sys.exit(1)

    now_ms = int(time.time() * 1000)
    expires_in = body.get("expires_in", 3600)
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", creds["refresh_token"]),
        "expires_at_ms": now_ms + (expires_in * 1000) - (5 * 60 * 1000),  # 5 min buffer
    }


def ensure_valid_token():
    """Return a valid access token, auto-refreshing if needed."""
    config = load_config()
    creds = load_credentials()
    if not creds:
        print("ERROR: No credentials found. Run outlook-setup.py first.", file=sys.stderr)
        sys.exit(1)

    now_ms = int(time.time() * 1000)
    expires_at = creds.get("expires_at_ms", 0)

    # Refresh if token expires within 10 minutes
    if now_ms >= expires_at - (10 * 60 * 1000):
        creds = refresh_token(config, creds)
        save_credentials(creds)

    return creds["access_token"]


def graph_request(endpoint, method="GET", body=None, params=None, paginate=False):
    """Make an authenticated Microsoft Graph API request.

    Args:
        endpoint: Graph API path (e.g., "/me/messages") or full URL
        method: HTTP method
        body: Dict to send as JSON body
        params: Dict of query parameters
        paginate: If True, follows @odata.nextLink and returns all results

    Returns:
        Parsed JSON response dict
    """
    token = ensure_valid_token()

    if endpoint.startswith("http"):
        url = endpoint
    else:
        url = f"{GRAPH_BASE}{endpoint}"

    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = urllib.request.urlopen(req, timeout=30, context=_ssl_ctx())
            result = json.loads(resp.read().decode()) if resp.read else {}
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                retry_after = int(e.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            err_body = e.read().decode() if e.fp else ""
            print(f"ERROR: Graph API {method} {endpoint} failed ({e.code}): {err_body}",
                  file=sys.stderr)
            sys.exit(1)

    # Handle pagination
    if paginate and "@odata.nextLink" in result:
        all_values = result.get("value", [])
        next_url = result["@odata.nextLink"]
        page_limit = 5  # Safety cap
        for _ in range(page_limit):
            if not next_url:
                break
            page = graph_request(next_url, paginate=False)
            all_values.extend(page.get("value", []))
            next_url = page.get("@odata.nextLink")
        result["value"] = all_values
        result.pop("@odata.nextLink", None)

    return result


def check_auth():
    """Validate auth setup and print status."""
    config = load_config()
    creds = load_credentials()
    if not creds:
        print("STATUS: NOT_CONFIGURED")
        print("No credentials found. Run outlook-setup.py first.")
        return False

    now_ms = int(time.time() * 1000)
    expires_at = creds.get("expires_at_ms", 0)
    if now_ms >= expires_at:
        print("STATUS: EXPIRED")
        print("Token expired. Attempting refresh...")
        try:
            creds = refresh_token(config, creds)
            save_credentials(creds)
            print("STATUS: REFRESHED")
        except SystemExit:
            print("STATUS: REFRESH_FAILED")
            return False

    # Verify with /me
    try:
        token = creds["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        req = urllib.request.Request(f"{GRAPH_BASE}/me", headers=headers)
        resp = urllib.request.urlopen(req, timeout=10, context=_ssl_ctx())
        user = json.loads(resp.read().decode())
        email = user.get("mail") or user.get("userPrincipalName", "unknown")
        name = user.get("displayName", "unknown")
        remaining_min = max(0, (expires_at - now_ms) // 60000)
        print(f"STATUS: VALID")
        print(f"Account: {name} <{email}>")
        print(f"Token expires in: {remaining_min} minutes")
        return True
    except Exception as e:
        print(f"STATUS: ERROR ({e})")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        ok = check_auth()
        sys.exit(0 if ok else 1)
    else:
        print("Usage: python3 outlook_auth.py check")
        print("  Validates auth setup and token status")
