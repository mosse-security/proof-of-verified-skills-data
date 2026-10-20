"""IEEE Symposium on Security and Privacy accepted-paper scraper."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from ..archives import ArchiveStore
from ..domains import detect_domains
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..identity_registry import clean_person_name
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class IeeeSpResult:
    source: str
    endorsements: int
    output: Path


def parse_ieee_sp(html: bytes | str, source_url: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select(".list-group-item"):
        title_link = item.select_one("b a")
        author_box = item.select_one(".authorlist")
        if not title_link or not author_box:
            continue
        title = " ".join(title_link.get_text(" ", strip=True).split())
        parts: list[str] = []
        for child in author_box.children:
            if isinstance(child, Tag) and child.name == "br":
                break
            if isinstance(child, Tag) and child.name == "sup":
                continue
            parts.append(child.get_text(" ", strip=False) if isinstance(child, Tag) else str(child))
        author_text = "".join(parts)
        for name in re.split(r"\s*,\s*", author_text):
            name = clean_person_name(re.sub(r"\s+", " ", name))
            if name:
                rows.append((title, name, source_url))
    return list(dict.fromkeys(rows))


class IeeeSpScraper:
    assessor_id = "ieee-sp"
    scraper_id = "ieee-sp-accepted-papers"

    def __init__(self, *, assessor_file=Path("data/assessors/ieee-sp/ieee-sp.json"),
                 html_directory=Path("data/archives/html/ieee-sp.zip"),
                 output_directory=Path("tmp/endorsements/ieee-sp"),
                 profile_directory=Path("tmp/profiles/ieee-sp"), overwrite=True,
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

    def run(self) -> list[IeeeSpResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            rows = parse_ieee_sp(body, source)
            records = []
            names: dict[str, dict[str, object]] = {}
            for title, name, url in rows:
                records.append(build_endorsement_record(
                    name=name, label=title, description=title,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle="IEEE S&P 2026", url=url, year=2026,
                    domains=detect_domains(title, title),
                    evidence_links=self.catalog.links_for(
                        assessor_id=self.assessor.id, label=title, subtitle="IEEE S&P 2026"),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            output = self.output_directory / "ieee-sp-2026.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(IeeeSpResult(source, len(records), output))
        return results


