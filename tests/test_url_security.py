import os
import sys
import unittest
import importlib.util

# Add workspace/scripts to sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Helper to import hyphenated scripts
def import_script(name, filename):
    path = os.path.join(SCRIPTS_DIR, filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

preflight = import_script("preflight_check", "preflight-check.py")


class TestURLSecurity(unittest.TestCase):
    def test_valid_public_urls(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe)
        self.assertEqual(reason, "Safe URL")

        safe, reason = is_safe_url("http://example.com/job/123")
        self.assertTrue(safe)
        self.assertEqual(reason, "Safe URL")

    def test_unsupported_schemes(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Unsupported URL scheme", reason)

        safe, reason = is_safe_url("ftp://example.com/file")
        self.assertFalse(safe)
        self.assertIn("Unsupported URL scheme", reason)

    def test_loopback_and_internal_ips(self):
        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback/internal blocked", reason)

        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback/internal blocked", reason)

        safe, reason = is_safe_url("http://0.0.0.0/")
        self.assertFalse(safe)

    def test_private_and_link_local_ips(self):
        safe, reason = is_safe_url("http://10.0.0.1/")
        self.assertFalse(safe)
        self.assertIn("private IP blocked", reason)

        safe, reason = is_safe_url("http://172.16.0.1/")
        self.assertFalse(safe)
        self.assertIn("private IP blocked", reason)

        safe, reason = is_safe_url("http://192.168.1.1/")
        self.assertFalse(safe)
        self.assertIn("private IP blocked", reason)

        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("link-local blocked", reason)

    def test_preflight_check_ssrf_blocking(self):
        status, reason = preflight.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("loopback/internal blocked", reason)


if __name__ == "__main__":
    unittest.main()
