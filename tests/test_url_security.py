#!/usr/bin/env python3
"""Unit tests for URL safety validation and preflight check security."""

import sys
import os
import unittest
import importlib.util

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check module dynamically (hyphenated filename)
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        valid_urls = [
            "https://jobs.lever.co/example/123",
            "https://boards.greenhouse.io/company/jobs/456",
            "http://jobs.ashbyhq.com/company",
            "https://www.google.com",
        ]
        for url in valid_urls:
            safe, reason = is_safe_url(url)
            self.assertTrue(safe, f"Expected {url} to be safe, but got: {reason}")
            self.assertEqual(reason, "OK")

    def test_is_safe_url_blocked_schemes(self):
        blocked_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in blocked_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be blocked")
            self.assertIn("Unsupported scheme", reason)

    def test_is_safe_url_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8000",
            "http://0.0.0.0/",
            "http://[::1]/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected unsafe URL {url} to be blocked")

    def test_preflight_check_blocks_unsafe_url(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "file:///etc/passwd",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            status, reason = preflight_check.check_url(url)
            self.assertEqual(status, "DEAD", f"Expected DEAD status for {url}")
            self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
