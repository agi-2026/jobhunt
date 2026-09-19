import unittest
import sys
import os

# Ensure workspace/scripts is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts")))

from queue_utils import is_safe_url
import importlib.util

spec = importlib.util.spec_from_file_location(
    "preflight_check",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts", "preflight-check.py"))
)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestPreflightSecurity(unittest.TestCase):
    def test_is_safe_url_loopback(self):
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://0.0.0.0:8000"))

    def test_is_safe_url_private_ip(self):
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))

    def test_is_safe_url_cloud_metadata(self):
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_invalid_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))
        self.assertFalse(is_safe_url("gopher://example.com"))

    def test_is_safe_url_valid_public_urls(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/stripe/jobs/123"))

    def test_preflight_check_blocks_unsafe_url(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("blocked", reason)


if __name__ == "__main__":
    unittest.main()
