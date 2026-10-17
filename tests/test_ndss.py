import unittest

from scrapers.assessors.ndss import _authors


class NdssAuthorParserTests(unittest.TestCase):
    def test_ignores_affiliation_commas_and_removes_nicknames(self) -> None:
        text = (
            'Dave (Jing) Tian (Purdue University), '
            'Lea Gröber (ICSI), Mobin Javed '
            '(Lahore University of Management Sciences (LUMS), Pakistan)'
        )
        self.assertEqual(_authors(text), ["Dave Tian", "Lea Gröber", "Mobin Javed"])

    def test_does_not_emit_affiliation_fragments(self) -> None:
        text = (
            'Sumair Ijaz Hashmi (CISPA, Germany), '
            'Lea Gröber (ICSI, USA and Lahore University of Management Sciences)'
        )
        self.assertEqual(_authors(text), ["Sumair Ijaz Hashmi", "Lea Gröber"])


if __name__ == "__main__":
    unittest.main()
