import os
import sys
import unittest
import importlib.util

# Ensure workspace/scripts is in sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
scripts_dir = os.path.join(repo_root, "workspace", "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_public_urls(self):
        """Valid public http/https URLs should pass safety checks."""
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/openai"))
        self.assertTrue(is_safe_url("http://example.com/job/123"))

    def test_is_safe_url_blocks_loopback(self):
        """Loopback IP and localhost URLs should be blocked."""
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://0.0.0.0"))

    def test_is_safe_url_blocks_private_and_metadata(self):
        """Private network IPs and AWS cloud metadata endpoint should be blocked."""
        self.assertFalse(is_safe_url("http://10.0.0.1/admin"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_blocks_invalid_schemes(self):
        """Non-HTTP/HTTPS schemes like file:// or gopher:// should be blocked."""
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("gopher://127.0.0.1:70"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))

    def test_preflight_check_blocks_unsafe_urls(self):
        """preflight-check module should report DEAD for unsafe URLs."""
        preflight_path = os.path.join(scripts_dir, "preflight-check.py")
        spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)

        status, reason = preflight.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("blocked", reason.lower())


if __name__ == "__main__":
    unittest.main()
