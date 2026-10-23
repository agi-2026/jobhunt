import unittest
import sys
import os
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts")))
from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe_urls = [
            "https://jobs.ashbyhq.com/openai/12345",
            "https://boards.greenhouse.io/stripe/jobs/67890",
            "https://jobs.lever.co/anthropic/abcde",
            "http://example.com/job",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected safe URL: {url}, got: {reason}")

    def test_unsafe_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/resource",
            "gopher://127.0.0.1/",
            "data:text/plain;base64,SGVsbG8=",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected unsafe URL scheme: {url}")

    def test_loopback_and_private_ips(self):
        blocked_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765",
            "http://10.0.0.1/admin",
            "http://172.16.0.1/internal",
            "http://192.168.1.1/config",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]:8080/",
        ]
        for url in blocked_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected blocked internal URL: {url}")

    def test_preflight_check_cli_blocks_unsafe(self):
        preflight_script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts", "preflight-check.py")
        )
        proc = subprocess.run(
            ["python3", preflight_script, "http://127.0.0.1:8765"],
            capture_output=True,
            text=True,
        )
        self.assertIn("DEAD", proc.stdout)
        self.assertIn("Invalid URL", proc.stdout)


if __name__ == "__main__":
    unittest.main()
