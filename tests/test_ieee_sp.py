import unittest

from scrapers.assessors.ieee_sp import parse_ieee_sp


class IeeeSpParserTests(unittest.TestCase):
    def test_removes_parenthesized_aliases(self):
        html = b'''<div class="list-group-item"><b><a>Example Paper</a></b><div class="authorlist">Rie Helene (Lindy) Hernandez<br/></div></div>'''
        rows = parse_ieee_sp(html, "https://sp2026.ieee-security.org/accepted-papers.html")
        self.assertEqual(rows[0][1], "Rie Helene Hernandez")


if __name__ == "__main__":
    unittest.main()
