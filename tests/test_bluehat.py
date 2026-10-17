import unittest

from scrapers.assessors.bluehat import _names, parse_bluehat


class BlueHatParserTest(unittest.TestCase):
    def test_table_uses_speaker_not_time_or_company(self):
        html = """
        <table><tr><th>TRACK</th><th>Time</th><th>Speaker</th><th>Company</th><th>Talk Subject</th></tr>
        <tr><td>Track</td><td>10:00</td><td>Alban Diquet Thomas Sileo</td><td>Data Theorem</td><td>SSL research</td></tr>
        <tr><td>10:30</td><td>Joseph Salowey</td><td>Tableau Software</td><td>TLS research</td></tr></table>
        """
        rows = parse_bluehat(html, "https://example.test/2017")
        self.assertEqual([row.name for row in rows], ["Alban Diquet", "Thomas Sileo", "Joseph Salowey"])
        self.assertNotIn("10:30", [row.name for row in rows])
        self.assertNotIn("Tableau Software", [row.name for row in rows])

    def test_heading_speakers_strip_roles_and_affiliations(self):
        self.assertEqual(
            _names("Dr. Abhilasha Bhargav-Spantzel - Partner Security Architect; David Weston - Vice President, Enterprise and OS Security"),
            ["Dr. Abhilasha Bhargav-Spantzel", "David Weston"],
        )
