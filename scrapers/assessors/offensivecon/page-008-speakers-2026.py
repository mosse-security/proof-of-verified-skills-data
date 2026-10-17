"""Standalone parser for archive page https://www.offensivecon.org/speakers/2026/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-008-speakers-2026'
SOURCE_URL = 'https://www.offensivecon.org/speakers/2026/'
YEAR = 2026

"""OffensiveCon historical speaker and agenda archive parser."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from scrapers.archives import ArchiveStore
from scrapers.enrichment import EnrichmentCatalog
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class OffensiveConResult:
    source: str
    endorsements: int
    output: Path


@dataclass(frozen=True, slots=True)
class OffensiveConEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int

    def to_record(self, assessor: AssessorMetadata, catalog: EnrichmentCatalog | None = None) -> dict[str, object]:
        subtitle = f"OffensiveCon {self.year}" if self.year else "OffensiveCon"
        links = catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=subtitle) if catalog else ()
        return build_endorsement_record(
            name=self.name, label=self.title, description=self.description or self.title,
            endorsement_type="presentation", assessor=assessor, subtitle=subtitle,
            url=self.url, year=self.year, domains=(), evidence_links=links,
        )


class OffensiveConScraper:
    assessor_id = "offensivecon"
    scraper_id = "offensivecon-talks"

    def __init__(self, *, assessor_file=Path("data/assessors/offensivecon/offensivecon.json"), html_directory=Path("data/archives/html/offensivecon.zip"), output_directory=Path("tmp/endorsements/offensivecon"), profile_directory=Path("tmp/profiles/offensivecon"), overwrite=True, timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        # Use an absolute archive path so Windows can atomically replace the
        # ZIP while it is being extended across multiple historical pages.
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8")).get("links", {}).get("processUrls", [])
        # Detail links are numerous; fail quickly on an unavailable page and
        # retain the agenda title rather than blocking the whole conference.
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id, timeout=min(timeout, 8), retries=0).fetch

    def run(self) -> list[OffensiveConResult]:
        results = []
        for source in self.sources:
            member = _member(source)
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year = _year(source, body)
            rows = parse_offensivecon(body, source, year)
            rows = self._hydrate_details(rows, source, year)
            if not rows:
                continue
            output = self.output_directory / f"offensivecon-{year}.json"
            records = [row.to_record(self.assessor, self.catalog) for row in rows]
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = {row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"offensivecon-{year}.json").write_text(json.dumps(list(profiles.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(OffensiveConResult(source, len(rows), output))
        return results

    def _hydrate_details(self, rows: list[OffensiveConEndorsement], source: str, year: int) -> list[OffensiveConEndorsement]:
        hydrated = []
        descriptions: dict[str, str] = {}
        for row in rows:
            if not row.url or row.url == source or row.description != row.title:
                hydrated.append(row)
                continue
            if row.url in descriptions:
                description = descriptions[row.url]
            else:
                member = _member(row.url)
                body = self.archive.read(member)
                if body is None:
                    try:
                        body = self.fetch(Request(row.url)).body
                        self.archive.write(member, body)
                    except Exception:
                        body = None
                description = _detail_description(body) if body else row.description
                descriptions[row.url] = description or row.description
            hydrated.append(OffensiveConEndorsement(row.name, row.title, description or row.description, row.url, year))
        return hydrated


def parse_offensivecon(html: bytes | str, source_url: str, year: int) -> list[OffensiveConEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    rows = _parse_speaker_cards(soup, source_url, year)
    if not rows:
        rows = _parse_agenda(soup, source_url, year)
    unique = {(r.name.casefold(), r.title.casefold(), r.url): r for r in rows if _valid_name(r.name) and r.title}
    return list(unique.values())


def _parse_speaker_cards(soup: BeautifulSoup, source_url: str, year: int) -> list[OffensiveConEndorsement]:
    rows = []
    # Speaker index pages use h4 (speaker) followed by h5 (talk title).
    # Agenda pages also contain h3/h4 headings for venue and day labels, so
    # do not treat those as speaker cards.
    for speaker_heading in soup.find_all("h4"):
        title_heading = speaker_heading.find_next(["h5", "h4"])
        if not title_heading or title_heading.name == speaker_heading.name and title_heading is not speaker_heading:
            continue
        raw_name = speaker_heading.get_text(" ", strip=True)
        title = title_heading.get_text(" ", strip=True)
        if not _valid_name(raw_name) or not title or title.casefold() in {"read more", "bio", "address", "berlin", "the venue"}:
            continue
        description_parts = []
        for paragraph in speaker_heading.find_all_next("p"):
            if paragraph.find_previous(["h4", "h3"]) is not speaker_heading:
                break
            text = paragraph.get_text(" ", strip=True)
            if text:
                description_parts.append(text)
        link = _detail_link(title_heading, source_url)
        for name in _split_names(raw_name):
            rows.append(OffensiveConEndorsement(name, title, " ".join(description_parts) or title, link, year))
    return rows


def _parse_agenda(soup: BeautifulSoup, source_url: str, year: int) -> list[OffensiveConEndorsement]:
    rows = []
    for entry in soup.select(".row-agenda"):
        text = entry.get_text(" ", strip=True)
        link = entry.find("a", href=True)
        if " by " not in text.casefold() or len(text) < 12:
            continue
        # Remove the time prefix and the Read more link before splitting.
        text = re.sub(r"^\s*\d{1,2}:\d{2}\s*[-â€“]\s*\d{1,2}:\d{2}\s*", "", text)
        text = re.sub(r"\s*Read more\s*$", "", text, flags=re.I)
        title, names = re.split(r"\s+by\s+", text, maxsplit=1, flags=re.I)
        title = re.sub(r"^keynote\s*[-:]?\s*", "", title, flags=re.I).strip()
        if any(term in title.casefold() for term in ("opening remarks", "welcome address", "closing remarks", "winners announcement")):
            continue
        detail_url = urljoin(source_url, link["href"]) if link else source_url
        for name in _split_names(names):
            rows.append(OffensiveConEndorsement(name, title, title, detail_url, year))
    return rows


def _detail_description(body: bytes) -> str:
    soup = BeautifulSoup(body, "html.parser")
    abstract = next((heading for heading in soup.find_all(["h2", "h3", "h4"]) if "abstract" in heading.get_text(" ", strip=True).casefold()), None)
    paragraphs = []
    if abstract:
        for paragraph in abstract.find_all_next("p"):
            if paragraph.find_previous(["h2", "h3", "h4"]) is not abstract:
                break
            text = paragraph.get_text(" ", strip=True)
            if text:
                paragraphs.append(text)
    if not paragraphs:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(" ", strip=True)]
    return " ".join(paragraphs).strip()


def _detail_link(node: Tag, source_url: str) -> str:
    link = node.find("a", href=True) or node.find_next("a", href=True)
    return urljoin(source_url, link["href"]) if link else source_url


def _split_names(value: str) -> list[str]:
    value = re.sub(r"\s+", " ", value).strip(" .")
    parts = re.split(r",\s+|\s+and\s+|\s*&\s*|\s+//\s+", value, flags=re.IGNORECASE)
    names = []
    for part in parts:
        part = re.sub(r"\s*(?:\([^)]*\)|\[[^]]*\])\s*$", "", part)
        part = re.sub(r"\s+(?:aka|a\.k\.a\.)\s+.*$", "", part, flags=re.IGNORECASE)
        part = re.sub(r"\s*`[^`]+`\s*", " ", part)
        part = re.sub(r"^and\s+", "", part, flags=re.IGNORECASE).strip(" .")
        if _valid_name(part):
            names.append(part)
    return names


def _valid_name(value: str) -> bool:
    lowered = value.casefold()
    return bool(value and len(value) < 100 and not any(x in lowered for x in ("coffee", "lunch", "remarks", "registration", "break", "party", "welcome")))


def _year(source: str, body: bytes) -> int:
    match = re.search(r"\b(20\d{2})\b", source)
    if match:
        return int(match.group(1))
    match = re.search(r"\b(20\d{2})\b", BeautifulSoup(body, "html.parser").get_text(" ", strip=True)[:3000])
    return int(match.group(1)) if match else 0


def _member(url: str) -> str:
    path = urlsplit(url).path.strip("/")
    return path or "index.html"


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_offensivecon(body, source_url, 2026)


