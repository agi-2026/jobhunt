import os
import sys
import unittest

# Add workspace/scripts and dashboard to path
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "workspace", "scripts")
DASHBOARD_DIR = os.path.join(ROOT_DIR, "dashboard")

for p in (SCRIPTS_DIR, DASHBOARD_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import server


class TestDashboardSecurity(unittest.TestCase):
    def test_add_job_ssrf_blocking(self):
        unsafe_urls = [
            "http://127.0.0.1:8765",
            "http://localhost:8765/api/data",
            "http://169.254.169.254/latest/meta-data/",
            "file:///etc/passwd",
        ]
        for url in unsafe_urls:
            res = server.add_job(url, destination="queue")
            self.assertFalse(res["ok"], f"Expected {url} to be rejected")
            self.assertIn("Invalid URL", res.get("error", ""))

    def test_sanitization_helpers(self):
        dirty_title = "Senior Engineer\nRole | Admin — Hack\r"
        clean_title = server.sanitize_field(dirty_title)
        self.assertNotIn("\n", clean_title)
        self.assertNotIn("\r", clean_title)
        self.assertNotIn("|", clean_title)
        self.assertNotIn("—", clean_title)

        dirty_url = "https://example.com/job\r\n/path"
        clean_url = server.sanitize_url(dirty_url)
        self.assertNotIn("\r", clean_url)
        self.assertNotIn("\n", clean_url)


if __name__ == "__main__":
    unittest.main()
