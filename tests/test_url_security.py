import os
import sys
import unittest
import subprocess

# Add workspace/scripts to path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):

    def test_safe_public_urls(self):
        safe, msg = is_safe_url("https://www.google.com")
        self.assertTrue(safe, f"Expected safe URL but got: {msg}")

        safe, msg = is_safe_url("http://jobs.lever.co/company/job-id")
        self.assertTrue(safe, f"Expected safe URL but got: {msg}")

    def test_loopback_blocked(self):
        safe, msg = is_safe_url("http://localhost:8765")
        self.assertFalse(safe)
        self.assertIn("loopback", msg.lower())

        safe, msg = is_safe_url("http://127.0.0.1:8765/api")
        self.assertFalse(safe)
        self.assertIn("loopback", msg.lower())

        safe, msg = is_safe_url("http://[::1]:8080")
        self.assertFalse(safe)

    def test_private_ip_blocked(self):
        safe, msg = is_safe_url("http://10.0.0.1/internal")
        self.assertFalse(safe)
        self.assertIn("private ip", msg.lower())

        safe, msg = is_safe_url("http://192.168.1.1/admin")
        self.assertFalse(safe)
        self.assertIn("private ip", msg.lower())

        safe, msg = is_safe_url("http://172.16.0.1/dashboard")
        self.assertFalse(safe)
        self.assertIn("private ip", msg.lower())

    def test_aws_metadata_blocked(self):
        safe, msg = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)

    def test_invalid_scheme_blocked(self):
        safe, msg = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("scheme", msg.lower())

        safe, msg = is_safe_url("ftp://example.com/file")
        self.assertFalse(safe)
        self.assertIn("scheme", msg.lower())

    def test_preflight_script_blocks_internal(self):
        preflight_script = os.path.join(SCRIPTS_DIR, "preflight-check.py")
        result = subprocess.run(
            ["python3", preflight_script, "http://127.0.0.1:8765"],
            capture_output=True,
            text=True
        )
        self.assertIn("DEAD", result.stdout)
        self.assertIn("loopback/internal blocked", result.stdout)


if __name__ == "__main__":
    unittest.main()
