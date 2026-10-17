"""Standalone parser for archive page https://blackhat.com/archive/usa/2025/briefings/schedule/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-002-archive-usa-2025-briefings-schedule'
SOURCE_URL = 'https://blackhat.com/archive/usa/2025/briefings/schedule/'
YEAR = 2025


import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from scrapers.archives import ArchiveStore
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record
from scrapers.enrichment import EnrichmentCatalog


@dataclass(frozen=True, slots=True)
class BlackHatResult:
    year: int
    region: str
    endorsements: int
    cache: str
    output: Path


class BlackHatScraper:
    assessor_id = "black-hat"
    scraper_id = "black-hat-briefings"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/black-hat/black-hat.json"),
        html_directory: Path = Path("data/archives/html/black-hat.zip"),
        output_directory: Path = Path("tmp/endorsements/black-hat"),
        profile_directory: Path = Path("tmp/profiles/black-hat"),
        fetch: Callable[[Request], object] | None = None,
        overwrite: bool = True,
        timeout: float = 30,
        retries: int = 2,
        backoff: float = 0.5,
        delay: float = 0,
        user_agent: str = "verified-endorsement-scraper/0.1",
    ) -> None:
        self.assessor_file = assessor_file
        self.assessor = AssessorMetadata.from_file(assessor_file)
        self.enrichment_catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.html_directory = html_directory
        self.output_directory = output_directory
        self.profile_directory = profile_directory
        self.overwrite = overwrite
        if fetch is None:
            fetch = HttpClient(
                assessor_id=self.assessor_id,
                scraper_id=self.scraper_id,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
                delay=delay,
                user_agent=user_agent,
            ).fetch
        self.fetch = fetch

    def conference_urls(self) -> list[tuple[int, str, str]]:
        document = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        urls = document.get("links", {}).get("processUrls", [])
        result = []
        for url in urls:
            try:
                year, region = _event_identity(url)
            except ValueError:
                # The MEA landing page is an index, not a conference program.
                # Its event-specific pages are still processed below.
                if "blackhatmea.com" in url and url.rstrip("/").endswith("blackhatmea.com"):
                    continue
                if "blackhatmea.com" in url:
                    year, region = 2025, "middle-east"
                else:
                    raise
            result.append((year, region, url))
        return result

    def run(self) -> list[BlackHatResult]:
        results = []
        for year, region, url in self.conference_urls():
            member = _archive_member(url)
            archive = ArchiveStore(self.html_directory)
            body = archive.read(member)
            cache = "local"
            if body is None:
                response = self.fetch(Request(url, meta={"year": year, "region": region}))
                body = getattr(response, "body", None)
                if not isinstance(body, bytes):
                    raise TypeError("Black Hat fetch function must return bytes body")
                archive.write(member, body)
                cache = "fetched"
            rows = parse_black_hat_page(body, url, year, region)
            if not rows:
                # Some current landing/schedule pages legitimately contain no
                # published sessions yet; leave them cached for a later run.
                continue
            records = [row.to_record(self.assessor, self.enrichment_catalog) for row in rows]
            output = self.output_directory / f"blackhat-{region}-{year}.json"
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._write_profiles(rows, year, region)
            results.append(BlackHatResult(year, region, len(records), cache, output))
        return results

    def _write_profiles(self, rows: list["BlackHatEndorsement"], year: int, region: str) -> None:
        profiles = sorted({row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}.values(), key=lambda x: x["name"].casefold())
        output = self.profile_directory / f"blackhat-{region}-{year}.json"
        if self.overwrite or not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass(frozen=True, slots=True)
class BlackHatEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int
    subtitle: str
    evidence_links: tuple[dict[str, str], ...] = ()

    def to_record(self, assessor: AssessorMetadata, enrichment_catalog: EnrichmentCatalog | None = None) -> dict[str, object]:
        return build_endorsement_record(
            name=self.name,
            label=self.title,
            description=self.description or self.title,
            endorsement_type="presentation",
            assessor=assessor,
            subtitle=self.subtitle,
            url=self.url,
            year=self.year,
            domains=(),
            evidence_links=self.evidence_links or (enrichment_catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=self.subtitle) if enrichment_catalog else ()),
        )


def parse_black_hat_page(html: bytes | str, source_url: str, year: int, region: str) -> list[BlackHatEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    rows = _parse_modern(soup, source_url, year, region)
    if not rows:
        rows = _parse_legacy(soup, source_url, year, region)
    unique = {(row.name.casefold(), row.title.casefold(), row.url): row for row in rows}
    return list(unique.values())


def _parse_modern(soup: BeautifulSoup, source_url: str, year: int, region: str) -> list[BlackHatEndorsement]:
    rows = []
    for container in soup.select(".data-container"):
        title = container.select_one(".session-title a, .session-title")
        speakers = container.select(".session-speakers a.speaker_link")
        if not title or not speakers:
            continue
        description = container.select_one(".search_description")
        talk = title.get_text(" ", strip=True)
        desc = description.get_text(" ", strip=True) if description else talk
        link = urljoin(source_url, title.get("href", ""))
        for speaker in speakers:
            rows.append(BlackHatEndorsement(speaker.get_text(" ", strip=True), talk, desc, link, year, f"Black Hat {region.title()} {year}"))
    return rows


def _parse_legacy(soup: BeautifulSoup, source_url: str, year: int, region: str) -> list[BlackHatEndorsement]:
    rows = []
    for block in soup.select("div.span-14"):
        heading = block.select_one("h2.briefing-title")
        if not heading:
            continue
        title = heading.get_text(" ", strip=True)
        description = next((p.get_text(" ", strip=True) for p in block.select("p") if p.get_text(" ", strip=True)), title)
        link = urljoin(source_url, f"#{heading.get('id', '')}")
        presenter = block.find_next_sibling("div", class_=lambda value: value and "presented-by" in value)
        names = presenter.select("a") if presenter else []
        if not names and presenter:
            text = presenter.get_text(" ", strip=True)
            text = re.sub(r"^presented\s+by\s*:?\s*", "", text, flags=re.I)
            names = [text] if text else []
        for speaker in names:
            name = speaker.get_text(" ", strip=True) if isinstance(speaker, Tag) else str(speaker)
            if name:
                rows.append(BlackHatEndorsement(name, title, description, link, year, f"Black Hat {region.title()} {year}"))
    for block in soup.select("div.span-13, div.span-14"):
        heading = block.select_one("h2 a, h2")
        if not heading:
            continue
        title = heading.get_text(" ", strip=True)
        if title.casefold() in {"briefings", "media legend", "white paper", "presentation", "source", "audio", "video"}:
            continue
        description = next((p.get_text(" ", strip=True) for p in block.select("p") if p.get_text(" ", strip=True)), title)
        link = urljoin(source_url, heading.get("href", ""))
        sibling = block.find_next_sibling("div", class_=lambda value: value and "span-5" in value)
        speakers = sibling.select("a") if sibling else []
        for speaker in speakers:
            name = speaker.get_text(" ", strip=True)
            if name:
                rows.append(BlackHatEndorsement(name, title, description, link, year, f"Black Hat {region.title()} {year}"))
    return rows


def _event_identity(url: str) -> tuple[int, str]:
    path = urlsplit(url).path.casefold()
    match = re.search(r"(?:19|20)\d{2}", path)
    if match:
        value = int(match.group(0))
    else:
        short = re.search(r"(?:usa|us|europe|eu|ad|archives?)[/-]?(\d{2})(?:[^\d]|$)", path)
        if not short:
            short = re.search(r"-(\d{2})(?:[^\d]|$)", path)
        if not short:
            raise ValueError(f"Cannot determine Black Hat year from {url}")
        value = 2000 + int(short.group(1))
    year = value
    region = "europe" if "europe" in path or "/eu" in path else "middle-east" if "/ad-" in path or "bh-ad" in path else "usa"
    return year, region


def _archive_member(url: str) -> str:
    return urlsplit(url).path.strip("/") or "index.html"


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_black_hat_page(body, source_url, 2025, 'usa')


