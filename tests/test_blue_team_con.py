import unittest

from scrapers.assessors.blue_team_con import parse_blue_team_con


class BlueTeamConParserTest(unittest.TestCase):
    def test_parses_multiple_presenters_and_detail_link(self):
        html = """
        <div><h2><a href='/directory/talk/'>Defensive Detection</a></h2>
        <p>Presented by Alice Example &amp; Bob Example</p></div>
        """
        rows = parse_blue_team_con(html, "https://blueteamcon.com/btc-history/talks-blue-team-con-2025/")
        self.assertEqual([row.name for row in rows], ["Alice Example", "Bob Example"])
        self.assertEqual(rows[0].title, "Defensive Detection")
        self.assertEqual(rows[0].year, 2025)
        self.assertEqual(rows[0].url, "https://blueteamcon.com/directory/talk/")


if __name__ == "__main__":
    unittest.main()
