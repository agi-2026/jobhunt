import importlib.util
import os
import sys
import unittest

# Ensure workspace/scripts is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "workspace", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):
    def test_safe_urls(self):
        safe_urls = [
            "https://jobs.lever.co/example/123",
            "https://boards.greenhouse.io/example/jobs/456",
            "http://example.com/job",
        ]
        for url in safe_urls:
            safe, msg = is_safe_url(url)
            self.assertTrue(safe, f"Expected {url} to be safe, but got error: {msg}")

    def test_unsafe_schemes(self):
        unsafe_urls = [
            "file:///etc/passwd",
            "ftp://example.com/resource",
            "gopher://example.com",
            "javascript:alert(1)",
        ]
        for url in unsafe_urls:
            safe, msg = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be rejected due to unsafe scheme")
            self.assertIn("Invalid scheme", msg)

    def test_loopback_and_internal_ips(self):
        internal_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://127.0.0.1",
            "http://0.0.0.0",
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in internal_urls:
            safe, msg = is_safe_url(url)
            self.assertFalse(safe, f"Expected {url} to be blocked as unsafe/internal IP")
            self.assertIn("blocked", msg)

    def test_preflight_script_ssrf_blocking(self):
        # Dynamically import preflight-check.py
        preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
        spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)

        # Verify safe URL passes is_safe_url check
        safe, msg = preflight.is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", msg)


if __name__ == "__main__":
    unittest.main()
