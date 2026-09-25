import unittest
import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
QUEUE_UTILS_PATH = REPO_ROOT / "workspace" / "scripts" / "queue_utils.py"
PREFLIGHT_PATH = REPO_ROOT / "workspace" / "scripts" / "preflight-check.py"

spec_qu = importlib.util.spec_from_file_location("queue_utils", QUEUE_UTILS_PATH)
queue_utils = importlib.util.module_from_spec(spec_qu)
spec_qu.loader.exec_module(queue_utils)

spec_pf = importlib.util.spec_from_file_location("preflight_check", PREFLIGHT_PATH)
preflight_check = importlib.util.module_from_spec(spec_pf)
spec_pf.loader.exec_module(preflight_check)


class TestUrlSecurity(unittest.TestCase):
    def test_is_safe_url_valid_public_url(self):
        is_safe, reason = queue_utils.is_safe_url("https://www.google.com")
        self.assertTrue(is_safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_loopback_ipv4(self):
        is_safe, reason = queue_utils.is_safe_url("http://127.0.0.1:8765")
        self.assertFalse(is_safe)
        self.assertIn("Loopback address blocked", reason)

    def test_is_safe_url_loopback_hostname(self):
        is_safe, reason = queue_utils.is_safe_url("http://localhost:8765")
        self.assertFalse(is_safe)
        self.assertIn("Loopback address blocked", reason)

    def test_is_safe_url_private_ip(self):
        is_safe, reason = queue_utils.is_safe_url("http://10.0.0.1/admin")
        self.assertFalse(is_safe)
        self.assertIn("Private address blocked", reason)

    def test_is_safe_url_aws_metadata(self):
        is_safe, reason = queue_utils.is_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(is_safe)
        self.assertIn("address blocked", reason)

    def test_is_safe_url_invalid_scheme(self):
        is_safe, reason = queue_utils.is_safe_url("file:///etc/passwd")
        self.assertFalse(is_safe)
        self.assertIn("Unsupported URL scheme", reason)

    def test_preflight_check_blocks_loopback(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
