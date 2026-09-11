#!/usr/bin/env python3
"""Unit tests for URL safety checks and SSRF prevention."""

import os
import sys
import unittest
import importlib.util

# Add workspace/scripts to sys.path to import queue_utils
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Load preflight-check.py dynamically
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        valid_urls = [
            "https://boards.greenhouse.io/stripe/jobs/123",
            "https://jobs.lever.co/example/456",
            "https://jobs.ashbyhq.com/acme/789",
            "https://www.google.com",
            "http://example.com/test",
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(is_safe_url(url), f"Expected {url} to be safe")

    def test_is_safe_url_loopback_and_private_ips(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1",
            "http://127.0.0.1:8080/admin",
            "http://0.0.0.0",
            "http://10.0.0.1/secret",
            "http://172.16.0.1",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]:8080",
        ]
        for url in unsafe_urls:
            with self.subTest(url=url):
                self.assertFalse(is_safe_url(url), f"Expected {url} to be blocked as unsafe")

    def test_is_safe_url_invalid_schemes_and_malformed(self):
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
            "not_a_url",
            "",
            None,
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                self.assertFalse(is_safe_url(url), f"Expected {url} to be invalid/blocked")

    def test_preflight_check_blocks_loopback(self):
        status, reason = preflight.check_url("http://localhost:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("blocked", reason.lower())


if __name__ == "__main__":
    unittest.main()
