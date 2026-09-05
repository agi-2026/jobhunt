import unittest
import sys
from pathlib import Path
import importlib.util

ROOT_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_SCRIPTS = ROOT_DIR / "workspace" / "scripts"

if str(WORKSPACE_SCRIPTS) not in sys.path:
    sys.path.append(str(WORKSPACE_SCRIPTS))

from queue_utils import is_safe_url

spec = importlib.util.spec_from_file_location("preflight_check", WORKSPACE_SCRIPTS / "preflight-check.py")
preflight_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight_check)


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_public(self):
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("https://jobs.ashbyhq.com/example/123"))

    def test_is_safe_url_blocked(self):
        self.assertFalse(is_safe_url("http://localhost:8765"))
        self.assertFalse(is_safe_url("http://127.0.0.1:8765"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))
        self.assertFalse(is_safe_url("http://10.0.0.1"))
        self.assertFalse(is_safe_url("file:///etc/passwd"))

    def test_preflight_check_blocks_unsafe_urls(self):
        status, reason = preflight_check.check_url("http://127.0.0.1:8765")
        self.assertEqual(status, "DEAD")
        self.assertIn("Invalid URL", reason)


if __name__ == "__main__":
    unittest.main()
