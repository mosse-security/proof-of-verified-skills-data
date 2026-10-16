"""NDSS accepted-paper and abstract scraper."""
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
class NdssResult:
    source: str
    endorsements: int
    output: Path


def _authors(text: str) -> list[str]:
    names = re.findall(r"([^,()]+?)\s*\([^)]*\)(?:,|$)", text)
    return list(dict.fromkeys(name.strip() for name in names if name.strip()))


def _year(url: str) -> int:
    match = re.search(r"ndss(20\d{2})", url)
    return int(match.group(1)) if match else 0


def _subtitle(year: int) -> str:
    return f"NDSS {year}" if year else "NDSS"


def parse_index(html: bytes | str, source_url: str) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select(".pt-cv-content-item"):
        link = item.select_one("h2.pt-cv-title a[href]")
        authors = item.select_one(".pt-cv-ctf-display_authors")
        if link and authors:
            rows.append((link.get_text(" ", strip=True), authors.get_text(" ", strip=True), link["href"]))
    return rows


def parse_detail(html: bytes | str, fallback_title: str, fallback_authors: str) -> tuple[str, list[str], str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h1")
    paper = soup.select_one(".paper-data")
    title_text = title.get_text(" ", strip=True) if title else fallback_title
    paragraphs = paper.select("p") if paper else []
    author_text = paragraphs[0].get_text(" ", strip=True) if paragraphs else fallback_authors
    abstract = paragraphs[1].get_text(" ", strip=True) if len(paragraphs) > 1 else title_text
    return title_text, _authors(author_text), abstract or title_text


class NdssScraper:
    assessor_id = "ndss"
    scraper_id = "ndss-accepted-papers"

    def __init__(self, *, assessor_file=Path("data/assessors/ndss.json"),
                 html_directory=Path("data/archives/html/ndss.zip"),
                 output_directory=Path("data/tmp/endorsements/ndss"),
                 profile_directory=Path("data/tmp/profiles/ndss"), overwrite=True,
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

    def _get(self, url: str) -> bytes:
        member = urlsplit(url).path.strip("/")
        body = self.archive.read(member)
        if body is None:
            body = self.fetch(Request(url)).body
            self.archive.write(member, body)
        return body

    def run(self) -> list[NdssResult]:
        results = []
        for source in self.sources:
            year = _year(source)
            subtitle = _subtitle(year)
            rows = parse_index(self._get(source), source)
            records = []
            names: dict[str, dict[str, object]] = {}
            for fallback_title, fallback_authors, detail_url in rows:
                title, authors, abstract = parse_detail(self._get(detail_url), fallback_title, fallback_authors)
                for name in authors:
                    records.append(build_endorsement_record(
                        name=name, label=title, description=abstract,
                        endorsement_type="presentation", assessor=self.assessor,
                        subtitle=subtitle, url=detail_url, year=year,
                        domains=detect_domains(title, abstract),
                        evidence_links=self.catalog.links_for(
                            assessor_id=self.assessor.id, label=title, subtitle=subtitle),
                    ))
                    names[name] = {"name": name, "biography": "", "contact": []}
            output = self.output_directory / f"ndss-{year}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(NdssResult(source, len(records), output))
        return results
