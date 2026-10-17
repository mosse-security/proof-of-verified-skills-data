"""Standalone parser for archive page https://www.microsoft.com/en-us/msrc/blog/2019/11/bluehat-seattle-videos-are-online."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-013-en-us-msrc-blog-2019-11-bluehat-seattle-videos-are-online'
SOURCE_URL = 'https://www.microsoft.com/en-us/msrc/blog/2019/11/bluehat-seattle-videos-are-online'
YEAR = 2019

"""Parser for Microsoft's BlueHat MSRC schedule and session posts."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from scrapers.archives import ArchiveStore
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record
from scrapers.enrichment import EnrichmentCatalog


@dataclass(frozen=True, slots=True)
class BlueHatResult:
    source: str
    endorsements: int
    output: Path


@dataclass(frozen=True, slots=True)
class BlueHatEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int

    def to_record(self, assessor, enrichment_catalog=None):
        subtitle = f"BlueHat {self.year}" if self.year else "Microsoft BlueHat"
        links = enrichment_catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=subtitle) if enrichment_catalog else ()
        return build_endorsement_record(name=self.name, label=self.title, description=self.description or self.title, endorsement_type="presentation", assessor=assessor, subtitle=subtitle, url=self.url, year=self.year, domains=(), evidence_links=links)


class BlueHatScraper:
    assessor_id = "bluehat"
    scraper_id = "bluehat-sessions"

    def __init__(self, *, assessor_file=Path("data/assessors/bluehat.json"), html_directory=Path("data/archives/html/bluehat.zip"), output_directory=Path("tmp/endorsements/bluehat"), profile_directory=Path("tmp/profiles/bluehat"), overwrite=True, timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.enrichment_catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        document = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        self.sources = document.get("links", {}).get("processUrls", [])
        self.archive = ArchiveStore(Path(html_directory))
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id, timeout=timeout, retries=retries).fetch

    def run(self) -> list[BlueHatResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/") or "index.html"
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            rows = parse_bluehat(body, source)
            if not rows:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", member.casefold()).strip("-")
            output = self.output_directory / f"{slug}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps([r.to_record(self.assessor, self.enrichment_catalog) for r in rows], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = {r.name: {"name": r.name, "biography": "", "contact": []} for r in rows}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"{slug}.json").write_text(json.dumps(list(profiles.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(BlueHatResult(source, len(rows), output))
        return results


def parse_bluehat(html: bytes | str, source_url: str) -> list[BlueHatEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    year_match = re.search(r"20\d{2}", source_url + " " + soup.get_text(" ", strip=True)[:4000])
    year = int(year_match.group()) if year_match else 0
    rows: list[BlueHatEndorsement] = []
    for table in soup.find_all("table"):
        table_rows = table.find_all("tr")
        header_row = next((row for row in table_rows if "speaker" in row.get_text(" ", strip=True).casefold()), None)
        header = [c.get_text(" ", strip=True).casefold() for c in header_row.find_all(["td", "th"])] if header_row else []
        speaker_index = header.index("speaker") if "speaker" in header else (2 if len(header) >= 4 else 1)
        title_index = header.index("talk title") if "talk title" in header else (header.index("talk subject") if "talk subject" in header else -1)
        data_rows = table_rows[table_rows.index(header_row) + 1:] if header_row else table_rows[1:]
        for tr in data_rows:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) < 3 or any(c.casefold() in {"speaker", "talk subject", "talk title"} for c in cells):
                continue
            title = cells[title_index] if title_index >= 0 and title_index < len(cells) else cells[-1]
            row_speaker_index = 1 if len(cells) < len(header) and len(header) >= 4 else speaker_index
            speaker_cell = cells[row_speaker_index] if row_speaker_index < len(cells) else ""
            if not speaker_cell or not title or speaker_cell.casefold() in {"break", "lunch"}:
                continue
            for name in _names(speaker_cell):
                rows.append(BlueHatEndorsement(name, title, title, source_url, year))
    for heading in soup.find_all("h4"):
        title = heading.get_text(" ", strip=True)
        if title.casefold() in {"keynote", "categories", "tags"}:
            continue
        text_parts = []
        for sibling in heading.find_all_next(["h4", "h3", "p", "li"]):
            if sibling is not heading and sibling.name in {"h4", "h3"}:
                break
            if sibling is not heading:
                text_parts.append(sibling.get_text(" ", strip=True))
        text = " ".join(text_parts)
        match = re.search(r"Speakers?:\s*(.+?)(?:\s+Abstract:\s*(.*))?$", text)
        if match:
            desc = match.group(2) or title
            for name in _names(match.group(1)):
                rows.append(BlueHatEndorsement(name, title, desc, source_url, year))
    for node in soup.find_all(string=lambda value: value and "Presented by" in value):
        line = " ".join(str(node).split())
        match = re.match(r"(.+?)\s+Presented by\s+(.+?)(?:\s+from\s+.+)?$", line)
        if match:
            title = match.group(1).strip("- ")
            for name in _names(match.group(2)):
                rows.append(BlueHatEndorsement(name, title, title, source_url, year))
    return list({(r.name.casefold(), r.title.casefold(), r.url): r for r in rows}.values())


def _names(value: str) -> list[str]:
    value = re.sub(r"\([^)]*\)", "", value)
    people: list[str] = []
    for part in re.split(r";|\s*&\s*", value):
        part = re.split(r"\s+-\s+", part, maxsplit=1)[0].strip(" ,;â€“-")
        if not part:
            continue
        if " and " in part and not re.search(r"\b(?:director|president|manager|architect|enterprise|security|general counsel)\b", part, re.I):
            subparts = re.split(r"\s+and\s+", part)
        else:
            subparts = [part]
        chunks = [chunk.strip() for subpart in subparts for chunk in subpart.split(",") if chunk.strip()]
        for chunk in chunks:
            words = chunk.split()
            # Old MSRC tables often concatenate multiple names without a comma.
            # Split at recognizable first-name boundaries while preserving titles
            # and multi-token surnames.
            starts = [i for i, word in enumerate(words) if i and word.rstrip(".,").casefold() in _FIRST_NAMES]
            boundaries = [0, *starts, len(words)]
            for start, end in zip(boundaries, boundaries[1:]):
                candidate = " ".join(words[start:end]).strip(" ,;â€“-")
                if len(candidate.split()) >= 2 and not re.search(r"\b(?:AM|PM)\b|\d:\d", candidate, re.I) and not candidate.casefold() in {"microsoft", "eclypsium", "elevate security", "g-research"}:
                    people.append(candidate)
    return list(dict.fromkeys(people))


_FIRST_NAMES = {
    "adam", "alex", "alban", "amy", "anubhav", "andrea", "arshan", "brian", "casey",
    "chris", "cristin", "daniel", "david", "dana", "emily", "everett", "fabio",
    "fred", "gabriel", "gunter", "haifei", "holly", "jagadeesh", "james", "jan", "jay", "jean-ian",
    "jeremiah", "jonathan", "jordan", "joseph", "karen", "katie", "kyle", "lee", "li",
    "luke", "marc", "marianne", "mario", "mark", "matti", "mechele", "merike", "michael",
    "mingbo", "mohammad", "moustafa", "nate", "naveed", "niek", "nico", "oran", "pasi",
    "ben", "pete", "peter", "rahul", "ram", "ravi", "rich", "rob", "robert", "ross", "saman", "sam",
    "saruhan", "satoshi", "samuel", "sean", "sergey", "skip", "stephen", "stirling", "sven", "thomas",
    "tim", "tony", "travis", "william", "yong", "yunhai", "zisis", "zhuo", "siva"
}


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_bluehat(body, source_url)


