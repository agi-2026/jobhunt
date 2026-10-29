#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_SCRIPTS = REPO_ROOT / "workspace" / "scripts"
DASHBOARD_DIR = REPO_ROOT / "dashboard"

sys.path.insert(0, str(WORKSPACE_SCRIPTS))
sys.path.insert(0, str(DASHBOARD_DIR))

from queue_utils import is_safe_url
from server import add_job


class TestDashboardSecurity(unittest.TestCase):
    def test_is_safe_url_public(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_loopback(self):
        for url in ["http://localhost:8765", "http://127.0.0.1:8765", "http://[::1]:8080"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)
            self.assertIn("blocked", reason.lower())

    def test_is_safe_url_private_ip(self):
        for url in ["http://10.0.0.1", "http://192.168.1.1", "http://172.16.0.1"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)
            self.assertIn("blocked", reason.lower())

    def test_is_safe_url_aws_metadata(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("blocked", reason.lower())

    def test_is_safe_url_unsupported_scheme(self):
        for url in ["file:///etc/passwd", "gopher://127.0.0.1", "ftp://example.com"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)
            self.assertIn("unsupported scheme", reason.lower())

    def test_add_job_ssrf_blocking(self):
        result = add_job("http://127.0.0.1:8765")
        self.assertFalse(result["ok"])
        self.assertIn("unsafe", result["error"].lower())


if __name__ == "__main__":
    unittest.main()
