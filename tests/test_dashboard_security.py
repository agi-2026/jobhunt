import unittest
import sys
import os
from pathlib import Path

# Ensure workspace/scripts and dashboard are on path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "workspace" / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "dashboard"))

from queue_utils import is_safe_url
import server


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/company/job-123"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/company/jobs/456"))
        self.assertTrue(is_safe_url("http://example.com/test"))

    def test_is_safe_url_blocks_loopback(self):
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://0.0.0.0:8000"))
        self.assertFalse(is_safe_url("http://[::1]:8080"))

    def test_is_safe_url_blocks_private_and_metadata_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1/admin"))
        self.assertFalse(is_safe_url("http://192.168.1.1/setup"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_blocks_invalid_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))
        self.assertFalse(is_safe_url("gopher://example.com"))
        self.assertFalse(is_safe_url("javascript:alert(1)"))

    def test_add_job_ssrf_prevention(self):
        res = server.add_job("http://localhost:8765/api/data")
        self.assertFalse(res["ok"])
        self.assertIn("unsafe", res["error"].lower())

        res_meta = server.add_job("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(res_meta["ok"])
        self.assertIn("unsafe", res_meta["error"].lower())


if __name__ == "__main__":
    unittest.main()
