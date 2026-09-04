import os
import sys
import unittest
from pathlib import Path

# Add workspace/scripts and dashboard to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "workspace" / "scripts"
DASHBOARD_DIR = REPO_ROOT / "dashboard"

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(DASHBOARD_DIR))

from queue_utils import is_safe_url
from server import add_job


class TestDashboardSecurity(unittest.TestCase):
    def test_is_safe_url_valid_urls(self):
        self.assertTrue(is_safe_url("https://jobs.lever.co/company/job123"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/company/jobs/123"))
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/company/123"))
        self.assertTrue(is_safe_url("http://example.com/job"))

    def test_is_safe_url_ssrf_and_invalid(self):
        # Loopback
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://0.0.0.0:80"))
        self.assertFalse(is_safe_url("http://[::1]:8080"))

        # Private / Link Local IP addresses
        self.assertFalse(is_safe_url("http://10.0.0.1/admin"))
        self.assertFalse(is_safe_url("http://172.16.0.1/internal"))
        self.assertFalse(is_safe_url("http://192.168.1.1/router"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

        # Non-http/https schemes
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("gopher://localhost:70"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))

    def test_add_job_ssrf_blocked(self):
        res_loopback = add_job("http://localhost:8765")
        self.assertFalse(res_loopback["ok"])
        self.assertIn("SSRF protection", res_loopback["error"])

        res_metadata = add_job("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(res_metadata["ok"])
        self.assertIn("SSRF protection", res_metadata["error"])

        res_file = add_job("file:///etc/passwd")
        self.assertFalse(res_file["ok"])
        self.assertIn("SSRF protection", res_file["error"])


if __name__ == "__main__":
    unittest.main()
