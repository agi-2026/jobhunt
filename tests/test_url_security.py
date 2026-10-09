#!/usr/bin/env python3
"""Unit tests for URL safety logic and preflight checks."""

import os
import sys
import unittest
import subprocess

# Add workspace/scripts to sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_public_urls(self):
        valid_urls = [
            "https://jobs.ashbyhq.com/stripe/12345",
            "https://boards.greenhouse.io/openai/jobs/67890",
            "https://jobs.lever.co/figma/abcde",
            "http://example.com/job/1",
        ]
        for url in valid_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected {url} to be safe, got reason: {reason}")
            self.assertEqual(reason, "OK")

    def test_is_safe_url_blocks_loopback(self):
        loopback_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8765/api/data",
            "http://0.0.0.0:8000",
            "http://[::1]:8080",
        ]
        for url in loopback_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked")
            self.assertIn("blocked", reason.lower())

    def test_is_safe_url_blocks_private_and_metadata_ips(self):
        unsafe_urls = [
            "http://10.0.0.1/admin",
            "http://192.168.1.100/config",
            "http://172.16.0.1/",
            "http://169.254.169.254/latest/meta-data/",
        ]
        for url in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked")
            self.assertIn("blocked", reason.lower())

    def test_is_safe_url_blocks_invalid_schemes(self):
        invalid_scheme_urls = [
            "file:///etc/passwd",
            "gopher://127.0.0.1",
            "ftp://example.com/file",
            "data:text/html,hello",
        ]
        for url in invalid_scheme_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected {url} to be blocked due to scheme")
            self.assertIn("scheme", reason.lower())

    def test_preflight_script_blocks_unsafe_url(self):
        preflight_script = os.path.join(SCRIPTS_DIR, "preflight-check.py")
        proc = subprocess.run(
            ["python3", preflight_script, "http://127.0.0.1:8765"],
            capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0)
        output = proc.stdout.strip()
        self.assertTrue(output.startswith("DEAD"), f"Expected DEAD status, got: {output}")
        self.assertIn("blocked", output.lower())


if __name__ == "__main__":
    unittest.main()
