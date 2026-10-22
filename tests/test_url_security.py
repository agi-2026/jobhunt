import os
import sys
import unittest
import importlib.util

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check script dynamically due to hyphenated filename
preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_module)


class TestURLSecurity(unittest.TestCase):

    def test_safe_public_urls(self):
        safe_urls = [
            "https://jobs.ashbyhq.com/openai/123456",
            "https://boards.greenhouse.io/stripe/jobs/987654",
            "https://jobs.lever.co/anthropic/abcdef",
            "http://example.com/careers/job",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, but got: {reason}")

    def test_unsafe_urls(self):
        unsafe_urls = [
            ("http://localhost:8765", "loopback"),
            ("http://127.0.0.1:8080", "loopback"),
            ("http://0.0.0.0:3000", "loopback"),
            ("http://[::1]/admin", "loopback"),
            ("http://10.0.0.1/internal", "private network"),
            ("http://192.168.1.1/router", "private network"),
            ("http://172.16.0.1/secret", "private network"),
            ("http://169.254.169.254/latest/meta-data/", "link-local"),
            ("file:///etc/passwd", "scheme"),
            ("gopher://127.0.0.1", "scheme"),
            ("ftp://127.0.0.1/file", "scheme"),
        ]
        for url, expected_keyword in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be unsafe")

    def test_preflight_check_blocks_unsafe(self):
        status, reason = preflight_module.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
