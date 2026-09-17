import os
import sys
import unittest
import importlib.util

# Add workspace/scripts to sys.path so queue_utils can be imported
workspace_scripts = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if workspace_scripts not in sys.path:
    sys.path.insert(0, workspace_scripts)

from queue_utils import is_safe_url

# Import preflight-check.py using importlib because of hyphen in filename
preflight_path = os.path.join(workspace_scripts, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_module)


class TestUrlSecurity(unittest.TestCase):
    def test_is_safe_url_valid_http_and_https(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/example/123"))
        self.assertTrue(is_safe_url("http://boards.greenhouse.io/job/123"))

    def test_is_safe_url_blocks_loopback(self):
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://[::1]:8080"))

    def test_is_safe_url_blocks_private_and_link_local_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_blocks_unsupported_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("gopher://127.0.0.1:70"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))

    def test_preflight_check_blocks_unsafe_url(self):
        status, reason = preflight_module.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL (loopback/internal blocked)", reason)

        status, reason = preflight_module.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL (loopback/internal blocked)", reason)


if __name__ == "__main__":
    unittest.main()
