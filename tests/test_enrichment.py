from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scrapers.enrichment import EnrichmentCatalog, discover_enrichers


class EnrichmentTests(unittest.TestCase):
    def test_discovery_finds_def_con_youtube_enricher(self) -> None:
        self.assertIn(
            "def-con-youtube-recordings",
            {item.enricher_id for item in discover_enrichers(Path("scrapers/enrichers"))},
        )

    def test_catalog_matches_title_and_conference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "def-con-youtube-recordings" / "data.zip"
            archive.parent.mkdir(parents=True)
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("data.json", json.dumps([{
                    "assessor-id": "def-con",
                    "title": "DEF CON 34 - LaunchBreak: A Sip of Tea",
                    "url": "https://youtube.test/watch?v=abc",
                    "conference": "34",
                }]))
            catalog = EnrichmentCatalog.from_directory(Path(temporary))
            self.assertEqual(
                catalog.links_for(
                    assessor_id="def-con",
                    label="LaunchBreak: A Sip of Tea",
                    subtitle="DEF CON 34",
                ),
                ({"title": "DEF CON 34 - LaunchBreak: A Sip of Tea", "url": "https://youtube.test/watch?v=abc"},),
            )

    def test_catalog_matches_prefixed_video_title(self) -> None:
        catalog = EnrichmentCatalog([
            {
                "assessor-id": "def-con",
                "title": "DEF CON 29 - Yuhao Weng, Steven Seeley, Zhiniang Peng - An Attack Surface Tour of SharePoint Server",
                "url": "https://www.youtube.com/watch?v=mVXrl4W1jOU",
                "conference": "29",
            }
        ])
        links = catalog.links_for(
            assessor_id="def-con",
            label="Don't Dare to Exploit - An Attack Surface Tour of SharePoint Server",
            subtitle="DEF CON 29",
        )
        self.assertEqual(links[0]["url"], "https://www.youtube.com/watch?v=mVXrl4W1jOU")


if __name__ == "__main__":
    unittest.main()
