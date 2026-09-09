import sys
import os
import unittest
import importlib.util

# Add workspace/scripts to sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check.py dynamically due to hyphen in filename
preflight_spec = importlib.util.spec_from_file_location(
    "preflight_check", os.path.join(SCRIPTS_DIR, "preflight-check.py")
)
preflight_module = importlib.util.module_from_spec(preflight_spec)
preflight_spec.loader.exec_module(preflight_module)


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_http_https(self):
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/openai/12345"))
        self.assertTrue(is_safe_url("http://boards.greenhouse.io/stripe/jobs/67890"))

    def test_is_safe_url_blocks_loopback(self):
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://localhost:8000"))
        self.assertFalse(is_safe_url("http://[::1]:8080"))

    def test_is_safe_url_blocks_private_and_link_local_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))
        self.assertFalse(is_safe_url("http://169.254.169.254"))  # AWS metadata endpoint

    def test_is_safe_url_blocks_non_http_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))
        self.assertFalse(is_safe_url("gopher://example.com"))

    def test_preflight_check_url_ssrf_blocking(self):
        status, reason = preflight_module.check_url("http://localhost:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("blocked", reason.lower())

        status, reason = preflight_module.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("blocked", reason.lower())


if __name__ == "__main__":
    unittest.main()
