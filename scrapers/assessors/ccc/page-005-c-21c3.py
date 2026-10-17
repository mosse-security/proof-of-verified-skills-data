"""Standalone parser for archive page https://media.ccc.de/c/21c3."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-005-c-21c3'
SOURCE_URL = 'https://media.ccc.de/c/21c3'
YEAR = 0

"""Chaos Communication Congress recordings scraper."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.archives import ArchiveStore
from scrapers.domains import detect_domains
from scrapers.enrichment import EnrichmentCatalog
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class CccResult:
    source: str
    endorsements: int
    output: Path


def parse_ccc(html: bytes | str, source_url: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, str]] = []
    for item in soup.select(".event-preview"):
        title_link = item.select_one("h3 a[href]")
        people = item.select_one("li.persons")
        if not title_link or not people:
            continue
        title = " ".join(title_link.get_text(" ", strip=True).split())
        url = urljoin(source_url, title_link["href"])
        for link in people.select("a[href]"):
            name = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
            if title and name:
                rows.append((title, name, url))
    return list(dict.fromkeys(rows))


def _edition(html: bytes | str, source_url: str) -> tuple[int, str, str]:
    match = re.search(r"/(\d{2})c3/?$", source_url)
    slug = match.group(1) + "c3" if match else "ccc"
    soup = BeautifulSoup(html, "html.parser")
    breadcrumb = soup.select_one(".breadcrumb li.active")
    year_match = re.search(r"\b(20\d{2})\b", breadcrumb.get_text(" ", strip=True)) if breadcrumb else None
    year = int(year_match.group(1)) if year_match else 0
    return year, slug, slug.upper()


class CccScraper:
    assessor_id = "ccc"
    scraper_id = "ccc-recordings"

    def __init__(self, *, assessor_file=Path("data/assessors/ccc.json"),
                 html_directory=Path("data/archives/html/ccc.zip"),
                 output_directory=Path("tmp/endorsements/ccc"),
                 profile_directory=Path("tmp/profiles/ccc"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        data = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        self.sources = data["links"]["processUrls"]
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[CccResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year, slug, subtitle = _edition(body, source)
            rows = parse_ccc(body, source)
            records = []
            names: dict[str, dict[str, object]] = {}
            for title, name, url in rows:
                records.append(build_endorsement_record(
                    name=name, label=title, description=title,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle=subtitle, url=url, year=year,
                    domains=detect_domains(title, title),
                    evidence_links=self.catalog.links_for(
                        assessor_id=self.assessor.id, label=title, subtitle=subtitle),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            output = self.output_directory / f"ccc-{slug}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(CccResult(source, len(records), output))
        return results


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_ccc(body, source_url)


