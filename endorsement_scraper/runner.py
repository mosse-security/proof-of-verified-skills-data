from __future__ import annotations

import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Iterable

from .base import (
    BaseCollectionScraper,
    BaseScraper,
    CollectionScraperContext,
    CollectionScraperResult,
)
from .http import HttpClient
from .models import Endorsement, PageResult, PersonProfile, Request
from .schema import OrganizationMetadata, validate_endorsement_output_files
from .storage import EndorsementStore, ProfileStore


LOGGER = logging.getLogger(__name__)
ClientFactory = Callable[[str, str], HttpClient]


@dataclass(slots=True)
class ScraperReport:
    scraper_id: str
    organization_id: str
    pages: int = 0
    endorsements: int = 0
    created: int = 0
    skipped: int = 0
    overwritten: int = 0
    error: str | None = None


@dataclass(slots=True)
class RunReport:
    scrapers: list[ScraperReport] = field(default_factory=list)

    @property
    def failed(self) -> list[ScraperReport]:
        return [report for report in self.scrapers if report.error]

    def totals(self) -> dict[str, int]:
        fields = ("pages", "endorsements", "created", "skipped", "overwritten")
        return {
            name: sum(getattr(report, name) for report in self.scrapers)
            for name in fields
        }


class ScraperRunner:
    """Run independent scrapers concurrently and pages within each in order."""

    def __init__(
        self,
        *,
        store: EndorsementStore,
        profile_store: ProfileStore | None = None,
        client_factory: ClientFactory,
        workers: int = 8,
        overwrite: bool = False,
        max_pages: int | None = 1_000,
    ) -> None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        if max_pages is not None and max_pages < 1:
            raise ValueError("max_pages must be at least 1 or None")
        self.store = store
        self.profile_store = profile_store
        self.client_factory = client_factory
        self.workers = workers
        self.overwrite = overwrite
        self.max_pages = max_pages

    def run(self, scraper_classes: Iterable[type[BaseScraper]]) -> RunReport:
        classes = list(scraper_classes)
        reports: list[ScraperReport] = []
        with ThreadPoolExecutor(
            max_workers=self.workers, thread_name_prefix="scraper"
        ) as executor:
            futures = {executor.submit(self._run_one, cls): cls for cls in classes}
            for future in as_completed(futures):
                scraper_class = futures[future]
                try:
                    reports.append(future.result())
                except Exception as exc:
                    scraper_id = getattr(scraper_class, "scraper_id", scraper_class.__name__)
                    organization_id = getattr(scraper_class, "organization_id", "unknown")
                    LOGGER.exception("Could not initialize scraper %s", scraper_id)
                    reports.append(
                        ScraperReport(
                            scraper_id=scraper_id,
                            organization_id=organization_id,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
        reports.sort(key=lambda report: report.scraper_id)
        return RunReport(reports)

    def _run_one(self, scraper_class: type[BaseScraper]) -> ScraperReport:
        scraper = scraper_class()
        report = ScraperReport(scraper.scraper_id, scraper.organization_id)
        LOGGER.info("Starting %s", scraper.scraper_id)
        try:
            client = self.client_factory(scraper.organization_id, scraper.scraper_id)
            pending = deque(scraper.start_requests())
            seen_requests: set[str] = set()

            while pending:
                request = pending.popleft()
                if not isinstance(request, Request):
                    raise TypeError(
                        f"{scraper.scraper_id} emitted a non-Request value: {request!r}"
                    )
                if request.fingerprint in seen_requests:
                    continue
                if self.max_pages is not None and report.pages >= self.max_pages:
                    raise RuntimeError(
                        f"page limit ({self.max_pages}) reached with requests remaining"
                    )
                seen_requests.add(request.fingerprint)

                response = client.fetch(request)
                report.pages += 1
                result = scraper.parse(response, request)
                if not isinstance(result, PageResult):
                    raise TypeError(
                        f"{scraper.scraper_id}.parse() must return PageResult, "
                        f"not {type(result).__name__}"
                    )

                for endorsement in result.endorsements:
                    self._save_endorsement(scraper, endorsement, report)
                if self.profile_store is not None:
                    for profile in result.profiles:
                        if not isinstance(profile, PersonProfile):
                            raise TypeError(
                                f"{scraper.scraper_id} emitted a non-PersonProfile value: {profile!r}"
                            )
                        self.profile_store.save(
                            profile,
                            organization_id=scraper.organization_id,
                            scraper_id=scraper.scraper_id,
                        )
                pending.extend(result.follow)
        except Exception as exc:
            report.error = f"{type(exc).__name__}: {exc}"
            LOGGER.exception("Scraper %s failed", scraper.scraper_id)
        else:
            LOGGER.info("Finished %s", scraper.scraper_id)
        return report

    def _save_endorsement(
        self,
        scraper: BaseScraper,
        endorsement: Endorsement,
        report: ScraperReport,
    ) -> None:
        if not isinstance(endorsement, Endorsement):
            raise TypeError(
                f"{scraper.scraper_id} emitted a non-Endorsement value: "
                f"{endorsement!r}"
            )
        if endorsement.organization_id != scraper.organization_id:
            raise ValueError(
                f"{scraper.scraper_id} emitted organization_id "
                f"{endorsement.organization_id!r}; expected {scraper.organization_id!r}"
            )
        result = self.store.save(
            endorsement,
            scraper_id=scraper.scraper_id,
            overwrite=self.overwrite,
        )
        report.endorsements += 1
        setattr(report, result.status, getattr(report, result.status) + 1)
        validate_endorsement_output_files(
            (result.path,),
            expected_records=1,
            organization=self.store.organization_metadata(scraper.organization_id),
        )


class CollectionScraperRunner:
    """Run independent grouped-output scraper plugins concurrently."""

    def __init__(self, *, context: CollectionScraperContext, workers: int = 8) -> None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        self.context = context
        self.workers = workers

    def run(
        self, scraper_classes: Iterable[type[BaseCollectionScraper]]
    ) -> RunReport:
        classes = list(scraper_classes)
        reports: list[ScraperReport] = []
        with ThreadPoolExecutor(
            max_workers=self.workers, thread_name_prefix="collection-scraper"
        ) as executor:
            futures = {executor.submit(self._run_one, cls): cls for cls in classes}
            for future in as_completed(futures):
                scraper_class = futures[future]
                try:
                    reports.append(future.result())
                except Exception as exc:
                    LOGGER.exception(
                        "Could not initialize collection scraper %s",
                        scraper_class.scraper_id,
                    )
                    reports.append(
                        ScraperReport(
                            scraper_id=scraper_class.scraper_id,
                            organization_id=scraper_class.organization_id,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
        reports.sort(key=lambda report: report.scraper_id)
        return RunReport(reports)

    def _run_one(
        self, scraper_class: type[BaseCollectionScraper]
    ) -> ScraperReport:
        scraper = scraper_class()
        report = ScraperReport(scraper.scraper_id, scraper.organization_id)
        LOGGER.info("Starting %s", scraper.scraper_id)
        try:
            result = scraper.run(self.context)
            if not isinstance(result, CollectionScraperResult):
                raise TypeError(
                    f"{scraper.scraper_id}.run() must return CollectionScraperResult, "
                    f"not {type(result).__name__}"
                )
            organization = OrganizationMetadata.from_file(
                self.context.organizations_directory
                / f"{scraper.organization_id}.json"
            )
            validate_endorsement_output_files(
                result.output_files,
                expected_records=result.endorsements,
                organization=organization,
            )
            report.pages = result.pages
            report.endorsements = result.endorsements
            report.created = result.created
            report.skipped = result.skipped
            report.overwritten = result.overwritten
        except Exception as exc:
            report.error = f"{type(exc).__name__}: {exc}"
            LOGGER.exception("Collection scraper %s failed", scraper.scraper_id)
        else:
            LOGGER.info("Finished %s", scraper.scraper_id)
        return report
