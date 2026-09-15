#!/usr/bin/env python3
"""Unit tests for URL safety and SSRF prevention in JobHunt scripts."""

import os
import sys
import unittest
import subprocess

# Ensure workspace/scripts is in sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_valid(self):
        safe, msg = is_safe_url("https://jobs.ashbyhq.com/openai")
        self.assertTrue(safe, f"Expected safe URL but got: {msg}")

        safe, msg = is_safe_url("https://boards.greenhouse.io/anthropic")
        self.assertTrue(safe, f"Expected safe URL but got: {msg}")

    def test_is_safe_url_loopback(self):
        safe, msg = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", msg.lower())

        safe, msg = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", msg.lower())

    def test_is_safe_url_link_local(self):
        safe, msg = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("link-local", msg.lower())

    def test_is_safe_url_private(self):
        safe, msg = is_safe_url("http://10.0.0.1")
        self.assertFalse(safe)
        self.assertIn("private", msg.lower())

        safe, msg = is_safe_url("http://192.168.1.1")
        self.assertFalse(safe)
        self.assertIn("private", msg.lower())

    def test_is_safe_url_invalid_scheme(self):
        safe, msg = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("scheme", msg.lower())

        safe, msg = is_safe_url("gopher://127.0.0.1")
        self.assertFalse(safe)
        self.assertIn("scheme", msg.lower())

    def test_preflight_script_blocks_ssrf(self):
        script_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
        proc = subprocess.run(
            [sys.executable, script_path, "http://127.0.0.1:8765"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("DEAD", proc.stdout)
        self.assertIn("loopback/internal blocked", proc.stdout)


if __name__ == "__main__":
    unittest.main()
