import unittest
import sys
from pathlib import Path
import importlib.util

# Ensure workspace/scripts is in python path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url

# Import preflight-check.py dynamically due to hyphen in filename
preflight_path = SCRIPTS_DIR / "preflight-check.py"
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestPreflightSecurity(unittest.TestCase):
    def test_is_safe_url_valid_public_urls(self):
        safe, reason = is_safe_url("https://boards-api.greenhouse.io/v1/boards/stripe/jobs")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

        safe, reason = is_safe_url("https://jobs.ashbyhq.com/openai/123456")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_loopback_and_private_ips(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
            "http://10.0.0.1/admin",
            "http://172.16.0.1/internal",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be marked unsafe, but got safe")

    def test_is_safe_url_invalid_schemes(self):
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in invalid_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} scheme to be unsafe")

    def test_preflight_check_blocks_unsafe_url(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
