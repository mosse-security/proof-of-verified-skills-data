from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from endorsement_scraper.assessors.def_con import DefConScraper, parse_def_con_page


MODERN_HTML = b"""
<html><body>
  <article class="talk" id="content_42">
    <h3 class="talk-title">Breaking All The Things</h3>
    <h4 class="speaker">Alice Example<span class="speaker-title">Researcher</span></h4>
    <h4 class="speaker">Bob Example<span class="speaker-title">Engineer</span></h4>
  </article>
</body></html>
"""


def assessor_document(process_urls: list[str]) -> dict[str, object]:
    return {
        "id": "def-con",
        "name": "DEF CON",
        "category": "conference_community",
        "peerReview": {"rigorLevel": "medium", "reviewType": "community_review"},
        "links": {"processUrls": process_urls},
    }


class DefConTests(unittest.TestCase):
    def test_modern_page_emits_one_simple_record_per_speaker(self) -> None:
        records = parse_def_con_page(
            34,
            MODERN_HTML,
            "https://defcon.org/html/defcon-34/dc-34-speakers.html",
        )

        self.assertEqual([record.name for record in records], ["Alice Example", "Bob Example"])
        self.assertEqual(records[0].label, "Breaking All The Things")
        self.assertEqual(records[0].subtitle, "DEF CON 34")
        self.assertEqual(records[0].year, 2026)
        self.assertEqual(records[0].domains, ("unknown",))
        self.assertEqual(
            records[0].url,
            "https://defcon.org/html/defcon-34/dc-34-speakers.html#content_42",
        )

    def test_schedule_uses_talk_link_and_discards_timing_metadata(self) -> None:
        html = b"""
        <ul class="schedule-row"><li>
          <h4 class="sched-title"><a href="https://forum.defcon.org/node/42">A Scheduled Talk</a></h4>
          <p class="sched-speaker">Carol Example<br>20 minutes</p>
        </li></ul>
        """
        records = parse_def_con_page(
            30, html, "https://defcon.org/html/defcon-30/dc-30-schedule.html"
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].name, "Carol Example")
        self.assertEqual(records[0].url, "https://forum.defcon.org/node/42")

    def test_empty_abstract_marker_collects_following_description(self) -> None:
        html = b"""
        <article class="talk" id="content_66672">
          <h3 class="talk-title">LaunchBreak: a Full Desktop Takeover</h3>
          <h4 class="speaker">Gavin Example</h4>
          <p class="abstract"></p>
          <p>A multi-stage exploit chain produced 11 CVEs, full RCEs, and PoCs.</p>
          <p class="speaker-bio"><strong>Gavin Example</strong></p>
          <p>Gavin previously worked on AWS cloud-security.</p>
          <p class="speaker-bio"><a href="https://www.linkedin.com/in/gavin">LinkedIn</a><br>
          <a href="https://example.test/gavin">Website</a></p>
        </article>
        """
        records = parse_def_con_page(
            34,
            html,
            "https://defcon.org/html/defcon-34/dc-34-speakers.html",
        )

        self.assertEqual(records[0].domains, ("vulnerability-research",))
        self.assertEqual(records[0].biography, "")
        self.assertEqual(
            records[0].contact,
            (
                {"label": "linkedin", "url": "https://www.linkedin.com/in/gavin"},
                {"label": "website", "url": "https://example.test/gavin"},
            ),
        )

    def test_local_cache_is_preferred_and_output_is_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assessor_file = root / "def-con.json"
            assessor_file.write_text(
                json.dumps(assessor_document([
                    "https://defcon.org/html/defcon-34/dc-34-speakers.html"
                ])),
                encoding="utf-8",
            )
            cache = root / "html" / "defcon-34" / "speakers.html"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(MODERN_HTML)

            def unexpected_fetch(_request):
                self.fail("The network must not be used when a cache file exists")

            scraper = DefConScraper(
                assessor_file=assessor_file,
                html_directory=root / "html",
                output_directory=root / "endorsements",
                profile_directory=root / "profiles",
                workers=1,
                fetch=unexpected_fetch,
            )
            first = scraper.run()[0]
            self.assertEqual(first.cache, "local")
            self.assertEqual(first.status, "created")

            cache.write_bytes(MODERN_HTML.replace(b"Breaking All The Things", b"Updated Talk"))
            second = scraper.run()[0]
            self.assertEqual(second.status, "overwritten")
            payload = json.loads(second.output.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["label"], "Updated Talk")
            self.assertEqual(
                set(payload[0]),
                {
                    "name", "label", "description", "type", "assessor", "assessor-id",
                    "assessor-category", "assessor-rigor-level", "reviewType", "subtitle", "url",
                    "year", "evidence-links", "evidence", "domains", "subspecialties",
                },
            )
            self.assertEqual(payload[0]["type"], "presentation")
            self.assertEqual(payload[0]["assessor"], "DEF CON")
            self.assertEqual(payload[0]["assessor-id"], "def-con")
            self.assertEqual(payload[0]["assessor-category"], "conference_community")
            self.assertEqual(payload[0]["assessor-rigor-level"], "medium")
            self.assertEqual(payload[0]["reviewType"], "community_review")
            self.assertEqual(payload[0]["subtitle"], "DEF CON 34")
            self.assertEqual(payload[0]["year"], 2026)
            self.assertEqual(payload[0]["domains"], ["unknown"])

    def test_missing_cache_is_fetched_once_and_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assessor_file = root / "def-con.json"
            assessor_file.write_text(
                json.dumps(assessor_document([
                    "https://defcon.org/html/defcon-34/dc-34-speakers.html"
                ])),
                encoding="utf-8",
            )
            calls = []

            def fetch(request):
                calls.append(request.url)
                return SimpleNamespace(body=MODERN_HTML)

            scraper = DefConScraper(
                assessor_file=assessor_file,
                html_directory=root / "html",
                output_directory=root / "endorsements",
                profile_directory=root / "profiles",
                workers=1,
                fetch=fetch,
            )
            result = scraper.run()[0]

            self.assertEqual(result.cache, "fetched")
            self.assertEqual(len(calls), 1)
            self.assertEqual(
                (root / "html" / "defcon-34" / "speakers.html").read_bytes(),
                MODERN_HTML,
            )

    def test_zip_cache_is_read_without_extracting_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assessor_file = root / "def-con.json"
            assessor_file.write_text(
                json.dumps(assessor_document([
                    "https://defcon.org/html/defcon-34/dc-34-speakers.html"
                ])),
                encoding="utf-8",
            )
            archive = root / "def-con.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("defcon-34/speakers.html", MODERN_HTML)

            scraper = DefConScraper(
                assessor_file=assessor_file,
                html_directory=archive,
                output_directory=root / "endorsements",
                profile_directory=root / "profiles",
                workers=1,
                fetch=lambda _request: self.fail("The ZIP cache should be used"),
            )
            result = scraper.run()[0]

            self.assertEqual(result.cache, "local")
            self.assertTrue(archive.is_file())
            self.assertFalse((root / "defcon-34").exists())


if __name__ == "__main__":
    unittest.main()


