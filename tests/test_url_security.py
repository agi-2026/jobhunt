import sys
import os
import unittest
import importlib.util

# Add workspace/scripts to sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check module dynamically due to hyphenated name
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_public_domains(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/test/jobs/123"))

    def test_is_safe_url_loopback(self):
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://localhost:8080"))
        self.assertFalse(is_safe_url("http://0.0.0.0:80"))

    def test_is_safe_url_private_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))

    def test_is_safe_url_aws_metadata(self):
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_invalid_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url(None))

    def test_preflight_check_blocks_unsafe_urls(self):
        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status_loopback, reason_loopback = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status_loopback, "DEAD")
        self.assertIn("Invalid URL", reason_loopback)


if __name__ == "__main__":
    unittest.main()
