import os
import sys
import unittest
import subprocess

# Ensure scripts directory is in python path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestIsSafeUrl(unittest.TestCase):
    def test_loopback_addresses(self):
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://0.0.0.0:8000"))

    def test_aws_metadata_and_link_local(self):
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_private_networks(self):
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("http://172.16.0.1"))
        self.assertFalse(is_safe_url("http://192.168.1.1"))

    def test_invalid_schemes(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://example.com/file"))
        self.assertFalse(is_safe_url("gopher://example.com"))

    def test_safe_public_url(self):
        self.assertTrue(is_safe_url("https://www.google.com"))


class TestPreflightCheckScript(unittest.TestCase):
    def test_preflight_blocks_loopback(self):
        script_path = os.path.join(SCRIPTS_DIR, "preflight-check.py")
        proc = subprocess.run(
            ["python3", script_path, "http://localhost:8765"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertIn("DEAD Invalid URL (loopback/internal blocked)", proc.stdout)


if __name__ == "__main__":
    unittest.main()
