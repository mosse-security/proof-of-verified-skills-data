"""Standalone parser for archive page https://www.layerone.org/archives/layerone-2008/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-007-archives-layerone-2008'
SOURCE_URL = 'https://www.layerone.org/archives/layerone-2008/'
YEAR = 2008

"""Layer One historical speaker lineup parser."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from scrapers.archives import ArchiveStore
from scrapers.domains import detect_domains
from scrapers.enrichment import EnrichmentCatalog
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class LayerOneResult:
    source: str
    endorsements: int
    output: Path


def parse_layer_one(html: bytes | str, source_url: str) -> list[tuple[str, str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    if "/archives/layerone-" in source_url:
        entry = soup.select_one(".entry") or soup
        text = " ".join(entry.get_text(" ", strip=True).split())
        pattern = re.compile(
            r"Presenter:\s*(.+?)\s+Topic:\s*(.+?)(?=\s+Slides:|\s+Presenter:|\s+Photos & Media|\s+Pages|$)",
            re.I,
        )
        for match in pattern.finditer(text):
            presenters = re.split(r"\s*(?:;|&|\band\b)\s*", match.group(1), flags=re.I)
            title = match.group(2).strip(" .")
            for name in presenters:
                name = name.strip(" ,")
                if name and title:
                    rows.append((title, name, "", source_url))
        return rows
    for link in soup.select(".entry a[href*='/speakers/#']"):
        text = " ".join(link.get_text(" ", strip=True).split())
        parts = re.split(r"\s+[â€“â€”-]\s+", text, maxsplit=1)
        if len(parts) != 2 or not all(parts):
            continue
        rows.append((parts[1].strip(), parts[0].strip(), "", source_url))
    return rows


class LayerOneScraper:
    assessor_id = "layer-one"
    scraper_id = "layer-one-speakers"

    def __init__(self, *, assessor_file=Path("data/assessors/layer-one/layer-one.json"),
                 html_directory=Path("data/archives/html/layer-one.zip"),
                 output_directory=Path("tmp/endorsements/layer-one"),
                 profile_directory=Path("tmp/profiles/layer-one"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        data = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        self.sources = data["links"].get("processUrls", [])
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[LayerOneResult]:
        results = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year_match = re.search(r"20\d{2}", source)
            year = int(year_match.group()) if year_match else 0
            rows = parse_layer_one(body, source)
            subtitle = f"Layer One {year}" if year else "Layer One"
            records = [build_endorsement_record(
                name=name, label=title, description=description or title,
                endorsement_type="presentation", assessor=self.assessor,
                subtitle=subtitle, url=url, year=year,
                domains=detect_domains(title, description),
                evidence_links=self.catalog.links_for(assessor_id=self.assessor.id,
                    label=title, subtitle=subtitle),
            ) for title, name, description, url in rows]
            names = [{"name": name, "biography": "", "contact": []}
                     for _, name, _, _ in rows]
            stem = f"layer-one-{year}" if year else "layer-one"
            output = self.output_directory / f"{stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(names, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(LayerOneResult(source, len(records), output))
        return results


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_layer_one(body, source_url)


