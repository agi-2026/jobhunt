import importlib.util
import os
import sys
import unittest
from pathlib import Path

# Append workspace/scripts to sys.path so queue_utils can be imported
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url

# Import preflight-check.py dynamically due to hyphen in filename
preflight_spec = importlib.util.spec_from_file_location("preflight_check", str(SCRIPTS_DIR / "preflight-check.py"))
preflight_module = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight_module)


class TestPreflightSecurity(unittest.TestCase):
    def test_is_safe_url_valid_public_urls(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe, f"Expected safe URL but got: {reason}")
        safe, reason = is_safe_url("https://jobs.lever.co/example/123")
        self.assertTrue(safe, f"Expected safe URL but got: {reason}")

    def test_is_safe_url_blocks_loopback(self):
        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason.lower())

        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason.lower())

    def test_is_safe_url_blocks_private_and_link_local(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("link-local", reason.lower())

        safe, reason = is_safe_url("http://10.0.0.1/admin")
        self.assertFalse(safe)
        self.assertIn("private", reason.lower())

        safe, reason = is_safe_url("http://192.168.1.1/admin")
        self.assertFalse(safe)
        self.assertIn("private", reason.lower())

    def test_is_safe_url_blocks_disallowed_schemes(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("invalid scheme", reason.lower())

        safe, reason = is_safe_url("gopher://localhost:70")
        self.assertFalse(safe)
        self.assertIn("invalid scheme", reason.lower())

    def test_preflight_check_blocks_unsafe_urls(self):
        status, reason = preflight_module.check_url("http://localhost:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_module.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_module.check_url("http://169.254.169.254/latest/meta-data/")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
