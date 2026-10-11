from __future__ import annotations

import unittest

from endorsement_scraper.assessors.insomnihack import parse_insomnihack


class InsomnihackParserTest(unittest.TestCase):
    def test_talk_section_extracts_speakers_and_abstract(self) -> None:
        html = """
        <h2>Breaking the Sandbox</h2>
        <p>Speakers: Alice Smith &amp; Bob Jones</p>
        <p>SPEAKER BIO</p><p>Researcher biographies.</p>
        <p>ABSTRACT</p><p>We explain a browser sandbox escape and mitigation.</p>
        """
        rows = parse_insomnihack(html, "https://example.test/edition-2024/talks/", 2024)
        self.assertEqual([row.name for row in rows], ["Alice Smith", "Bob Jones"])
        self.assertIn("sandbox escape", rows[0].description)

    def test_current_homepage_navigation_is_not_an_endorsement(self) -> None:
        html = "<h2>About the event</h2><h1>Swiss CyberSecurity Conference</h1><h2>Organized by</h2>"
        self.assertEqual(parse_insomnihack(html, "https://example.test/edition-2024/talks/", 2024), [])

    def test_agenda_does_not_turn_schedule_time_into_person(self) -> None:
        html = """
        <h3>Thursday, March 13th</h3>
        <table><tr><th>Time</th><th>TRACK</th></tr>
        <tr><td>16:30</td><td>COFFEE</td></tr>
        <tr><td>17:00</td><td>Breaking Things by Jane Doe</td></tr></table>
        """
        rows = parse_insomnihack(html, "https://example.test/edition-2025/talks/", 2025)
        self.assertEqual([(row.name, row.title) for row in rows], [("Jane Doe", "Breaking Things")])

    def test_by_inside_title_is_not_treated_as_speaker_prefix(self) -> None:
        html = """
        <table><tr><th>Time</th><th>Track</th></tr>
        <tr><td>09:00</td><td>(KEYNOTE) Baffled By Bloated Complexity by Mathias Payer</td></tr>
        <tr><td>16:00</td><td>Security by Design: Reality vs Expectations Julien Patriarca, Wallix</td></tr>
        </table>
        """
        rows = parse_insomnihack(html, "https://example.test/edition-2025/talks/", 2025)
        self.assertEqual([row.name for row in rows], ["Mathias Payer", "Julien Patriarca"])
