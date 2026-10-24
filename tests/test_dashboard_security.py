import os
import sys
import unittest
from pathlib import Path

# Add scripts directory to path for imports
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

from queue_utils import is_safe_url


class TestDashboardSecurity(unittest.TestCase):
    def test_is_safe_url_valid_http(self):
        is_safe, msg = is_safe_url("https://jobs.lever.co/example/123")
        self.assertTrue(is_safe, f"Expected safe URL but got: {msg}")

    def test_is_safe_url_loopback_ip(self):
        is_safe, msg = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(is_safe)
        self.assertIn("loopback", msg.lower())

    def test_is_safe_url_localhost(self):
        is_safe, msg = is_safe_url("http://localhost:8765")
        self.assertFalse(is_safe)
        self.assertIn("loopback", msg.lower())

    def test_is_safe_url_private_ip(self):
        is_safe, msg = is_safe_url("http://10.0.0.1/")
        self.assertFalse(is_safe)
        self.assertIn("private", msg.lower())

    def test_is_safe_url_aws_metadata(self):
        is_safe, msg = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(is_safe)
        self.assertTrue("link-local" in msg.lower() or "private" in msg.lower())

    def test_is_safe_url_invalid_scheme(self):
        is_safe, msg = is_safe_url("file:///etc/passwd")
        self.assertFalse(is_safe)
        self.assertIn("scheme", msg.lower())


if __name__ == "__main__":
    unittest.main()
