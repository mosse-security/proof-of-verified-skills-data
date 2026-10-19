import unittest

from scrapers.assessors.black_hat import _speaker_names


class BlackHatParserTests(unittest.TestCase):
    def test_speaker_names_split_commas_and_remove_titles(self):
        self.assertEqual(
            _speaker_names("Rep. Alice Example, Bob Example"),
            ["Alice Example", "Bob Example"],
        )

    def test_speaker_names_remove_dr_title(self):
        self.assertEqual(_speaker_names("Dr. Silke Holtmanns"), ["Silke Holtmanns"])


if __name__ == "__main__":
    unittest.main()
