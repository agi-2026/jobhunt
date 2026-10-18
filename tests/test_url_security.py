import unittest
import sys
from pathlib import Path

# Add scripts directory to path for imports
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe_urls = [
            "https://www.google.com",
            "https://jobs.ashbyhq.com/openai",
            "https://boards.greenhouse.io/stripe",
            "http://jobs.lever.co/airbnb",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_invalid_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")
            self.assertIn("Invalid scheme", reason)

    def test_loopback_and_internal_hostnames(self):
        unsafe_urls = [
            "http://localhost/admin",
            "http://127.0.0.1:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")

    def test_private_ip_ranges(self):
        unsafe_urls = [
            "http://10.0.0.1/status",
            "http://172.16.0.1/config",
            "http://192.168.1.1/router",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")

    def test_aws_metadata_and_link_local(self):
        unsafe_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.1.1",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")


if __name__ == "__main__":
    unittest.main()
