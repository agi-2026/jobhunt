import os
import sys
import unittest
from pathlib import Path

# Add workspace/scripts to python path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "workspace" / "scripts"))

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe_urls = [
            "https://jobs.ashbyhq.com/openai/123456",
            "https://boards.greenhouse.io/stripe/jobs/98765",
            "https://jobs.lever.co/airbnb/abcde",
            "https://www.google.com",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_unsafe_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be rejected due to scheme")

    def test_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://0.0.0.0:8080",
            "http://10.0.0.1/admin",
            "http://172.16.0.1/status",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked as internal/SSRF risk. Reason: {reason}")


if __name__ == "__main__":
    unittest.main()
