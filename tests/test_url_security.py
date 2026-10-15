import sys
import unittest
from pathlib import Path

# Add workspace/scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe, f"Expected safe URL but got: {reason}")

        safe, reason = is_safe_url("https://boards.greenhouse.io/test/jobs/123")
        self.assertTrue(safe, f"Expected safe URL but got: {reason}")

    def test_block_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8000",
            "http://0.0.0.0:3000",
            "http://[::1]:8080",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected blocked loopback/internal URL '{url}' but passed")
            self.assertIn("blocked", reason.lower())

    def test_block_private_ip_ranges(self):
        private_urls = [
            "http://10.0.0.1/admin",
            "http://172.16.0.1/status",
            "http://192.168.1.1/config",
        ]
        for url in private_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected blocked private IP URL '{url}' but passed")
            self.assertIn("blocked", reason.lower())

    def test_block_aws_metadata(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("blocked", reason.lower())

    def test_block_invalid_schemes(self):
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
        ]
        for url in invalid_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected blocked scheme URL '{url}' but passed")
            self.assertIn("scheme", reason.lower())


if __name__ == "__main__":
    unittest.main()
