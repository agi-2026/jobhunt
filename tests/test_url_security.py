import sys
import unittest
import importlib.util
from pathlib import Path

scripts_dir = Path(__file__).parent.parent / "workspace" / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from queue_utils import is_safe_url

# Import preflight-check.py dynamically
preflight_path = scripts_dir / "preflight-check.py"
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_valid_public(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe)
        self.assertEqual(reason, "Safe")

    def test_is_safe_url_loopback(self):
        for url in ["http://127.0.0.1:8765", "http://localhost", "http://[::1]"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)
            self.assertIn("loopback", reason.lower())

    def test_is_safe_url_private_and_metadata(self):
        for url in [
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data/",
        ]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)

    def test_is_safe_url_invalid_schemes(self):
        for url in ["file:///etc/passwd", "ftp://example.com", "gopher://example.com"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)
            self.assertIn("scheme", reason.lower())

    def test_preflight_check_url_security(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
