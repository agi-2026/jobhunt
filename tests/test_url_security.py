import os
import sys
import unittest
from pathlib import Path

# Ensure workspace/scripts is in path for imports
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "workspace" / "scripts"))

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe_urls = [
            "https://jobs.ashbyhq.com/openai/12345",
            "https://boards.greenhouse.io/anthropic/jobs/67890",
            "https://jobs.lever.co/scale/abcde",
            "http://example.com/careers",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_unsafe_loopback_urls(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1/admin",
            "http://0.0.0.0/",
            "http://[::1]:8080/metrics",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")

    def test_unsafe_private_and_imds_urls(self):
        unsafe_urls = [
            "http://169.254.169.254/latest/meta-data",
            "http://10.0.0.1/secret",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")

    def test_unsafe_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com/",
            "javascript:alert(1)",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe scheme")


if __name__ == "__main__":
    unittest.main()
