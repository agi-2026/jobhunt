#!/usr/bin/env python3
"""Canonical browser-tool schema menu for apply subagents.

Keeps tool invocation syntax explicit so smaller models do not invent invalid
action names.
"""

from __future__ import annotations

import argparse
import json
import sys


MENU = {
    "browser_actions": {
        "navigate": {
            "action": "navigate",
            "required": ["targetUrl", "profile"],
            "example": {"action": "navigate", "targetUrl": "<url>", "profile": "<ats-profile>"},
        },
        "snapshot": {
            "action": "snapshot",
            "required": ["profile"],
            "example": {"action": "snapshot", "profile": "<ats-profile>"},
        },
        "evaluate": {
            "action": "act",
            "required": ["request.kind=evaluate", "request.fn", "profile"],
            "example": {
                "action": "act",
                "profile": "<ats-profile>",
                "request": {"kind": "evaluate", "fn": "<full_js_source>"},
            },
        },
        "click": {
            "action": "act",
            "required": ["request.kind=click", "request.ref|request.selector|request.x+y", "profile"],
            "example": {
                "action": "act",
                "profile": "<ats-profile>",
                "request": {"kind": "click", "ref": "<ref>"},
            },
        },
        "type": {
            "action": "act",
            "required": ["request.kind=type", "request.ref|request.selector", "request.text", "profile"],
            "example": {
                "action": "act",
                "profile": "<ats-profile>",
                "request": {"kind": "type", "ref": "<ref>", "text": "<value>"},
            },
        },
        "upload": {
            "action": "upload",
            "required": ["paths", "element|ref|inputRef", "profile"],
            "example": {
                "action": "upload",
                "profile": "<ats-profile>",
                "paths": ["/tmp/openclaw/uploads/Resume_Howard.pdf"],
                "element": "input[type=file]",
            },
        },
    },
    "invalid_patterns": [
        "action=evaluate (invalid)",
        "action=act with top-level kind/ref/text/paths (invalid for act; use action=act + request={...})",
        "action=act with request.kind=upload (invalid; use action=upload with top-level paths + element/ref/inputRef)",
        "action=click (invalid for browser tool schema; use action=act + request.kind=click)",
        "request.script for evaluate calls (invalid on this gateway; use request.fn)",
        "running .js files via python",
        "editing repo files during apply runs",
    ],
    "allowed_tools_for_apply_subagent": ["exec", "browser", "process"],
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Print canonical browser-tool action menu")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--profile", default="", help="Optional ATS profile hint")
    args = parser.parse_args()

    out = dict(MENU)
    if args.profile:
        out["profile_hint"] = args.profile

    if args.json:
        print(json.dumps(out, ensure_ascii=True, indent=2))
        return 0

    print("BROWSER TOOL MENU")
    if args.profile:
        print(f"Profile hint: {args.profile}")
    print("")
    for name, spec in out["browser_actions"].items():
        required = ", ".join(spec["required"])
        action = spec["action"]
        req = spec.get("example", {}).get("request", {})
        req_kind = req.get("kind") if isinstance(req, dict) else ""
        req_kind_text = f", request.kind={req_kind}" if req_kind else ""
        print(f"- {name}: action={action}{req_kind_text}; required: {required}")
    print("")
    print("INVALID PATTERNS")
    for p in out["invalid_patterns"]:
        print(f"- {p}")
    print("")
    print("ALLOWED TOOLS")
    print("- " + ", ".join(out["allowed_tools_for_apply_subagent"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
