import unittest
import importlib.util
from pathlib import Path

# Import queue_utils
from workspace.scripts.queue_utils import is_safe_url

# Import preflight-check script dynamically due to hyphen in filename
PREFLIGHT_PATH = Path(__file__).resolve().parent.parent / "workspace" / "scripts" / "preflight-check.py"
spec = importlib.util.spec_from_file_location("preflight_check", PREFLIGHT_PATH)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


class TestPreflightSecurity(unittest.TestCase):

    def test_is_safe_url_public_https(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_loopback_domain(self):
        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason.lower())

    def test_is_safe_url_loopback_ip(self):
        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason.lower())

    def test_is_safe_url_aws_metadata(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data")
        self.assertFalse(safe)
        self.assertIn("link-local", reason.lower())

    def test_is_safe_url_private_ip(self):
        safe, reason = is_safe_url("http://10.0.0.1")
        self.assertFalse(safe)
        self.assertIn("private network", reason.lower())

    def test_is_safe_url_unsupported_scheme(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("unsupported scheme", reason.lower())

    def test_preflight_check_url_blocks_unsafe(self):
        status, reason = preflight.check_url("http://localhost:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
