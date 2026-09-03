#!/usr/bin/env python3
"""Unit tests for URL safety logic and preflight SSRF protection."""

import importlib.util
import os
import sys
import unittest

SYS_PATH = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(SYS_PATH, "..", "workspace", "scripts")
sys.path.append(SCRIPTS_DIR)

from queue_utils import is_safe_url

spec = importlib.util.spec_from_file_location(
    "preflight_check", os.path.join(SCRIPTS_DIR, "preflight-check.py")
)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_valid(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/example/123"))

    def test_is_safe_url_blocked(self):
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://[::1]:8765"))
        self.assertFalse(is_safe_url("http://10.0.0.1/admin"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com"))

    def test_preflight_check_ssrf(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status_file, reason_file = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status_file, "DEAD")
        self.assertIn("Invalid URL", reason_file)


if __name__ == "__main__":
    unittest.main()
