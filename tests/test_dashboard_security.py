import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../workspace/scripts")))
from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_safe_urls(self):
        safe_urls = [
            "https://jobs.lever.co/example/12345",
            "https://boards.greenhouse.io/example/jobs/67890",
            "https://jobs.ashbyhq.com/example/abc-def",
            "http://example.com/job",
        ]
        for url in safe_urls:
            with self.subTest(url=url):
                self.assertTrue(is_safe_url(url), f"Expected safe URL: {url}")

    def test_unsafe_urls(self):
        unsafe_urls = [
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "http://0.0.0.0:80",
            "http://[::1]:8080",
            "http://169.254.169.254/latest/meta-data/",
            "http://10.0.0.1/admin",
            "http://172.16.0.1/",
            "http://192.168.1.1/router",
            "file:///etc/passwd",
            "ftp://example.com/file",
            "gopher://example.com/",
            "javascript:alert(1)",
            "",
            "not_a_url",
        ]
        for url in unsafe_urls:
            with self.subTest(url=url):
                self.assertFalse(is_safe_url(url), f"Expected unsafe URL blocked: {url}")


if __name__ == "__main__":
    unittest.main()
