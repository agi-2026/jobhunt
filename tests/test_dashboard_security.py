import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_SCRIPTS = REPO_ROOT / "workspace" / "scripts"
DASHBOARD_DIR = REPO_ROOT / "dashboard"

for p in (WORKSPACE_SCRIPTS, DASHBOARD_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from queue_utils import is_safe_url
import server


class TestSSRFSecurity(unittest.TestCase):
    def test_is_safe_url_valid(self):
        is_safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(is_safe, f"Expected google.com to be safe, got: {reason}")

    def test_is_safe_url_loopback(self):
        for url in ["http://localhost:8765", "http://127.0.0.1:8765", "http://0.0.0.0:8080"]:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked")
            self.assertIn("loopback/internal blocked", reason)

    def test_is_safe_url_metadata_and_private(self):
        for url in ["http://169.254.169.254/latest/meta-data/", "http://10.0.0.1", "http://192.168.1.1"]:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked")

    def test_is_safe_url_invalid_scheme(self):
        for url in ["file:///etc/passwd", "gopher://localhost:70", "ftp://example.com"]:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked")
            self.assertIn("Only http and https are allowed", reason)

    def test_add_job_ssrf_blocked(self):
        res = server.add_job("http://localhost:8765")
        self.assertFalse(res["ok"])
        self.assertIn("Security restriction", res["error"])

        res2 = server.add_job("http://169.254.169.254")
        self.assertFalse(res2["ok"])
        self.assertIn("Security restriction", res2["error"])


if __name__ == "__main__":
    unittest.main()
