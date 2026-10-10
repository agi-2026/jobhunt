import os
import sys
import unittest

# Ensure workspace/scripts is in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe, reason = is_safe_url("https://boards.greenhouse.io/test/jobs/123")
        self.assertTrue(safe, f"Expected safe URL, got reason: {reason}")

        safe, reason = is_safe_url("http://example.com")
        self.assertTrue(safe, f"Expected safe URL, got reason: {reason}")

    def test_loopback_urls_blocked(self):
        loopback_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8000",
            "http://0.0.0.0",
            "http://[::1]",
        ]
        for url in loopback_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected blocked loopback URL: {url}")

    def test_private_and_metadata_ips_blocked(self):
        unsafe_urls = [
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected blocked internal/metadata URL: {url}")

    def test_invalid_schemes_blocked(self):
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "javascript:alert(1)",
            "gopher://example.com",
        ]
        for url in invalid_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected blocked scheme: {url}")


if __name__ == "__main__":
    unittest.main()
