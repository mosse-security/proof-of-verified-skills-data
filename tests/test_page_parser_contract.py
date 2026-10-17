from __future__ import annotations

import unittest

from scrapers.page_parsers import ArchivedPageParser


class PageParserContractTest(unittest.TestCase):
    def test_every_emitted_record_is_validated(self):
        parser = ArchivedPageParser(
            assessor_id="test",
            page_id="fixture",
            archive_member="fixture.html",
            parse=lambda body, url: [{"invalid": True}],
        )
        with self.assertRaises(ValueError):
            parser.parse_validated(b"", "https://example.test/fixture.html")

    def test_valid_page_records_are_returned(self):
        record = {
            "name": "Ada Lovelace",
            "label": "A talk",
            "description": "A talk",
            "type": "presentation",
            "assessor": "Test",
            "assessor-id": "test",
            "assessor-category": "conference_community",
            "assessor-rigor-level": "medium",
            "reviewType": "committee_review",
            "subtitle": "Test 2026",
            "url": "https://example.test/fixture.html",
            "evidence-links": [],
            "evidence": False,
            "povs": {"milestones": {"verifiable": False, "defended": False, "recognized": False, "trusted": False}, "level": 0, "explanation": "No evidence discovered for this record therefore it could not be verified"},
            "year": 2026,
            "domains": ["unknown"],
            "subspecialties": {"unknown": []},
        }
        parser = ArchivedPageParser("test", "fixture", "fixture.html", lambda body, url: [record])
        self.assertEqual(parser.parse_validated(b"", record["url"]), [record])
