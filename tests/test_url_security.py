import unittest
import sys
import subprocess
from pathlib import Path

# Add workspace scripts to Python path
sys.path.append(str(Path(__file__).resolve().parent.parent / "workspace" / "scripts"))
from queue_utils import is_safe_url


class TestURLSecurity(unittest.TestCase):
    def test_is_safe_url_public(self):
        safe, reason = is_safe_url("https://jobs.ashbyhq.com/openai")
        self.assertTrue(safe)
        self.assertEqual(reason, "URL is safe")

    def test_is_safe_url_loopback(self):
        for url in ["http://localhost:8765", "http://127.0.0.1:8765", "http://[::1]:8080"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block {url}")
            self.assertIn("Loopback", reason)

    def test_is_safe_url_private_ip(self):
        for url in ["http://10.0.0.1/admin", "http://192.168.1.1/router", "http://172.16.0.1/status"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block {url}")
            self.assertIn("Private network", reason)

    def test_is_safe_url_link_local(self):
        url = "http://169.254.169.254/latest/meta-data/"
        safe, reason = is_safe_url(url)
        self.assertFalse(safe, f"Should block AWS metadata endpoint {url}")
        self.assertIn("Link-local", reason)

    def test_is_safe_url_invalid_schemes(self):
        for url in ["file:///etc/passwd", "gopher://localhost:70", "ftp://127.0.0.1/file"]:
            safe, reason = is_safe_url(url)
            self.assertFalse(safe, f"Should block non-http/https scheme in {url}")
            self.assertIn("Invalid scheme", reason)

    def test_preflight_script_ssrf_blocking(self):
        script_path = Path(__file__).resolve().parent.parent / "workspace" / "scripts" / "preflight-check.py"
        res = subprocess.run(
            ["python3", str(script_path), "http://localhost:8765"],
            capture_output=True,
            text=True,
        )
        self.assertTrue(res.stdout.startswith("DEAD"))
        self.assertIn("Invalid URL", res.stdout)


if __name__ == "__main__":
    unittest.main()
