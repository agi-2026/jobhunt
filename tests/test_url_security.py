#!/usr/bin/env python3
"""Unit tests for URL safety validation and preflight check security."""

import importlib.util
import os
import sys
import unittest

# Add workspace/scripts to sys.path for queue_utils import
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url

# Import preflight-check.py dynamically due to hyphen in filename
PREFLIGHT_PATH = os.path.join(SCRIPTS_DIR, "preflight-check.py")
spec = importlib.util.spec_from_file_location("preflight_check", PREFLIGHT_PATH)
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_valid_http_https(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://boards.greenhouse.io/stripe/jobs/12345"))
        self.assertTrue(is_safe_url("http://jobs.lever.co/airbnb/12345"))

    def test_is_safe_url_blocks_loopback(self):
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1/"))
        self.assertFalse(is_safe_url("http://0.0.0.0:8000"))
        self.assertFalse(is_safe_url("http://[::1]/"))

    def test_is_safe_url_blocks_private_ips(self):
        self.assertFalse(is_safe_url("http://10.0.0.1/"))
        self.assertFalse(is_safe_url("http://172.16.0.1/"))
        self.assertFalse(is_safe_url("http://192.168.1.1/"))

    def test_is_safe_url_blocks_aws_metadata(self):
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_is_safe_url_blocks_non_http_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("gopher://127.0.0.1/"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))

    def test_preflight_check_blocks_loopback(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
