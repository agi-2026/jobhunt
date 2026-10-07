import os
import sys
import unittest

# Ensure workspace/scripts is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts")))

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe, reason = is_safe_url("https://jobs.ashbyhq.com/openai/123")
        self.assertTrue(safe, f"Expected public URL to be safe, got reason: {reason}")

        safe, reason = is_safe_url("https://boards.greenhouse.io/anthropic/jobs/4012345")
        self.assertTrue(safe, f"Expected public URL to be safe, got reason: {reason}")

        safe, reason = is_safe_url("http://www.google.com")
        self.assertTrue(safe, f"Expected public URL to be safe, got reason: {reason}")

    def test_invalid_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "dict://example.com",
            "javascript:alert(1)",
            "data:text/html,test",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be rejected due to scheme, but got safe")
            self.assertIn("Invalid scheme", reason)

    def test_loopback_addresses(self):
        loopback_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8000",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
        ]
        for url in loopback_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected loopback {url} to be blocked")

    def test_aws_metadata_and_link_local(self):
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.1.1",
        ]
        for url in metadata_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected link-local/metadata {url} to be blocked")
            self.assertIn("Link-local address blocked", reason)

    def test_private_ip_addresses(self):
        private_urls = [
            "http://10.0.0.1/admin",
            "http://172.16.0.1/status",
            "http://192.168.1.1/router",
        ]
        for url in private_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected private IP {url} to be blocked")
            self.assertIn("Private network address blocked", reason)


if __name__ == "__main__":
    unittest.main()
