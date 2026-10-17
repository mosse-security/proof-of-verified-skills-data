"""Standalone parser for archive page https://grrcon.com/presentations24/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-002-presentations24'
SOURCE_URL = 'https://grrcon.com/presentations24/'
YEAR = 0

"""GrrCON presentations archive scraper."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from scrapers.archives import ArchiveStore
from scrapers.enrichment import EnrichmentCatalog
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record
from scrapers.domains import detect_domains
from scrapers.http import HttpClient


@dataclass(frozen=True, slots=True)
class GrrconResult:
    source: str
    endorsements: int
    output: Path


class GrrconScraper:
    assessor_id = "grrcon"
    scraper_id = "grrcon-presentations"

    def __init__(self, *, assessor_file=Path("data/assessors/grrcon/grrcon.json"),
                 html_directory=Path("data/archives/html/grrcon.zip"),
                 output_directory=Path("tmp/endorsements/grrcon"),
                 profile_directory=Path("tmp/profiles/grrcon"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8"))["links"]["processUrls"]
        self.archive = ArchiveStore(Path(html_directory))
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[GrrconResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            talks = parse_grrcon(body, source)
            if not talks:
                continue
            output = self.output_directory / f"{Path(member).stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            records = []
            names = {}
            for title, name, description, year in talks:
                subtitle = f"GrrCON {year}"
                records.append(build_endorsement_record(
                    name=name, label=title, description=description or title,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle=subtitle, url=source, year=year,
                    domains=detect_domains(title, description),
                    evidence_links=self.catalog.links_for(assessor_id=self.assessor.id,
                                                         label=title, subtitle=subtitle),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"{Path(member).stem}.json").write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(GrrconResult(source, len(records), output))
        return results


def parse_grrcon(html: bytes | str, source_url: str) -> list[tuple[str, str, str, int]]:
    soup = BeautifulSoup(html, "html.parser")
    year_match = re.search(r"20\d{2}", source_url)
    year = int(year_match.group()) if year_match else 2024
    rows = []
    headings = soup.find_all("h2")
    for heading in headings:
        if heading.get_text(" ", strip=True).casefold() in {"keynotes", "search", "downloads"}:
            continue
        title_node = heading.find_next("h3")
        if not title_node:
            continue
        first = " ".join(heading.get_text(" ", strip=True).split())
        second = " ".join(title_node.get_text(" ", strip=True).split())
        if year >= 2024:
            title, speaker = first, second
        else:
            title, speaker = second, first
        if not title or title.startswith("[") or not speaker:
            continue
        keynote = re.match(r"^(?:thursday morning|thursday afternoon|friday morning|friday wrap up)\s+keynote\s*[–—-]\s*(.+)$", speaker, re.IGNORECASE)
        if keynote:
            speaker = keynote.group(1).strip()
        wrapper = heading.parent if isinstance(heading.parent, Tag) else heading
        description = " ".join(wrapper.get_text(" ", strip=True).split())
        description = description.replace(speaker, "", 1).replace(title, "", 1).strip()
        for person in _split_speakers(speaker):
            rows.append((title, person, description or title, year))
    unique = {(r[0].casefold(), r[1].casefold()): r for r in rows}
    return list(unique.values())


def _split_speakers(value: str) -> list[str]:
    value = " ".join(value.replace("\xa0", " ").split())
    parts = re.split(r"\s*(?:&|\band\b)\s*", value, flags=re.IGNORECASE)
    candidates = [piece.strip(" ,") for part in parts for piece in part.split(",")]
    role_only = {"ciso", "cto", "ceo", "moderator", "panelist", "speaker"}
    return list(dict.fromkeys(candidate for candidate in candidates if candidate and candidate.casefold() not in role_only))


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_grrcon(body, source_url)


