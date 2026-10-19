import os
import sys
import unittest
from pathlib import Path

# Add workspace/scripts to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url


class TestDashboardSecurity(unittest.TestCase):
    def test_is_safe_url_valid_http_https(self):
        safe, reason = is_safe_url("https://jobs.ashbyhq.com/example/123")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

        safe, reason = is_safe_url("http://boards.greenhouse.io/example/jobs/123")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_blocks_loopback(self):
        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback/internal blocked", reason)

        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback/internal blocked", reason)

    def test_is_safe_url_blocks_private_ip(self):
        safe, reason = is_safe_url("http://10.0.0.1/admin")
        self.assertFalse(safe)
        self.assertIn("private IP address blocked", reason)

        safe, reason = is_safe_url("http://192.168.1.100/status")
        self.assertFalse(safe)
        self.assertIn("private IP address blocked", reason)

    def test_is_safe_url_blocks_aws_metadata(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("link-local IP address blocked", reason)

    def test_is_safe_url_blocks_invalid_schemes(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Invalid scheme: file", reason)

        safe, reason = is_safe_url("ftp://example.com/file")
        self.assertFalse(safe)
        self.assertIn("Invalid scheme: ftp", reason)


if __name__ == "__main__":
    unittest.main()
