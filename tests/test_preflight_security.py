import unittest
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PREFLIGHT_PATH = REPO_ROOT / "workspace" / "scripts" / "preflight-check.py"

spec = importlib.util.spec_from_file_location("preflight_check", PREFLIGHT_PATH)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestPreflightSecurity(unittest.TestCase):

    def test_is_safe_url(self):
        self.assertFalse(preflight_check.is_safe_url("http://localhost:8765"))
        self.assertFalse(preflight_check.is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(preflight_check.is_safe_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(preflight_check.is_safe_url("file:///etc/passwd"))
        self.assertFalse(preflight_check.is_safe_url("http://10.0.0.1"))
        self.assertFalse(preflight_check.is_safe_url("http://192.168.1.1"))
        self.assertTrue(preflight_check.is_safe_url("https://www.google.com"))

    def test_check_url_ssrf_blocked(self):
        status, reason = preflight_check.check_url("http://localhost:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("loopback/internal blocked", reason)


if __name__ == "__main__":
    unittest.main()
