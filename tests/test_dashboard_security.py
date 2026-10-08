import importlib.util
import os
import sys
import unittest
from pathlib import Path

# Add workspace/scripts and repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_SCRIPTS = REPO_ROOT / "workspace" / "scripts"
DASHBOARD_DIR = REPO_ROOT / "dashboard"

if str(WORKSPACE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_SCRIPTS))
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from queue_utils import is_safe_url
import server as dashboard_server

# Import preflight-check dynamically due to hyphen in filename
preflight_path = WORKSPACE_SCRIPTS / "preflight-check.py"
spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestDashboardSecurity(unittest.TestCase):

    def test_is_safe_url_public(self):
        safe, reason = is_safe_url("https://jobs.ashbyhq.com/openai/123")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_loopback(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8000",
            "http://[::1]:8080",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be unsafe")
            self.assertIn("loopback", reason)

    def test_is_safe_url_private_ip(self):
        unsafe_urls = [
            "http://10.0.0.1/admin",
            "http://172.16.0.1/secret",
            "http://192.168.1.1/router",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be unsafe")
            self.assertIn("private IP network blocked", reason)

    def test_is_safe_url_aws_metadata(self):
        url = "http://169.254.169.254/latest/meta-data/"
        safe, reason = is_safe_url(url)
        self.assertFalse(safe)
        self.assertIn("link-local/metadata blocked", reason)

    def test_is_safe_url_invalid_scheme(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be unsafe")
            self.assertIn("Invalid URL scheme", reason)

    def test_add_job_ssrf_blocked(self):
        res = dashboard_server.add_job("http://127.0.0.1:8765/api/data")
        self.assertFalse(res["ok"])
        self.assertIn("Invalid URL", res["error"])

    def test_preflight_check_ssrf_blocked(self):
        status, reason = preflight_check.check_url("http://localhost:8000/internal")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
