import os
import sys
import unittest
from pathlib import Path

# Add workspace/scripts and dashboard to import path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from queue_utils import is_safe_url
import server


class TestDashboardSecurity(unittest.TestCase):
    def test_is_safe_url_valid(self):
        safe_urls = [
            "https://jobs.lever.co/example/123",
            "https://boards.greenhouse.io/example/jobs/456",
            "http://example.com/job",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")

    def test_is_safe_url_unsafe(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8080",
            "http://0.0.0.0:8000",
            "http://[::1]/",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/admin",
            "http://192.168.1.1/",
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked as unsafe")

    def test_add_job_ssrf_blocked(self):
        res = server.add_job("http://127.0.0.1:8765/secret")
        self.assertFalse(res["ok"])
        self.assertIn("Invalid URL safety check", res["error"])

        res2 = server.add_job("file:///etc/hosts")
        self.assertFalse(res2["ok"])
        self.assertIn("Invalid URL safety check", res2["error"])


if __name__ == "__main__":
    unittest.main()
