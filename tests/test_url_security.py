import unittest
import sys
from pathlib import Path
import importlib.util

# Ensure workspace/scripts is in sys.path so queue_utils can be imported
workspace_scripts = Path(__file__).parent.parent / "workspace" / "scripts"
if str(workspace_scripts) not in sys.path:
    sys.path.insert(0, str(workspace_scripts))

from queue_utils import is_safe_url

# Load preflight-check module dynamically due to hyphenated filename
preflight_path = workspace_scripts / "preflight-check.py"
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_module)


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/test"))
        self.assertTrue(is_safe_url("http://jobs.lever.co/company/123"))

    def test_is_safe_url_blocks_loopback(self):
        self.assertFalse(is_safe_url("http://127.0.0.1/"))
        self.assertFalse(is_safe_url("http://localhost:8000"))
        self.assertFalse(is_safe_url("http://[::1]/"))

    def test_is_safe_url_blocks_private_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1/"))
        self.assertFalse(is_safe_url("http://172.16.0.1/"))
        self.assertFalse(is_safe_url("http://192.168.1.1/"))

    def test_is_safe_url_blocks_aws_metadata(self):
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_blocks_invalid_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("gopher://localhost:70"))
        self.assertFalse(is_safe_url("ftp://example.com"))

    def test_preflight_check_blocks_unsafe_url(self):
        status, reason = preflight_module.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("loopback/internal blocked", reason)

        status, reason = preflight_module.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("loopback/internal blocked", reason)


if __name__ == "__main__":
    unittest.main()
