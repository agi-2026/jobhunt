#!/usr/bin/env python3
import importlib.util
import os
import sys
import unittest

# Add workspace/scripts to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Dynamically import preflight-check.py
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class TestURLSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe_urls = [
            "https://www.google.com",
            "https://jobs.lever.co/example/123",
            "http://boards.greenhouse.io/company/jobs/456",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected safe URL to pass: {url} ({reason})")

    def test_unsafe_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected unsafe scheme to fail: {url}")
            status, msg = preflight.check_url(url)
            self.assertEqual(status, "DEAD")
            self.assertIn("Invalid URL", msg)

    def test_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://0.0.0.0:80",
            "http://10.0.0.1/admin",
            "http://192.168.1.1/router",
            "http://172.16.0.1",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected internal/loopback URL to fail: {url}")
            status, msg = preflight.check_url(url)
            self.assertEqual(status, "DEAD")
            self.assertIn("Invalid URL", msg)


if __name__ == "__main__":
    unittest.main()
