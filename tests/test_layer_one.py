import unittest
import json
from pathlib import Path

from endorsement_scraper.assessors.layer_one import parse_layer_one


class LayerOneParserTests(unittest.TestCase):
    def test_archive_inventory_accounts_for_2004_through_2025(self):
        data = json.loads(Path("data/assessors/layer-one.json").read_text(encoding="utf-8"))
        inv = data["archiveInventory"]
        years = set(inv["htmlYears"]) | {int(y) for y in inv["youtubeYears"]} | set(inv["unavailableYears"])
        self.assertEqual(years, set(range(2004, 2026)))

    def test_lineup_extracts_name_and_title(self):
        html = """<div class='entry'><a href='/speakers/#a'>Alex Useche – Pragmatic Program Analysis</a><a href='/other'>Ignore</a></div>"""
        self.assertEqual(parse_layer_one(html, "https://www.layerone.org/2024-speaker-lineup/"),
                         [("Pragmatic Program Analysis", "Alex Useche", "", "https://www.layerone.org/2024-speaker-lineup/")])

    def test_malformed_link_is_ignored(self):
        self.assertEqual(parse_layer_one("<div class='entry'><a href='/speakers/#a'>No separator</a></div>", "x"), [])

    def test_historical_archive_extracts_presenters_and_topics(self):
        html = "<div class='entry'>Presenter: Alex and Sam Topic: Radio Security Slides: deck.pdf Presenter: Jo Topic: Web Safety</div>"
        rows = parse_layer_one(html, "https://www.layerone.org/archives/layerone-2012/")
        self.assertEqual([(r[0], r[1]) for r in rows], [("Radio Security", "Alex"), ("Radio Security", "Sam"), ("Web Safety", "Jo")])


if __name__ == "__main__":
    unittest.main()
