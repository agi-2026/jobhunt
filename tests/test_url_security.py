#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

# Add workspace/scripts to python path
SCRIPTS_DIR = Path(__file__).parent.parent / "workspace" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from queue_utils import is_safe_url
import importlib.util

spec = importlib.util.spec_from_file_location("preflight_check", str(SCRIPTS_DIR / "preflight-check.py"))
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_valid_http_https(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

        safe, reason = is_safe_url("http://example.com/job/123")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_disallowed_schemes(self):
        for url in ["file:///etc/passwd", "ftp://example.com/file", "gopher://example.com", "javascript:alert(1)"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe)
            self.assertIn("only http/https allowed", reason)

    def test_is_safe_url_loopback_and_internal_ips(self):
        unsafe_urls = [
            "http://127.0.0.1/admin",
            "http://localhost:8765",
            "http://[::1]/",
            "http://10.0.0.1/secret",
            "http://172.16.0.1/",
            "http://192.168.1.1/router",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block unsafe URL: {url}")
            self.assertTrue(
                any(b in reason for b in ["Blocked loopback", "Blocked link-local", "Blocked private network"]),
                f"Unexpected failure reason for {url}: {reason}"
            )

    def test_preflight_check_blocks_unsafe_urls(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)

        status, reason = preflight_check.check_url("file:///etc/passwd")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
