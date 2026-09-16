import sys
import os
import unittest
import importlib.util

# Ensure workspace/scripts is in sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check module (hyphenated name)
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestPreflightSecurity(unittest.TestCase):

    def test_is_safe_url_valid_http_https(self):
        """Test that public valid http/https URLs are considered safe."""
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("http://jobs.ashbyhq.com/openai"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/stripe"))

    def test_is_safe_url_blocks_loopback(self):
        """Test that loopback addresses are blocked."""
        self.assertFalse(is_safe_url("http://127.0.0.1"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://localhost"))
        self.assertFalse(is_safe_url("http://localhost:8000"))
        self.assertFalse(is_safe_url("http://[::1]"))

    def test_is_safe_url_blocks_private_and_link_local(self):
        """Test that private IPs and cloud metadata IP addresses are blocked."""
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://169.254.169.254"))  # AWS metadata

    def test_is_safe_url_blocks_invalid_schemes(self):
        """Test that non-http/https schemes are blocked."""
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com"))
        self.assertFalse(is_safe_url("gopher://example.com"))

    def test_preflight_check_blocks_unsafe_urls(self):
        """Test that preflight-check.py returns DEAD for unsafe SSRF URLs."""
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
