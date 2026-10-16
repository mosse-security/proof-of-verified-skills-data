"""ACM CCS accepted-paper scraper."""
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
class AcmCcsResult:
    source: str
    endorsements: int
    output: Path


def parse_acm_ccs(html: bytes | str, source_url: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[tuple[str, str, str]] = []
    for table in soup.select("table.accepted-papers-table"):
        for row in table.select("tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            title = " ".join(cells[0].get_text(" ", strip=True).split())
            for line in cells[1].stripped_strings:
                name = re.sub(r"\s*\([^)]*\)\s*$", "", line).strip()
                name = re.sub(r"\s+", " ", name)
                if title and name:
                    rows.append((title, name, source_url))
    return list(dict.fromkeys(rows))


class AcmCcsScraper:
    assessor_id = "acm-ccs"
    scraper_id = "acm-ccs-accepted-papers"

    def __init__(self, *, assessor_file=Path("data/assessors/acm-ccs.json"),
                 html_directory=Path("data/archives/html/acm-ccs.zip"),
                 output_directory=Path("data/tmp/endorsements/acm-ccs"),
                 profile_directory=Path("data/tmp/profiles/acm-ccs"), overwrite=True,
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

    def run(self) -> list[AcmCcsResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            rows = parse_acm_ccs(body, source)
            records = []
            names: dict[str, dict[str, object]] = {}
            for title, name, url in rows:
                records.append(build_endorsement_record(
                    name=name, label=title, description=title,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle="ACM CCS 2026", url=url, year=2026,
                    domains=detect_domains(title, title),
                    evidence_links=self.catalog.links_for(
                        assessor_id=self.assessor.id, label=title, subtitle="ACM CCS 2026"),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            output = self.output_directory / "acm-ccs-2026.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(AcmCcsResult(source, len(records), output))
        return results
