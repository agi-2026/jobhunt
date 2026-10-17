#!/usr/bin/env python3
"""Unit tests for URL safety validation and preflight security controls."""

import importlib.util
import os
import sys
import unittest

# Ensure workspace/scripts is in python path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):

    def test_safe_public_url(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe, f"Expected safe URL, got reason: {reason}")
        self.assertEqual(reason, "URL is safe")

    def test_block_loopback_ip(self):
        safe, reason = is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", reason.lower())

    def test_block_localhost_name(self):
        safe, reason = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("localhost", reason.lower())

    def test_block_zero_address(self):
        safe, reason = is_safe_url("http://0.0.0.0")
        self.assertFalse(safe)
        self.assertIn("0.0.0.0", reason.lower())

    def test_block_aws_metadata(self):
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("link-local", reason.lower())

    def test_block_private_rfc1918(self):
        for private_url in [
            "http://10.0.0.1",
            "http://172.16.0.1",
            "http://192.168.1.1",
        ]:
            safe, reason = is_safe_url(private_url)
            self.assertFalse(safe, f"Should block private IP: {private_url}")
            self.assertIn("private", reason.lower())

    def test_block_invalid_scheme(self):
        for invalid_url in [
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com",
        ]:
            safe, reason = is_safe_url(invalid_url)
            self.assertFalse(safe, f"Should block scheme: {invalid_url}")
            self.assertIn("unsupported scheme", reason.lower())

    def test_preflight_script_integration(self):
        preflight_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
        spec = importlib.util.spec_from_file_location("preflight_check", preflight_path)
        preflight = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(preflight)

        status, reason = preflight.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
