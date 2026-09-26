#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_SCRIPTS = REPO_ROOT / "workspace" / "scripts"
if str(WORKSPACE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_SCRIPTS))

from queue_utils import is_safe_url


class TestDashboardSecurity(unittest.TestCase):

    def test_safe_public_urls(self):
        safe_urls = [
            "https://jobs.lever.co/company/123",
            "https://boards.greenhouse.io/company/jobs/456",
            "https://jobs.ashbyhq.com/company/789",
            "https://www.google.com",
            "http://example.com/job",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, but got: {reason}")

    def test_loopback_urls_blocked(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked, but was allowed: {reason}")

    def test_link_local_metadata_blocked(self):
        unsafe_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.169.254/",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked, but was allowed: {reason}")

    def test_private_ips_blocked(self):
        private_urls = [
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
        ]
        for url in private_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked, but was allowed: {reason}")

    def test_unsupported_schemes_blocked(self):
        bad_scheme_urls = [
            "file:///etc/passwd",
            "ftp://example.com/resource",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in bad_scheme_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked, but was allowed: {reason}")

    def test_invalid_and_empty_inputs(self):
        invalid_inputs = ["", "   ", None, "http://", "not_a_url"]
        for inp in invalid_inputs:
            is_safe, reason = is_safe_url(inp)
            self.assertFalse(is_safe, f"Expected input '{inp}' to be invalid")


if __name__ == "__main__":
    unittest.main()
