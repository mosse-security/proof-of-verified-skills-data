from __future__ import annotations

import unittest

from endorsement_scraper.assessors.grrcon import parse_grrcon


class GrrconParserTests(unittest.TestCase):
    def test_parses_speaker_title_and_description(self) -> None:
        html = """
        <html><body>
          <h2>Thursday Afternoon Keynote – Alex Example</h2>
          <h3>Defending the Blue Team</h3>
          <p>A detailed abstract about detection and response.</p>
          <h2>Jamie Tester</h2>
          <h3>Reverse Engineering 101</h3>
          <p>Reverse engineering fundamentals.</p>
        </body></html>
        """
        rows = parse_grrcon(html, "https://grrcon.com/presentations2022/")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], "Defending the Blue Team")
        self.assertEqual(rows[0][1], "Alex Example")
        self.assertIn("detection and response", rows[0][2])
        self.assertEqual(rows[0][3], 2022)

    def test_2024_layout_has_title_before_speaker(self) -> None:
        rows = parse_grrcon(
            "<h2>Defending Cloud Workloads</h2><h3>Jordan Example</h3><p>Cloud defense.</p>",
            "https://grrcon.com/presentations24/",
        )
        self.assertEqual(rows[0][0], "Defending Cloud Workloads")
        self.assertEqual(rows[0][1], "Jordan Example")
        self.assertEqual(rows[0][3], 2024)


if __name__ == "__main__":
    unittest.main()
