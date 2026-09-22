import importlib.util
import os
import sys
import unittest

# Import queue_utils from workspace/scripts
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check module via spec_from_file_location
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestUrlSecurity(unittest.TestCase):
    def test_is_safe_url_valid_public_urls(self):
        valid_urls = [
            "https://jobs.ashbyhq.com/example/123",
            "https://boards.greenhouse.io/example/jobs/456",
            "https://jobs.lever.co/example/789",
        ]
        for url in valid_urls:
            safe, reason = is_safe_url(url)
            self.assertTrue(safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_is_safe_url_blocked_schemes(self):
        invalid_schemes = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in invalid_schemes:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected scheme for {url} to be rejected")
            self.assertIn("Unsupported scheme", reason)

    def test_is_safe_url_loopback_and_private(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected unsafe URL {url} to be blocked")

    def test_preflight_check_ssrf_blocking(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
