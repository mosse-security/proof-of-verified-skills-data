from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from .models import PageResult, Request, Response


class BaseScraper(ABC):
    """Base class for every dynamically discovered scraper.

    Multiple scraper classes may target one assessor. Give each one a
    globally unique ``scraper_id`` (for example ``black-hat-briefings`` and
    ``black-hat-arsenal``).
    """

    assessor_id: ClassVar[str]
    scraper_id: ClassVar[str]
    start_urls: ClassVar[tuple[str, ...]] = ()

    def start_requests(self) -> Iterable[Request]:
        """Seed the crawl.

        Override this for yearly archives, APIs, POST requests, or other
        dynamically generated page sets.
        """

        return (Request(url) for url in self.start_urls)

    @abstractmethod
    def parse(self, response: Response, request: Request) -> PageResult:
        """Parse one response and optionally return pagination requests."""


@dataclass(frozen=True, slots=True)
class CollectionScraperContext:
    """Shared command-line settings supplied to a collection scraper."""

    assessors_directory: Path
    output_directory: Path
    html_directory: Path
    workers: int
    overwrite: bool | None
    timeout: float
    retries: int
    backoff: float
    delay: float
    user_agent: str
    profile_directory: Path = Path("data/tmp/profiles")


@dataclass(frozen=True, slots=True)
class CollectionScraperResult:
    """Aggregate result returned by one collection scraper."""

    pages: int = 0
    endorsements: int = 0
    created: int = 0
    skipped: int = 0
    overwritten: int = 0
    output_files: tuple[Path, ...] = ()


class BaseCollectionScraper(ABC):
    """Plugin contract for scrapers that control their own grouped output."""

    assessor_id: ClassVar[str]
    scraper_id: ClassVar[str]
    overwrite_by_default: ClassVar[bool] = False

    @abstractmethod
    def run(self, context: CollectionScraperContext) -> CollectionScraperResult:
        """Run the scraper and return aggregate output counts."""


