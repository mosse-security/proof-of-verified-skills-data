import json
import tempfile
import unittest
from pathlib import Path

from scrapers.assessors.black_hat import _speaker_names, merge_black_hat_images, parse_black_hat_page


class BlackHatParserTests(unittest.TestCase):
    def test_speaker_names_split_commas_and_remove_titles(self):
        self.assertEqual(
            _speaker_names("Rep. Alice Example, Bob Example"),
            ["Alice Example", "Bob Example"],
        )

    def test_speaker_names_remove_dr_title(self):
        self.assertEqual(_speaker_names("Dr. Silke Holtmanns"), ["Silke Holtmanns"])

    def test_modern_parser_keeps_image_only_when_nested_in_speaker_node(self):
        rows = parse_black_hat_page(
            """
            <div class="data-container">
              <div class="session-title">A safe talk</div>
              <div class="session-speakers">
                <a class="speaker_link" href="speakers.html#alice-1">
                  <img src="/sites/default/files/alice.jpg" alt="Alice Example">
                  Alice Example
                </a>
              </div>
            </div>
            """,
            "https://blackhat.example/briefings/schedule",
            2024,
            "usa",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].image_url, "https://blackhat.example/sites/default/files/alice.jpg")
        self.assertEqual(rows[0].image_source_url, "https://blackhat.example/briefings/schedule")

    def test_modern_parser_does_not_pair_speaker_with_unrelated_image(self):
        rows = parse_black_hat_page(
            """
            <div class="data-container">
              <div class="session-title">A safe talk</div>
              <div class="session-speakers">
                <a class="speaker_link" href="speakers.html#alice-1">
                  <img src="/logo.png" alt="Black Hat logo">
                  Alice Example
                </a>
              </div>
            </div>
            """,
            "https://blackhat.example/briefings/schedule",
            2024,
            "usa",
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].image_url)

    def test_image_merges_into_existing_contact_record_without_creating_files(self):
        rows = parse_black_hat_page(
            """
            <div class="data-container">
              <div class="session-title">A safe talk</div>
              <div class="session-speakers">
                <a class="speaker_link" href="speakers.html#alice-1">
                  <img src="/people/alice.jpg" alt="Alice Example">
                  Alice Example
                </a>
              </div>
            </div>
            """,
            "https://blackhat.example/briefings/schedule",
            2024,
            "usa",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "alice-example.json").write_text(
                json.dumps({"name": "Alice Example", "contact": []}),
                encoding="utf-8",
            )
            changed = merge_black_hat_images(rows, root, 2024, "usa", verified_at="2026-11-20T00:00:00Z")
            self.assertEqual(changed, 1)
            document = json.loads((root / "alice-example.json").read_text(encoding="utf-8"))
            self.assertEqual(document["image"]["conference"], "Black Hat")
            self.assertEqual(document["image"]["verified"], True)
            self.assertEqual(list(root.glob("*.json")), [root / "alice-example.json"])


if __name__ == "__main__":
    unittest.main()
