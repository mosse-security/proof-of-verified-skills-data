"""USENIX Security technical-session and paper parser."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from ..archives import ArchiveStore
from ..domains import detect_domains
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class UsenixSecurityResult:
    source: str
    endorsements: int
    output: Path


def _year(source_url: str) -> int:
    match = re.search(r"usenixsecurity(\d{2})", source_url)
    return 2000 + int(match.group(1)) if match else 0


def _subtitle(year: int) -> str:
    return f"USENIX Security '{year % 100:02d}" if year else "USENIX Security"


def _authors(article: Tag) -> list[str]:
    field = article.select_one(".field-name-field-paper-people-text")
    if not field:
        return []
    names: list[str] = []
    for paragraph in field.select("p") or [field]:
        for child in paragraph.children:
            if isinstance(child, Tag) and child.name == "em":
                continue
            if isinstance(child, str):
                for value in re.split(r"\s*,\s*|\s+\band\b\s+", child, flags=re.IGNORECASE):
                    value = _clean_author(value)
                    if _valid_author(value):
                        names.append(value)
    if not names:
        text = " ".join(field.get_text(" ", strip=True).split())
        names = [_clean_author(part) for part in text.split(";") if _valid_author(_clean_author(part))]
    return list(dict.fromkeys(names))


def _clean_author(value: str) -> str:
    """Remove list-conjunctions that belong to the author separator."""
    return re.sub(r"^and\s+", "", " ".join(value.split()), flags=re.IGNORECASE).strip(" ,;\n\t")


def _valid_author(value: str) -> bool:
    value = " ".join(value.split())
    lowered = value.casefold()
    return bool(
        value and len(value) < 120 and re.search(r"[A-Za-z]", value)
        and not lowered.startswith(("originally presented", "proceedings", "abstract"))
        and not value.endswith((".", ":"))
    )


def parse_usenix_security(html: bytes | str, source_url: str) -> list[tuple[str, str, str, str, int]]:
    soup = BeautifulSoup(html, "html.parser")
    year = _year(source_url)
    rows: list[tuple[str, str, str, str, int]] = []
    for article in soup.select("article.node-paper"):
        title_link = article.select_one("h2 a[href]")
        if not title_link:
            continue
        title = " ".join(title_link.get_text(" ", strip=True).split())
        description_field = article.select_one(".field-name-field-paper-description-long")
        description = " ".join(description_field.get_text(" ", strip=True).split()) if description_field else title
        url = urljoin(source_url, title_link.get("href", ""))
        for name in _authors(article):
            rows.append((title, name, description, url, year))
    return rows


class UsenixSecurityScraper:
    assessor_id = "usenix-security"
    scraper_id = "usenix-security-papers"

    def __init__(self, *, assessor_file=Path("data/assessors/usenix-security/usenix-security.json"),
                 html_directory=Path("data/archives/html/usenix-security.zip"),
                 output_directory=Path("tmp/endorsements/usenix-security"),
                 profile_directory=Path("tmp/profiles/usenix-security"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        data = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        self.sources = data["links"].get("processUrls", [])
        self.archive = ArchiveStore(Path(html_directory))
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[UsenixSecurityResult]:
        results: list[UsenixSecurityResult] = []
        for source in self.sources:
            member = urlsplit(source).path.strip("/")
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year = _year(source)
            subtitle = _subtitle(year)
            rows = parse_usenix_security(body, source)
            records = []
            names: dict[str, dict[str, object]] = {}
            for title, name, description, url, row_year in rows:
                records.append(build_endorsement_record(
                    name=name, label=title, description=description,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle=subtitle, url=url, year=row_year,
                    domains=detect_domains(title, description),
                    evidence_links=self.catalog.links_for(
                        assessor_id=self.assessor.id, label=title, subtitle=subtitle),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            output = self.output_directory / f"usenix-security-{year}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(
                json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(UsenixSecurityResult(source, len(records), output))
        return results


