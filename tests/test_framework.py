from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from endorsement_scraper import (
    BaseCollectionScraper,
    BaseScraper,
    CollectionScraperContext,
    CollectionScraperResult,
    Endorsement,
    PageResult,
    PersonProfile,
    Request,
    Response,
)
from endorsement_scraper.discovery import discover_all_scrapers, discover_scrapers
from endorsement_scraper.http import HttpClient
from endorsement_scraper.runner import CollectionScraperRunner, ScraperRunner
from endorsement_scraper.storage import EndorsementStore, ProfileStore


class FakeClient:
    def fetch(self, request: Request) -> Response:
        return Response(
            request=request,
            url=request.url,
            status=200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            body=request.url.encode(),
        )


class FakeUrlResponse:
    status = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def geturl(self) -> str:
        return "https://example.test/final"

    def read(self) -> bytes:
        return b"<html>saved</html>"


class PaginatedScraper(BaseScraper):
    assessor_id = "test-org"
    scraper_id = "test-pages"
    start_urls = ("https://example.test/page/1",)

    def parse(self, response: Response, request: Request) -> PageResult:
        shared = Endorsement(
            assessor_id=self.assessor_id,
            kind="cve",
            title="Shared finding",
            description="A shared vulnerability finding.",
            recipient="Researcher One",
            year=2026,
            external_id="CVE-2026-0001",
            source_url=response.url,
        )
        if request.url.endswith("/1"):
            return PageResult.build(
                [shared], [Request("https://example.test/page/2")],
                [PersonProfile("Researcher One", "A security researcher.", ())],
            )
        second = Endorsement(
            assessor_id=self.assessor_id,
            kind="cash_prize",
            title="Winner",
            description="A cash prize awarded to the winner.",
            recipient="Alice",
            date="2026",
            source_url=response.url,
            details={"amount": 1000},
        )
        # The link back verifies request-cycle protection.
        return PageResult.build(
            [shared, second], [Request("https://example.test/page/1")]
        )


class GroupedScraper(BaseCollectionScraper):
    assessor_id = "grouped-org"
    scraper_id = "grouped-records"

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        output = context.output_directory / "grouped.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps([
                {
                    "name": f"Person {index}",
                    "label": "Example endorsement",
                    "description": "A detailed endorsement description.",
                    "type": "presentation",
                    "assessor": "Grouped Org",
                    "assessor-id": "grouped-org",
                    "assessor-category": "conference_community",
                    "assessor-rigor-level": "medium",
                    "reviewType": "community_review",
                    "url": f"https://example.test/{index}",
                    "evidence-links": [],
                    "evidence": False,
                    "povs": {
                        "milestones": {"verifiable": False, "defended": False, "recognized": False, "trusted": False},
                        "level": 0,
                        "explanation": "No evidence discovered for this record therefore it could not be verified",
                    },
                    "year": 2026,
                    "domains": ["unknown"],
                }
                for index in range(7)
            ]),
            encoding="utf-8",
        )
        return CollectionScraperResult(
            pages=3,
            endorsements=7,
            overwritten=1,
            output_files=(output,),
        )


class InvalidGroupedScraper(BaseCollectionScraper):
    assessor_id = "invalid-grouped-org"
    scraper_id = "invalid-grouped-records"

    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        output = context.output_directory / "invalid.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps([{"title": "Missing domains"}]), encoding="utf-8")
        return CollectionScraperResult(
            pages=1, endorsements=1, created=1, output_files=(output,)
        )


class FrameworkTests(unittest.TestCase):
    @staticmethod
    def write_assessor(directory: Path, assessor_id: str, name: str) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{assessor_id}.json").write_text(
            json.dumps(
                {
                    "id": assessor_id,
                    "name": name,
                    "category": "conference_community",
                    "peerReview": {"rigorLevel": "medium", "reviewType": "community_review"},
                }
            ),
            encoding="utf-8",
        )

    def test_runner_follows_pages_and_deduplicates_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "endorsements"
            assessors = root / "assessors"
            self.write_assessor(assessors, "test-org", "Test Org")
            runner = ScraperRunner(
                store=EndorsementStore(output, assessors),
                profile_store=ProfileStore(root / "profiles"),
                client_factory=lambda _assessor, _scraper: FakeClient(),
                workers=2,
            )

            first = runner.run([PaginatedScraper])
            report = first.scrapers[0]
            self.assertIsNone(report.error)
            self.assertEqual(report.pages, 2)
            self.assertEqual(report.endorsements, 3)
            self.assertEqual(report.created, 2)
            self.assertEqual(report.skipped, 1)
            self.assertEqual(len(list(output.rglob("*.json"))), 2)
            self.assertEqual(len(list((root / "profiles").rglob("*.json"))), 1)
            for path in output.rglob("*.json"):
                self.assertTrue(json.loads(path.read_text())["domains"])

            second = runner.run([PaginatedScraper]).scrapers[0]
            self.assertEqual(second.created, 0)
            self.assertEqual(second.skipped, 3)
            self.assertEqual(len(list(output.rglob("*.json"))), 2)

    def test_overwrite_updates_an_existing_stable_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assessors = root / "assessors"
            self.write_assessor(assessors, "test-org", "Test Org")
            store = EndorsementStore(root / "endorsements", assessors)
            original = Endorsement(
                assessor_id="test-org",
                kind="cve",
                title="Old title",
                description="The original finding description.",
                recipient="Researcher One",
                source_url="https://example.test/old",
                external_id="CVE-2026-0002",
                year=2026,
            )
            changed = Endorsement(
                assessor_id="test-org",
                kind="cve",
                title="Corrected title",
                description="The corrected finding description.",
                recipient="Researcher One",
                source_url="https://example.test/new",
                external_id="CVE-2026-0002",
                year=2026,
            )
            created = store.save(original, scraper_id="one", overwrite=False)
            skipped = store.save(changed, scraper_id="two", overwrite=False)
            self.assertEqual(created.status, "created")
            self.assertEqual(skipped.status, "skipped")
            self.assertEqual(json.loads(created.path.read_text())["label"], "Old title")

            overwritten = store.save(changed, scraper_id="two", overwrite=True)
            self.assertEqual(overwritten.status, "overwritten")
            self.assertEqual(
                json.loads(created.path.read_text())["label"], "Corrected title"
            )

    def test_discovery_recurses_and_ignores_template_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "scrapers"
            nested = directory / "nested"
            nested.mkdir(parents=True)
            source = textwrap.dedent(
                """
                from endorsement_scraper import BaseScraper, PageResult

                class Found(BaseScraper):
                    assessor_id = "found-org"
                    scraper_id = "found-scraper"
                    start_urls = ("https://example.test",)

                    def parse(self, response, request):
                        return PageResult()
                """
            )
            (nested / "active.py").write_text(source, encoding="utf-8")
            (directory / "_ignored.py").write_text(source, encoding="utf-8")

            found = discover_scrapers(directory)
            self.assertEqual([item.scraper_id for item in found], ["found-scraper"])

    def test_discovery_includes_grouped_output_scrapers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "scrapers"
            directory.mkdir()
            source = textwrap.dedent(
                """
                from endorsement_scraper import (
                    BaseCollectionScraper,
                    CollectionScraperResult,
                )

                class FoundCollection(BaseCollectionScraper):
                    assessor_id = "found-org"
                    scraper_id = "found-collection"

                    def run(self, context):
                        return CollectionScraperResult()
                """
            )
            (directory / "collection.py").write_text(source, encoding="utf-8")

            found = discover_all_scrapers(directory)
            self.assertEqual(found.page_scrapers, ())
            self.assertEqual(
                [item.scraper_id for item in found.collection_scrapers],
                ["found-collection"],
            )

    def test_collection_runner_reports_grouped_scraper_totals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_assessor(
                root / "assessors", "grouped-org", "Grouped Org"
            )
            context = CollectionScraperContext(
                assessors_directory=root / "assessors",
                output_directory=root / "endorsements",
                html_directory=root / "html",
                workers=2,
                overwrite=None,
                timeout=30,
                retries=2,
                backoff=0.5,
                delay=0,
                user_agent="test",
            )
            report = CollectionScraperRunner(context=context, workers=2).run(
                [GroupedScraper]
            )

            self.assertEqual(len(report.scrapers), 1)
            self.assertEqual(report.totals()["pages"], 3)
            self.assertEqual(report.totals()["endorsements"], 7)
            self.assertEqual(report.totals()["overwritten"], 1)

    def test_collection_runner_rejects_output_without_domains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_assessor(
                root / "assessors", "invalid-grouped-org", "Invalid Grouped Org"
            )
            context = CollectionScraperContext(
                assessors_directory=root / "assessors",
                output_directory=root / "endorsements",
                html_directory=root / "html",
                workers=1,
                overwrite=None,
                timeout=30,
                retries=2,
                backoff=0.5,
                delay=0,
                user_agent="test",
            )
            with self.assertLogs("endorsement_scraper.runner", level="ERROR"):
                report = CollectionScraperRunner(context=context, workers=1).run(
                    [InvalidGroupedScraper]
                )

            self.assertIn("domains", report.scrapers[0].error)

    def test_http_snapshot_saves_body_and_metadata(self) -> None:
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as temporary:
            snapshots = Path(temporary)
            client = HttpClient(
                assessor_id="test-org",
                scraper_id="test-pages",
                save_html=True,
                html_directory=snapshots,
            )
            request = Request("https://example.test/start")
            with patch(
                "endorsement_scraper.http.urllib.request.urlopen",
                return_value=FakeUrlResponse(),
            ):
                response = client.fetch(request)

            directory = snapshots / "test-org" / "test-pages"
            self.assertEqual(
                (directory / f"{request.fingerprint}.html").read_bytes(),
                b"<html>saved</html>",
            )
            metadata = json.loads(
                (directory / f"{request.fingerprint}.json").read_text()
            )
            self.assertEqual(metadata["requestedUrl"], request.url)
            self.assertEqual(metadata["finalUrl"], response.url)


if __name__ == "__main__":
    unittest.main()


