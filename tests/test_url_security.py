import os
import sys
import unittest

# Ensure workspace/scripts is in sys.path
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):
    def test_safe_urls(self):
        safe_urls = [
            "https://jobs.ashbyhq.com/openai/123",
            "https://boards.greenhouse.io/google/jobs/456",
            "https://jobs.lever.co/stripe/789",
            "http://example.com/job",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_unsafe_schemes(self):
        unsafe_schemes = [
            "file:///etc/passwd",
            "gopher://localhost:70",
            "ftp://example.com/file",
            "data:text/html,<script>alert(1)</script>",
        ]
        for url in unsafe_schemes:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")

    def test_loopback_and_internal_ips(self):
        internal_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
            "http://10.0.0.1/admin",
            "http://172.16.0.1/status",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in internal_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked as unsafe")


if __name__ == "__main__":
    unittest.main()
