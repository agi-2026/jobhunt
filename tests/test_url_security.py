import unittest
import sys
import os
import importlib.util
from pathlib import Path

# Add workspace/scripts to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url
import dashboard.server as server


class TestUrlSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        valid_urls = [
            "https://jobs.lever.co/google",
            "https://boards.greenhouse.io/stripe/jobs/12345",
            "https://jobs.ashbyhq.com/openai/67890",
            "https://www.google.com",
            "http://example.com/job",
        ]
        for url in valid_urls:
            with self.subTest(url=url):
                self.assertTrue(is_safe_url(url), f"Expected safe for: {url}")

    def test_is_safe_url_loopback_and_internal(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://0.0.0.0:80",
            "http://[::1]:8080",
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            with self.subTest(url=url):
                self.assertFalse(is_safe_url(url), f"Expected unsafe for: {url}")

    def test_is_safe_url_invalid_schemes(self):
        invalid_schemes = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
            "javascript:alert(1)",
            "data:text/html,test",
            "",
            None,
        ]
        for url in invalid_schemes:
            with self.subTest(url=url):
                self.assertFalse(is_safe_url(url), f"Expected unsafe for: {url}")

    def test_add_job_ssrf_blocking(self):
        response = server.add_job("http://127.0.0.1:8765/api/data")
        self.assertFalse(response["ok"])
        self.assertIn("Invalid or unsafe URL", response.get("error", ""))

        response_aws = server.add_job("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(response_aws["ok"])
        self.assertIn("Invalid or unsafe URL", response_aws.get("error", ""))

    def test_preflight_check_ssrf_blocking(self):
        spec = importlib.util.spec_from_file_location(
            "preflight_check", str(SCRIPTS_DIR / "preflight-check.py")
        )
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)

        status, reason = preflight.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
