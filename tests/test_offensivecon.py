from __future__ import annotations

import unittest

from endorsement_scraper.assessors.offensivecon import parse_offensivecon


class OffensiveConParserTest(unittest.TestCase):
    def test_agenda_rows_emit_each_speaker_and_skip_logistics(self) -> None:
        html = """
        <main class="agenda">
          <div class="row row-agenda"><div>09:00 - 09:30</div><div>Opening Remarks by Host</div></div>
          <div class="row row-agenda"><div>10:00 - 11:00</div><div>Kernel Fuzzing by Alice Smith and Bob Jones</div><div><a href="speakers/2025/talk.html">Read more</a></div></div>
        </main>
        """
        rows = parse_offensivecon(html, "https://example.test/agenda/2025.html", 2025)
        self.assertEqual([row.name for row in rows], ["Alice Smith", "Bob Jones"])
        self.assertEqual(rows[0].title, "Kernel Fuzzing")
        self.assertEqual(rows[0].url, "https://example.test/agenda/speakers/2025/talk.html")

    def test_speaker_cards_keep_abstract_description(self) -> None:
        html = """
        <section><h4>Alice Smith</h4><h5>Finding Bugs</h5>
        <p>We describe a vulnerability discovery method.</p></section>
        """
        rows = parse_offensivecon(html, "https://example.test/speakers/2024/", 2024)
        self.assertEqual(len(rows), 1)
        self.assertIn("vulnerability discovery", rows[0].description)
