import unittest
import sys
import os
import importlib.util
from pathlib import Path

# Add workspace/scripts to sys.path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url

# Load preflight-check.py dynamically
preflight_spec = importlib.util.spec_from_file_location("preflight_check", SCRIPTS_DIR / "preflight-check.py")
preflight_module = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight_module)


class TestURLSecurity(unittest.TestCase):

    def test_safe_urls(self):
        safe, _ = is_safe_url("https://www.google.com")
        self.assertTrue(safe)

        safe, _ = is_safe_url("https://boards.greenhouse.io/stripe/jobs/12345")
        self.assertTrue(safe)

    def test_unsafe_schemes(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Unsupported scheme", reason)

        safe, reason = is_safe_url("ftp://example.com/file")
        self.assertFalse(safe)
        self.assertIn("Unsupported scheme", reason)

    def test_loopback_and_internal_ips(self):
        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason)

        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason)

        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("link-local", reason)

        safe, reason = is_safe_url("http://10.0.0.1/admin")
        self.assertFalse(safe)
        self.assertIn("private network", reason)

        safe, reason = is_safe_url("http://192.168.1.1/router")
        self.assertFalse(safe)
        self.assertIn("private network", reason)

    def test_preflight_check_integration(self):
        status, reason = preflight_module.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Unsupported scheme", reason)

        status, reason = preflight_module.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("loopback", reason)


if __name__ == "__main__":
    unittest.main()
