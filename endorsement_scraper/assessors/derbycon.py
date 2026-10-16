"""Historical DerbyCon schedule scraper using archived official pages."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..archives import ArchiveStore
from ..domains import detect_domains
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class DerbyConResult:
    source: str
    endorsements: int
    output: Path


def _year(source: str) -> int:
    match = re.search(r"(?:web/\d{14}/)?(?:https?://)?(?:www\.)?derbycon\.com/(?:[^/]+/)*(20(?:1[2-9]))", source)
    if match:
        return int(match.group(1))
    match = re.search(r"web/(20(?:1[2-9]))\d{10}/", source)
    return int(match.group(1)) if match else 2017


def parse_derbycon(html: bytes | str, source_url: str) -> list[tuple[str, str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, str, str]] = []
    for event in soup.select("a.sched-event[title]"):
        raw = " ".join(event.get("title", "").split())
        if " - " not in raw:
            continue
        name, title = raw.split(" - ", 1)
        if not name or not title or title.lower() in {"lunch", "break", "registration"}:
            continue
        event_id = event.get("data-event-id")
        description = title
        if event_id:
            detail = soup.select_one(f'.sched-event-fulldescription[data-event-id="{event_id}"] p')
            if detail:
                description = " ".join(detail.get_text(" ", strip=True).split()) or title
        rows.append((title, name, description, source_url))
    if rows:
        return list(dict.fromkeys(rows))
    for cell in soup.select("table tbody tr td:not(:first-child)"):
        text = " ".join(cell.get_text(" ", strip=True).split())
        if not text or text.lower() in {"lunch", "open", "intro"}:
            continue
        parts = re.split(r"\s+[–—]\s+|\s+-\s+", text)
        if len(parts) < 2:
            continue
        title = parts[0].strip()
        author_text = parts[-1].strip()
        if not title or not author_text:
            continue
        for name in re.split(r"\s+and\s+|\s*&\s*", author_text, flags=re.IGNORECASE):
            name = re.sub(r"\s*\([^)]*\)", "", name).strip(" .")
            if name:
                rows.append((title, name, title, source_url))
    return list(dict.fromkeys(rows))


class DerbyConScraper:
    assessor_id = "derbycon"
    scraper_id = "derbycon-archived-schedules"

    def __init__(self, *, assessor_file=Path("data/assessors/derbycon.json"),
                 html_directory=Path("data/archives/html/derbycon.zip"),
                 output_directory=Path("data/tmp/endorsements/derbycon"),
                 profile_directory=Path("data/tmp/profiles/derbycon"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8"))["links"]["processUrls"]
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[DerbyConResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year = _year(source)
            rows = parse_derbycon(body, source)
            records = []
            names: dict[str, dict[str, object]] = {}
            for title, name, description, url in rows:
                records.append(build_endorsement_record(
                    name=name, label=title, description=description,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle=f"DerbyCon {year}", url=url, year=year,
                    domains=detect_domains(title, description),
                    evidence_links=self.catalog.links_for(
                        assessor_id=self.assessor.id, label=title, subtitle=f"DerbyCon {year}"),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")[-60:]
            output = self.output_directory / f"derbycon-{year}-{slug}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(DerbyConResult(source, len(records), output))
        return results
