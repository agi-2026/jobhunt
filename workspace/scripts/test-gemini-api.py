#!/usr/bin/env python3
"""
Quick Gemini API health test.

Usage:
  python3 scripts/test-gemini-api.py --api-key "<KEY>" --model gemini-3-flash-preview
  GEMINI_API_KEY="<KEY>" python3 scripts/test-gemini-api.py
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def http_get(url: str, timeout: int = 20):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body


def http_post_json(url: str, payload: dict, timeout: int = 30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return resp.status, body


def main() -> int:
    parser = argparse.ArgumentParser(description="Gemini API health + model smoke test")
    parser.add_argument("--api-key", default=os.getenv("GEMINI_API_KEY", ""), help="Gemini API key")
    parser.add_argument("--model", default="gemini-3-flash-preview", help="Model to test")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: provide --api-key or set GEMINI_API_KEY", file=sys.stderr)
        return 2

    key = args.api_key.strip()
    model = args.model.strip()
    enc_key = urllib.parse.quote_plus(key)
    base = "https://generativelanguage.googleapis.com/v1beta"

    print("== Gemini API Health Test ==")
    print(f"Model target: {model}")

    # 1) List models (health + auth check)
    models_url = f"{base}/models?key={enc_key}"
    try:
        status, body = http_get(models_url, timeout=20)
        print(f"[1/2] models.list status: {status}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[1/2] models.list HTTP error: {e.code}")
        print(err_body)
        return 1
    except Exception as e:
        print(f"[1/2] models.list failed: {e}")
        return 1

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print("[1/2] models.list returned non-JSON response")
        print(body[:500])
        return 1

    model_names = [m.get("name", "") for m in data.get("models", [])]
    has_target = any(name.endswith("/" + model) for name in model_names)
    print(f"[1/2] models returned: {len(model_names)}")
    print(f"[1/2] target model present: {'yes' if has_target else 'no'}")

    # 2) Generate content test
    gen_url = f"{base}/models/{model}:generateContent?key={enc_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Reply with exactly: GEMINI_OK"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0
        },
    }

    try:
        status, body = http_post_json(gen_url, payload, timeout=30)
        print(f"[2/2] generateContent status: {status}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[2/2] generateContent HTTP error: {e.code}")
        print(err_body)
        return 1
    except Exception as e:
        print(f"[2/2] generateContent failed: {e}")
        return 1

    try:
        resp = json.loads(body)
    except json.JSONDecodeError:
        print("[2/2] generateContent returned non-JSON response")
        print(body[:500])
        return 1

    text = ""
    try:
        text = resp["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        text = ""

    print(f"[2/2] response text: {text!r}")
    print("RESULT: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

