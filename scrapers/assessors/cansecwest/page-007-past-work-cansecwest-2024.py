"""Standalone parser for archive page https://www.secwest.net/past-work/cansecwest-2024."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-007-past-work-cansecwest-2024'
SOURCE_URL = 'https://www.secwest.net/past-work/cansecwest-2024'
YEAR = 2024

"""CanSecWest Squarespace presentation archive parser."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.archives import ArchiveStore
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record
from scrapers.enrichment import EnrichmentCatalog


@dataclass(frozen=True, slots=True)
class CanSecWestResult:
    source: str
    endorsements: int
    output: Path


class CanSecWestScraper:
    assessor_id = "cansecwest"
    scraper_id = "cansecwest-presentations"

    def __init__(self, *, assessor_file=Path("data/assessors/cansecwest/cansecwest.json"), html_directory=Path("data/archives/html/cansecwest.zip"), output_directory=Path("tmp/endorsements/cansecwest"), profile_directory=Path("tmp/profiles/cansecwest"), overwrite=True, timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.enrichment_catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8")).get("links", {}).get("processUrls", [])
        self.archive = ArchiveStore(Path(html_directory))
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id, timeout=timeout, retries=retries).fetch

    def run(self) -> list[CanSecWestResult]:
        results = []
        for source in self.sources:
            member = _member(source)
            body = self.archive.read(member)
            if body is None:
                response = self.fetch(Request(source))
                body = response.body
                self.archive.write(member, body)
            rows = parse_cansecwest(body, source)
            if not rows:
                continue
            output = self.output_directory / f"{_slug(member)}.json"
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps([r.to_record(self.assessor, self.enrichment_catalog) for r in rows], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = {r.name: {"name": r.name, "biography": "", "contact": []} for r in rows}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"{_slug(member)}.json").write_text(json.dumps(list(profiles.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(CanSecWestResult(source, len(rows), output))
        return results


@dataclass(frozen=True, slots=True)
class CanSecWestEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int

    def to_record(self, assessor, enrichment_catalog=None):
        subtitle = f"CanSecWest {self.year}" if self.year else "CanSecWest"
        links = enrichment_catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=subtitle) if enrichment_catalog else ()
        return build_endorsement_record(name=self.name, label=self.title, description=self.description or self.title, endorsement_type="presentation", assessor=assessor, subtitle=subtitle, url=self.url, year=self.year, domains=(), evidence_links=links)


def parse_cansecwest(html: bytes | str, source_url: str) -> list[CanSecWestEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    year_match = re.search(r"20\d{2}", soup.get_text(" ", strip=True)[:3000] + source_url)
    year = int(year_match.group()) if year_match else 0
    rows = []
    for heading in soup.select("h1.blog-title"):
        title_link = heading.find("a")
        title = heading.get_text(" ", strip=True)
        container = heading.parent
        excerpt = container.select_one(".blog-excerpt")
        description = excerpt.get_text(" ", strip=True) if excerpt else title
        names = [a.get_text(" ", strip=True) for a in container.select("a.blog-categories")]
        for name in dict.fromkeys(n for n in names if _likely_person(n)):
            rows.append(CanSecWestEndorsement(name, title, description, urljoin(source_url, title_link.get("href", "") if title_link else ""), year))
    unique = {(r.name.casefold(), r.title.casefold(), r.url): r for r in rows}
    return list(unique.values())


def _likely_person(value: str) -> bool:
    lowered = value.casefold()
    return value and not any(token in lowered for token in ("network", "security group", "inc.", " llc", "laborator", "university", "microsoft", "rapidns"))


def _member(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    return path or "index.html"


def _slug(member: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", member.casefold()).strip("-") or "source"


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_cansecwest(body, source_url)


