import unittest

from scrapers.assessors.derbycon import _clean_person_name, _split_names, parse_derbycon


class DerbyConParserTests(unittest.TestCase):
    def test_cleans_aliases_credentials_and_metadata(self):
        self.assertEqual(_clean_person_name('Luis "Connection" Santana'), "Luis Santana")
        self.assertEqual(_clean_person_name("Christian Dameff MD MS"), "Christian Dameff")
        self.assertEqual(_clean_person_name("Sean Metcalf TBD"), "Sean Metcalf")

    def test_splits_joined_speakers_but_rejects_title_fragments(self):
        self.assertEqual(_split_names("Tom McBee, Jeff McCutchan"), ["Tom McBee", "Jeff McCutchan"])
        self.assertEqual(_split_names("Easy Passwords = Easy Break-Ins"), [])
        self.assertEqual(_split_names("8:30 - 8:55"), [])
        self.assertEqual(_split_names("Opening Ceremonies"), [])

    def test_colon_separates_speaker_from_title(self):
        html = b'''<a class="sched-event" title="Kellep Charles: Security Vulnerability Assessments - Workshop"></a>'''
        rows = parse_derbycon(html, "https://www.derbycon.com/friday-schedule/")
        self.assertEqual(rows[0][1], "Kellep Charles")


if __name__ == "__main__":
    unittest.main()
