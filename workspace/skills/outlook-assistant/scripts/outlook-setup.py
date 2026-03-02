#!/usr/bin/env python3
"""One-time setup for Outlook Assistant — Azure app registration + OAuth device code flow.

Cross-platform (macOS/Windows/Linux). Uses only Python stdlib.

Usage:
    python3 skills/outlook-assistant/scripts/outlook-setup.py              # Interactive setup
    python3 skills/outlook-assistant/scripts/outlook-setup.py --check      # Verify existing setup
    python3 skills/outlook-assistant/scripts/outlook-setup.py --refresh    # Force token refresh
"""
import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# Add workspace/scripts to path for outlook_auth
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_SCRIPTS = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", "..", "scripts"))
sys.path.insert(0, WORKSPACE_SCRIPTS)

from outlook_auth import (
    CONFIG_DIR, CONFIG_PATH, CREDS_PATH, DEFAULT_SCOPES,
    check_auth, load_config, load_credentials, refresh_token, save_credentials,
)

TOKEN_ENDPOINT = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
DEVICE_CODE_ENDPOINT = TOKEN_ENDPOINT + "/devicecode"
TOKEN_EXCHANGE_ENDPOINT = TOKEN_ENDPOINT + "/token"


def _ssl_ctx():
    return ssl.create_default_context()


def print_setup_guide():
    """Print step-by-step Azure app registration guide."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           Outlook Assistant — One-Time Setup                 ║
╚══════════════════════════════════════════════════════════════╝

STEP 1: Create an Azure App Registration
─────────────────────────────────────────
1. Go to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
2. Click "+ New registration"
3. Name: "OpenClaw Outlook Assistant"
4. Supported account types: "Personal Microsoft accounts only"
   (If using work/school: "Accounts in any organizational directory and personal Microsoft accounts")
5. Redirect URI: Leave blank (we use device code flow)
6. Click "Register"

STEP 2: Copy the Application (client) ID
─────────────────────────────────────────
On the app overview page, copy the "Application (client) ID" (a UUID).

STEP 3: Enable Public Client Flows
───────────────────────────────────
1. Go to "Authentication" in the left sidebar
2. Under "Advanced settings", set "Allow public client flows" to YES
3. Click "Save"

STEP 4: Add API Permissions
────────────────────────────
1. Go to "API permissions" in the left sidebar
2. Click "+ Add a permission" → "Microsoft Graph" → "Delegated permissions"
3. Add these permissions:
   - Mail.ReadWrite
   - Mail.Send
   - User.Read
   - offline_access
4. Click "Add permissions"
   (No admin consent needed for personal accounts)
""")


def prompt_config():
    """Interactively collect config from user."""
    print_setup_guide()

    client_id = input("Enter your Application (client) ID: ").strip()
    if not client_id or len(client_id) < 10:
        print("ERROR: Invalid client ID.", file=sys.stderr)
        sys.exit(1)

    print("\nAccount type:")
    print("  1. Personal Microsoft account (outlook.com, hotmail.com)")
    print("  2. Work/School (Office 365)")
    choice = input("Choose [1]: ").strip() or "1"
    tenant_id = "consumers" if choice == "1" else "common"

    config = {
        "client_id": client_id,
        "tenant_id": tenant_id,
        "scopes": DEFAULT_SCOPES,
        "scan_defaults": {
            "days": 7,
            "max_results": 50,
        },
    }

    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(CONFIG_PATH, 0o600)
    print(f"\nConfig saved to: {CONFIG_PATH}")
    return config


def device_code_flow(config):
    """Perform OAuth2 device code flow to obtain tokens."""
    tenant = config.get("tenant_id", "consumers")
    scopes = config.get("scopes", DEFAULT_SCOPES)

    # Step 1: Request device code
    data = urllib.parse.urlencode({
        "client_id": config["client_id"],
        "scope": scopes,
    }).encode()
    req = urllib.request.Request(
        DEVICE_CODE_ENDPOINT.format(tenant=tenant),
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=_ssl_ctx())
        dc_response = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"ERROR: Device code request failed ({e.code}): {err}", file=sys.stderr)
        sys.exit(1)

    # Step 2: Display code to user
    user_code = dc_response["user_code"]
    verify_url = dc_response["verification_uri"]
    expires_in = dc_response.get("expires_in", 900)
    interval = dc_response.get("interval", 5)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  To sign in, open this URL in any browser:                   ║
║  {verify_url:<57s} ║
║                                                              ║
║  Enter code: {user_code:<45s} ║
╚══════════════════════════════════════════════════════════════╝

Waiting for you to authorize (expires in {expires_in // 60} minutes)...
""")

    # Step 3: Poll for token
    deadline = time.time() + expires_in
    while time.time() < deadline:
        time.sleep(interval)
        poll_data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": config["client_id"],
            "device_code": dc_response["device_code"],
        }).encode()
        poll_req = urllib.request.Request(
            TOKEN_EXCHANGE_ENDPOINT.format(tenant=tenant),
            data=poll_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            resp = urllib.request.urlopen(poll_req, timeout=15, context=_ssl_ctx())
            token_data = json.loads(resp.read().decode())

            # Success
            now_ms = int(time.time() * 1000)
            expires_in_s = token_data.get("expires_in", 3600)
            creds = {
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token", ""),
                "expires_at_ms": now_ms + (expires_in_s * 1000) - (5 * 60 * 1000),
            }
            save_credentials(creds)
            print("Authorization successful! Tokens saved.")
            return creds

        except urllib.error.HTTPError as e:
            err_body = json.loads(e.read().decode()) if e.fp else {}
            error_code = err_body.get("error", "")
            if error_code == "authorization_pending":
                print(".", end="", flush=True)
                continue
            elif error_code == "slow_down":
                interval += 5
                continue
            elif error_code == "authorization_declined":
                print("\nERROR: Authorization was declined.", file=sys.stderr)
                sys.exit(1)
            elif error_code == "expired_token":
                print("\nERROR: Device code expired. Run setup again.", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"\nERROR: Token poll failed: {err_body}", file=sys.stderr)
                sys.exit(1)

    print("\nERROR: Timed out waiting for authorization.", file=sys.stderr)
    sys.exit(1)


def verify_setup():
    """Verify the setup by calling /me."""
    from outlook_auth import GRAPH_BASE
    creds = load_credentials()
    if not creds:
        print("ERROR: No credentials found.", file=sys.stderr)
        return False

    try:
        headers = {"Authorization": f"Bearer {creds['access_token']}"}
        req = urllib.request.Request(f"{GRAPH_BASE}/me", headers=headers)
        resp = urllib.request.urlopen(req, timeout=10, context=_ssl_ctx())
        user = json.loads(resp.read().decode())
        email = user.get("mail") or user.get("userPrincipalName", "unknown")
        name = user.get("displayName", "unknown")
        print(f"\nSetup verified successfully!")
        print(f"  Account: {name} <{email}>")

        # Quick inbox check
        headers2 = {"Authorization": f"Bearer {creds['access_token']}"}
        req2 = urllib.request.Request(
            f"{GRAPH_BASE}/me/mailFolders/inbox?$select=totalItemCount,unreadItemCount",
            headers=headers2,
        )
        resp2 = urllib.request.urlopen(req2, timeout=10, context=_ssl_ctx())
        inbox = json.loads(resp2.read().decode())
        print(f"  Inbox: {inbox.get('totalItemCount', '?')} total, "
              f"{inbox.get('unreadItemCount', '?')} unread")
        return True
    except Exception as e:
        print(f"ERROR: Verification failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Outlook Assistant Setup")
    parser.add_argument("--check", action="store_true", help="Verify existing setup")
    parser.add_argument("--refresh", action="store_true", help="Force token refresh")
    args = parser.parse_args()

    if args.check:
        ok = check_auth()
        sys.exit(0 if ok else 1)

    if args.refresh:
        config = load_config()
        creds = load_credentials()
        if not creds:
            print("ERROR: No credentials to refresh. Run setup first.", file=sys.stderr)
            sys.exit(1)
        creds = refresh_token(config, creds)
        save_credentials(creds)
        print("Token refreshed successfully.")
        check_auth()
        sys.exit(0)

    # Interactive setup
    if os.path.isfile(CONFIG_PATH):
        print(f"Config already exists at {CONFIG_PATH}")
        choice = input("Overwrite? [y/N]: ").strip().lower()
        if choice != "y":
            config = load_config()
        else:
            config = prompt_config()
    else:
        config = prompt_config()

    # Device code flow
    device_code_flow(config)

    # Verify
    verify_setup()

    print(f"""
Setup complete! You can now use the Outlook Assistant.

Test with:
  python3 scripts/outlook_auth.py check
  python3 skills/outlook-assistant/scripts/outlook-scan.py --days 3
""")


if __name__ == "__main__":
    main()
