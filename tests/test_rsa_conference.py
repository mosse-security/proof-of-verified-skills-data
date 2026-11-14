from __future__ import annotations

import unittest

from scrapers.assessors.rsa_conference import parse_rsa, rsa_year


class RsaConferenceParserTests(unittest.TestCase):
    def test_rainfocus_catalog_extracts_session_speakers(self) -> None:
        html = """
        <article class="session-card">
          <a href="/flow/rsac/us26/FullAgenda/page/catalog/session/abc">Securing Agentic AI Systems</a>
          <div class="session-speakers">Alice Smith<br>Bob Jones</div>
          <p>Practical controls for protecting autonomous systems.</p>
        </article>
        """
        rows = parse_rsa(html, "https://path.rsaconference.com/flow/rsac/us26/FullAgenda/page/catalog")
        self.assertEqual([row.name for row in rows], ["Alice Smith", "Bob Jones"])
        self.assertEqual(rows[0].title, "Securing Agentic AI Systems")
        self.assertIn("Practical controls", rows[0].description)

    def test_legacy_agenda_table_extracts_speakers(self) -> None:
        html = """
        <table><tr><th>Time</th><th>Session</th><th>Speakers</th></tr>
        <tr><td>8:30</td><td>Modern Cloud Defense Strategies</td>
        <td>Speakers: Carol White and Dan Brown</td></tr></table>
        """
        rows = parse_rsa(html, "https://www.rsaconference.com/events/2022-cryptography/agenda/full-agenda")
        self.assertEqual([row.name for row in rows], ["Carol White", "Dan Brown"])
        self.assertEqual(rows[0].year, 2022)

    def test_year_supports_short_event_codes(self) -> None:
        self.assertEqual(rsa_year("https://path.rsaconference.com/flow/rsac/us25/speakers/page/Conference"), 2025)


if __name__ == "__main__":
    unittest.main()
