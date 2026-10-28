import os
import sys
import unittest
import importlib.util

# Add workspace/scripts to sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check module using spec since it contains a hyphen
preflight_spec = importlib.util.spec_from_file_location(
    "preflight_check", os.path.join(SCRIPTS_DIR, "preflight-check.py")
)
preflight_check = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight_check)


class TestUrlSecurity(unittest.TestCase):
    def test_is_safe_url_public(self):
        is_safe, msg = is_safe_url("https://www.google.com")
        self.assertTrue(is_safe)
        self.assertEqual(msg, "URL safety check passed")

    def test_is_safe_url_loopback(self):
        is_safe, msg = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(is_safe)
        self.assertIn("loopback/internal blocked", msg)

        is_safe_localhost, msg_localhost = is_safe_url("http://localhost:8765")
        self.assertFalse(is_safe_localhost)
        self.assertIn("loopback/internal blocked", msg_localhost)

    def test_is_safe_url_private_ip(self):
        is_safe, msg = is_safe_url("http://10.0.0.1/secret")
        self.assertFalse(is_safe)
        self.assertIn("private network blocked", msg)

        is_safe_192, msg_192 = is_safe_url("http://192.168.1.1/admin")
        self.assertFalse(is_safe_192)
        self.assertIn("private network blocked", msg_192)

    def test_is_safe_url_aws_metadata(self):
        is_safe, msg = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(is_safe)
        self.assertTrue("link-local blocked" in msg or "private network blocked" in msg)

    def test_is_safe_url_invalid_scheme(self):
        is_safe, msg = is_safe_url("file:///etc/passwd")
        self.assertFalse(is_safe)
        self.assertIn("Unsupported scheme", msg)

    def test_preflight_check_url_security(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("loopback/internal blocked", reason)

        status_file, reason_file = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status_file, "DEAD")
        self.assertIn("Unsupported scheme", reason_file)


if __name__ == "__main__":
    unittest.main()
