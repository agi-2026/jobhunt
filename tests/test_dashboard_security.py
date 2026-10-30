#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

# Add workspace/scripts to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "workspace" / "scripts"))

from queue_utils import is_safe_url


class TestDashboardSecurity(unittest.TestCase):
    def test_safe_public_url(self):
        is_safe, reason = is_safe_url("https://jobs.ashbyhq.com/example/123")
        self.assertTrue(is_safe)
        self.assertEqual(reason, "URL is safe")

    def test_loopback_and_internal_ip(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Should block unsafe URL: {url}")
            self.assertIn("loopback/internal blocked", reason)

    def test_private_ip_ranges(self):
        private_urls = [
            "http://10.0.0.1/admin",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
        ]
        for url in private_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Should block private IP: {url}")
            self.assertIn("private IP blocked", reason)

    def test_aws_metadata_ip(self):
        url = "http://169.254.169.254/latest/meta-data/"
        is_safe, reason = is_safe_url(url)
        self.assertFalse(is_safe)
        self.assertIn("link-local blocked", reason)

    def test_invalid_and_unsupported_schemes(self):
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "",
            None,
        ]
        for url in invalid_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Should reject invalid/unsupported URL: {url}")


if __name__ == "__main__":
    unittest.main()
