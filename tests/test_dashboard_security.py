#!/usr/bin/env python3
"""Unit tests for URL SSRF security checks in queue_utils.py."""

import unittest
import sys
from pathlib import Path

# Add workspace/scripts to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url


class TestDashboardSecurity(unittest.TestCase):
    def test_safe_urls(self):
        safe_urls = [
            "https://jobs.ashbyhq.com/example/123",
            "https://boards.greenhouse.io/company/jobs/456",
            "https://jobs.lever.co/company/789",
        ]
        for url in safe_urls:
            safe, reason = is_safe_url(url)
            self.assertTrue(safe, f"Expected {url} to be safe, but got: {reason}")

    def test_unsafe_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be blocked due to scheme")
            self.assertIn("Unsupported scheme", reason)

    def test_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
            "http://10.0.0.1/admin",
            "http://172.16.0.1/secret",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be blocked as unsafe internal IP/domain")


if __name__ == "__main__":
    unittest.main()
