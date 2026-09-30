import unittest
import sys
from pathlib import Path

# Add scripts directory to path
repo_root = Path(__file__).resolve().parent.parent
sys.path.append(str(repo_root / "workspace" / "scripts"))

from queue_utils import is_safe_url


class TestUrlSecurity(unittest.TestCase):
    def test_valid_public_urls(self):
        safe, reason = is_safe_url("https://www.google.com")
        self.assertTrue(safe, f"Expected safe for google.com but got: {reason}")

        safe, reason = is_safe_url("http://boards.greenhouse.io/company/jobs/12345")
        self.assertTrue(safe, f"Expected safe for greenhouse URL but got: {reason}")

    def test_blocked_schemes(self):
        safe, reason = is_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("Invalid URL scheme", reason)

        safe, reason = is_safe_url("ftp://example.com")
        self.assertFalse(safe)
        self.assertIn("Invalid URL scheme", reason)

    def test_blocked_loopback_hostnames(self):
        for host in ["localhost", "127.0.0.1", "0.0.0.0", "[::1]"]:
            safe, reason = is_safe_url(f"http://{host}:8765")
            self.assertFalse(safe)
            self.assertIn("blocked", reason.lower())

    def test_blocked_private_and_link_local_ips(self):
        # Private IPs
        for ip in ["10.0.0.1", "172.16.0.1", "192.168.1.1"]:
            safe, reason = is_safe_url(f"http://{ip}/admin")
            self.assertFalse(safe)
            self.assertIn("blocked", reason.lower())

        # Link-local / AWS IMDS
        safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("blocked", reason.lower())


if __name__ == "__main__":
    unittest.main()
