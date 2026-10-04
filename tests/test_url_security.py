import importlib.util
import os
import sys
import unittest

# Ensure workspace/scripts is in path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check module dynamically due to hyphen in filename
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestUrlSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        safe_urls = [
            "https://boards.greenhouse.io/stripe/jobs/12345",
            "https://jobs.lever.co/anthropic/67890",
            "http://example.com/careers",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_is_safe_url_blocks_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8000",
            "http://0.0.0.0/",
            "http://[::1]/",
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked as unsafe")

    def test_is_safe_url_blocks_unsupported_schemes(self):
        bad_scheme_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com/",
            "javascript:alert(1)",
        ]
        for url in bad_scheme_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked due to unsupported scheme")

    def test_preflight_check_url_blocks_ssrf(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
