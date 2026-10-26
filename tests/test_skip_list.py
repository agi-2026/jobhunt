import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from dashboard import server


class TestSkipListSanitization(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.skip_file = Path(self.temp_dir.name) / "skip-companies.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sanitize_input_str(self):
        self.assertEqual(server._sanitize_input_str("  Acme Corp  "), "Acme Corp")
        self.assertEqual(server._sanitize_input_str("<b>Acme</b>\n\rTech\t"), "Acme Tech")
        self.assertEqual(server._sanitize_input_str("<script>alert(1)</script>Inc"), "alert(1)Inc")

    def test_add_to_skip_list_sanitization_and_category_validation(self):
        with patch.object(server, "SKIP_LIST_FILE", self.skip_file):
            res = server.add_to_skip_list(" <b> EvilCorp </b>\n ", "<script>bad</script>Reason", "INVALID_CAT")
            self.assertTrue(res["ok"])
            self.assertEqual(res["message"], "Added EvilCorp to skip list")

            # Verify saved json structure
            with open(self.skip_file, "r") as f:
                data = json.load(f)

            self.assertEqual(len(data["companies"]), 1)
            entry = data["companies"][0]
            self.assertEqual(entry["name"], "EvilCorp")
            self.assertEqual(entry["reason"], "badReason")
            self.assertEqual(entry["category"], "manual")  # Fallback to manual for invalid category

    def test_add_to_skip_list_duplicate(self):
        with patch.object(server, "SKIP_LIST_FILE", self.skip_file):
            server.add_to_skip_list("Acme", "Reason 1", "csp")
            res = server.add_to_skip_list("acme", "Reason 2", "csp")

            self.assertFalse(res["ok"])
            self.assertIn("already in skip list", res["error"])

    def test_remove_from_skip_list(self):
        with patch.object(server, "SKIP_LIST_FILE", self.skip_file):
            server.add_to_skip_list("Acme", "Reason", "csp")
            res = server.remove_from_skip_list("<b>Acme</b>\n")
            self.assertTrue(res["ok"])

            with open(self.skip_file, "r") as f:
                data = json.load(f)
            self.assertEqual(len(data["companies"]), 0)


if __name__ == "__main__":
    unittest.main()
