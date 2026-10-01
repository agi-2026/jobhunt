import os
import sys
import unittest
import importlib.util

# Add workspace/scripts directory to Python path for queue_utils import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts")))

from queue_utils import is_safe_url

# Import search-vc-boards dynamically
vc_boards_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "workspace", "scripts", "search-vc-boards.py"))
spec = importlib.util.spec_from_file_location("search_vc_boards", vc_boards_path)
search_vc_boards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(search_vc_boards)


class TestURLSecurity(unittest.TestCase):

    def test_is_safe_url_valid_urls(self):
        safe_urls = [
            "https://www.google.com",
            "http://example.com/jobs",
            "https://jobs.lever.co/company/123",
        ]
        for url in safe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertTrue(is_safe, f"Expected safe for '{url}', got unsafe reason: {reason}")

    def test_is_safe_url_unsafe_urls(self):
        unsafe_urls = [
            ("http://127.0.0.1/admin", "loopback"),
            ("http://localhost:8080", "loopback"),
            ("file:///etc/passwd", "scheme"),
            ("http://169.254.169.254/latest/meta-data", "link-local"),
            ("http://10.0.0.1/internal", "private"),
            ("http://192.168.1.1/router", "private"),
            ("ftp://example.com/file", "scheme"),
        ]
        for url, tag in unsafe_urls:
            is_safe, reason = is_safe_url(url)
            self.assertFalse(is_safe, f"Expected unsafe for '{url}' ({tag})")

    def test_search_vc_boards_fetch_text_blocks_unsafe_url(self):
        unsafe_url = "http://127.0.0.1:8765/api/data"
        with self.assertRaises(ValueError) as ctx:
            search_vc_boards.fetch_text(unsafe_url)
        self.assertIn("Blocked unsafe URL", str(ctx.exception))

    def test_search_vc_boards_post_json_blocks_unsafe_url(self):
        unsafe_url = "http://10.0.0.1:8000/api"
        with self.assertRaises(ValueError) as ctx:
            search_vc_boards.post_json(unsafe_url, {"test": "payload"})
        self.assertIn("Blocked unsafe URL", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
