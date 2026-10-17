"""Insomni'hack output runner; extraction lives in one module per archive page."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from ..archives import ArchiveStore
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..identity_registry import IdentityRegistry
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class InsomnihackResult:
    source: str
    endorsements: int
    output: Path


@dataclass(frozen=True, slots=True)
class InsomnihackEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int

    def to_record(self, assessor: AssessorMetadata, catalog: EnrichmentCatalog | None = None) -> dict[str, object]:
        subtitle = f"Insomni'hack {self.year}" if self.year else "Insomni'hack"
        links = catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=subtitle) if catalog else ()
        return build_endorsement_record(
            name=self.name, label=self.title, description=self.description or self.title,
            endorsement_type="presentation", assessor=assessor, subtitle=subtitle,
            url=self.url, year=self.year, domains=(), evidence_links=links,
        )


class InsomnihackScraper:
    assessor_id = "insomnihack"
    scraper_id = "insomnihack-talks"

    def __init__(self, *, assessor_file=Path("data/assessors/insomnihack.json"), html_directory=Path("data/archives/html/insomnihack.zip"), output_directory=Path("tmp/endorsements/insomnihack"), profile_directory=Path("tmp/profiles/insomnihack"), overwrite=True, timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.identity_registry = IdentityRegistry.for_assessor(self.assessor_id)
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8")).get("links", {}).get("processUrls", [])
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id, timeout=timeout, retries=retries).fetch

    def run(self) -> list[InsomnihackResult]:
        from .insomnihack import PAGE_PARSERS

        results = []
        for source in self.sources:
            member = _member(source)
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year = _year(source)
            parser = PAGE_PARSERS.get(year)
            if parser is None:
                raise ValueError(f"No page-owned parser registered for Insomni'hack {year}")
            rows = parser(body, source)
            if not rows:
                raise ValueError(f"Page parser emitted no records for Insomni'hack {year}: {source}")
            output = self.output_directory / f"insomnihack-{year}.json"
            rows = [row for row in rows if self.identity_registry.allows(row.name)]
            records = [row.to_record(self.assessor, self.catalog) for row in rows]
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = {row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"insomnihack-{year}.json").write_text(json.dumps(list(profiles.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(InsomnihackResult(source, len(rows), output))
        return results


def _year(source: str) -> int:
    match = re.search(r"edition-(20\d{2})", source)
    return int(match.group(1)) if match else 0


def _member(url: str) -> str:
    return urlsplit(url).path.strip("/") + "/index.html"


