import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARD_DIR = os.path.join(REPO_ROOT, "dashboard")
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)

from server import add_job, canonicalize_url


class TestDashboardSecurity(unittest.TestCase):
    def test_canonicalize_url(self):
        self.assertEqual(canonicalize_url("https://example.com/job/123/"), "https://example.com/job/123")
        self.assertEqual(canonicalize_url("https://example.com/job/123/application"), "https://example.com/job/123")
        self.assertEqual(canonicalize_url(""), "")

    def test_add_job_ssrf_protection(self):
        res = add_job("http://localhost:8765")
        self.assertFalse(res["ok"])
        self.assertIn("Invalid URL", res["error"])

        res = add_job("http://169.254.169.254")
        self.assertFalse(res["ok"])
        self.assertIn("Invalid URL", res["error"])

        res = add_job("file:///etc/passwd")
        self.assertFalse(res["ok"])


if __name__ == "__main__":
    unittest.main()
