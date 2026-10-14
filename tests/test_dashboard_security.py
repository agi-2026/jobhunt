import unittest
import sys
from pathlib import Path

# Add workspace/scripts and dashboard to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "workspace" / "scripts"))
sys.path.append(str(REPO_ROOT / "dashboard"))

from queue_utils import is_safe_url
import server


class TestURLSecurity(unittest.TestCase):
    def test_safe_public_urls(self):
        safe, reason = is_safe_url("https://example.com/job/123")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

        safe, reason = is_safe_url("http://jobs.ashbyhq.com/company/12345")
        self.assertTrue(safe)

    def test_block_loopback_and_local(self):
        for url in [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
        ]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block loopback URL: {url}")

    def test_block_private_ips(self):
        for url in [
            "http://10.0.0.1/",
            "http://172.16.0.1/",
            "http://192.168.1.1/",
        ]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block private IP URL: {url}")

    def test_block_aws_metadata(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)

    def test_block_invalid_schemes(self):
        for url in [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
        ]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block non-http/https scheme: {url}")

    def test_dashboard_add_job_rejection(self):
        res = server.add_job("http://127.0.0.1:8765/admin")
        self.assertFalse(res["ok"])
        self.assertIn("Invalid or unsafe URL", res["error"])

        res = server.add_job("http://10.0.0.1/admin")
        self.assertFalse(res["ok"])
        self.assertIn("Invalid or unsafe URL", res["error"])


if __name__ == "__main__":
    unittest.main()
