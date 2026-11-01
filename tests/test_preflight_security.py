import importlib.util
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Dynamically load preflight-check module
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestPreflightSecurity(unittest.TestCase):
    def test_is_safe_url_public_domains(self):
        safe, reason = is_safe_url("https://example.com")
        self.assertTrue(safe)
        self.assertEqual(reason, "OK")

        safe, reason = is_safe_url("https://jobs.ashbyhq.com/openai/test-id")
        self.assertTrue(safe)
        self.assertEqual(reason, "OK")

    def test_is_safe_url_invalid_scheme(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Invalid scheme", reason)

        safe, reason = is_safe_url("ftp://example.com/test")
        self.assertFalse(safe)
        self.assertIn("Invalid scheme", reason)

        safe, reason = is_safe_url("")
        self.assertFalse(safe)
        self.assertIn("Empty or invalid URL", reason)

    def test_is_safe_url_loopback_and_metadata(self):
        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertTrue("loopback" in reason.lower())

        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertTrue("loopback" in reason.lower())

        safe, reason = is_safe_url("http://[::1]:8765")
        self.assertFalse(safe)
        self.assertTrue("loopback" in reason.lower())

        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertTrue("link-local" in reason.lower())

    def test_is_safe_url_private_networks(self):
        for ip in ("10.0.0.1", "172.16.0.1", "192.168.1.1"):
            safe, reason = is_safe_url(f"http://{ip}/admin")
            self.assertFalse(safe)
            self.assertTrue("private" in reason.lower())

    def test_preflight_check_blocks_unsafe_urls(self):
        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("http://169.254.169.254")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
