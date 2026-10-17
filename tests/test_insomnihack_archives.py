from __future__ import annotations

import json
import unittest
from pathlib import Path

from scrapers.assessors.insomnihack import (
    PAGE_PARSERS,
    _member,
    _year,
)
from scrapers.archives import ArchiveStore
from scrapers.individuals import _looks_like_talk_title
from scrapers.assessors.insomnihack.edition_2026 import _names


class InsomnihackArchiveValidationTest(unittest.TestCase):
    """Validate every archived Insomni'hack page independently, offline."""

    def test_each_configured_archive_has_clean_records(self) -> None:
        config = json.loads(Path("data/assessors/insomnihack/insomnihack.json").read_text(encoding="utf-8"))
        archive = ArchiveStore(Path("data/archives/html/insomnihack.zip"))
        sources = config["links"]["processUrls"]
        self.assertEqual(len(sources), 13)

        for source in sources:
            with self.subTest(source=source):
                body = archive.read(_member(source))
                self.assertIsNotNone(body, source)
                year = _year(source)
                parser = PAGE_PARSERS[year]
                self.assertEqual(parser.__module__, f"scrapers.assessors.insomnihack.edition_{year}")
                rows = parser(body, source)
                self.assertTrue(rows, source)
                for row in rows:
                    self.assertNotIn(row.name.casefold(), {
                        "information security",
                        "introduction alain mowat",
                    })
                    self.assertFalse(
                        _looks_like_talk_title(row.name, row.title),
                        f"{source}: {row.name!r} / {row.title!r}",
                    )

    def test_2026_sandra_pichon_is_not_split_on_and_substring(self) -> None:
        self.assertEqual(
            _names("Trust Valley & Sandra Pichon & Geovani Rizk"),
            ["Trust Valley", "Sandra Pichon", "Geovani Rizk"],
        )

    def test_known_insomnihack_names_have_correct_identity_forms(self) -> None:
        config = json.loads(Path("data/assessors/insomnihack/insomnihack.json").read_text(encoding="utf-8"))
        archive = ArchiveStore(Path("data/archives/html/insomnihack.zip"))
        found = {}
        for source in config["links"]["processUrls"]:
            year = _year(source)
            rows = PAGE_PARSERS[year](archive.read(_member(source)), source)
            for row in rows:
                if row.name.casefold() in {"mia landsem", "christian folini", "lorenz adlung"}:
                    found[row.name.casefold()] = year
                self.assertNotIn(row.name.casefold(), {"dr. christian folini", "dr. lorenz adlung"})
        self.assertEqual(found, {
            "mia landsem": 2023,
            "christian folini": 2023,
            "lorenz adlung": 2020,
        })

    def test_known_truncated_names_are_not_emitted(self) -> None:
        config = json.loads(Path("data/assessors/insomnihack/insomnihack.json").read_text(encoding="utf-8"))
        archive = ArchiveStore(Path("data/archives/html/insomnihack.zip"))
        found = {}
        bad = {"er kozlov", "rea apollino", "rea pierini", "reas schneider"}
        for source in config["links"]["processUrls"]:
            year = _year(source)
            rows = PAGE_PARSERS[year](archive.read(_member(source)), source)
            for row in rows:
                self.assertNotIn(row.name.casefold(), bad)
                if row.name.casefold() in {
                    "alexander kozlov", "andrea apollino", "andrea pierini", "andreas schneider",
                }:
                    found[row.name.casefold()] = year
        self.assertEqual(found, {
            "alexander kozlov": 2024,
            "andrea apollino": 2026,
            "andrea pierini": 2026,
            "andreas schneider": 2022,
        })

    def test_organizations_are_not_emitted_as_people(self) -> None:
        config = json.loads(Path("data/assessors/insomnihack/insomnihack.json").read_text(encoding="utf-8"))
        archive = ArchiveStore(Path("data/archives/html/insomnihack.zip"))
        for source in config["links"]["processUrls"]:
            year = _year(source)
            rows = PAGE_PARSERS[year](archive.read(_member(source)), source)
            self.assertNotIn("orange cyberdefense", {row.name.casefold() for row in rows})
