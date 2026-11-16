"""Mozilla Web and Services Bug Bounty Hall of Fame scraper."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from ..archives import ArchiveStore
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..identity_registry import clean_person_name, expand_person_names
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


SOURCE_URL = "https://www.mozilla.org/en-US/security/bug-bounty/web-hall-of-fame/"


@dataclass(frozen=True, slots=True)
class MozillaResult:
    source: str
    endorsements: int
    output: Path


class MozillaSecurityScraper:
    assessor_id = "mozilla-security"
    scraper_id = "mozilla-web-hall-of-fame"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/mozilla-security/mozilla-security.json"),
        html_directory: Path = Path("data/archives/html/mozilla-security.zip"),
        output_directory: Path = Path("tmp/endorsements/mozilla-security"),
        profile_directory: Path = Path("tmp/profiles/mozilla-security"),
        overwrite: bool = True,
        timeout: float = 30,
        retries: int = 2,
    ) -> None:
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(
            assessor_id=self.assessor_id,
            scraper_id=self.scraper_id,
            timeout=timeout,
            retries=retries,
        ).fetch

    def run(self) -> list[MozillaResult]:
        member = "hall-of-fame.html"
        body = self.archive.read(member)
        if body is None or self.overwrite:
            response = self.fetch(Request(SOURCE_URL))
            if response.status != 200:
                raise RuntimeError(f"Mozilla Hall of Fame returned HTTP {response.status}")
            body = response.body
            self.archive.write(member, body)
        rows = _parse_page(body)
        records = [self._record(row) for row in rows]
        output = self.output_directory / "mozilla-web-hall-of-fame.json"
        profile_output = self.profile_directory / "mozilla-web-hall-of-fame.json"
        if self.overwrite or not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        profiles = [{"name": row["name"], "biography": "", "contact": []} for row in rows]
        if self.overwrite or not profile_output.exists():
            profile_output.parent.mkdir(parents=True, exist_ok=True)
            profile_output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return [MozillaResult(SOURCE_URL, len(records), output)]

    def _record(self, row: dict[str, object]) -> dict:
        year = int(row["year"])
        quarter = str(row["quarter"])
        return build_endorsement_record(
            name=str(row["name"]),
            label="Mozilla Web and Services Bug Bounty Hall of Fame",
            subtitle=f"{year} {quarter}",
            description=f"Publicly credited by Mozilla in the Web and Services Bug Bounty Hall of Fame for {quarter} {year}.",
            endorsement_type="bug_bounty",
            assessor=self.assessor,
            url=SOURCE_URL,
            year=year,
            domains=("vulnerability-research",),
            evidence_links=({"url": SOURCE_URL, "title": "Mozilla Web and Services Bug Bounty Hall of Fame"},),
        )


def _parse_page(body: bytes) -> list[dict[str, object]]:
    soup = BeautifulSoup(body, "html.parser")
    rows: list[dict[str, object]] = []
    year: int | None = None
    quarter = "Unknown quarter"
    for element in soup.find_all(["h3", "h4", "li"]):
        text = element.get_text(" ", strip=True)
        if element.name == "h3":
            match = re.fullmatch(r"(20\d{2})", text)
            if match:
                year = int(match.group(1))
            continue
        if element.name == "h4":
            quarter = text
            continue
        if year is None or not text:
            continue
        for name in _split_credit(text):
            rows.append({"name": name, "year": year, "quarter": quarter})
    return rows


def _split_credit(value: str) -> list[str]:
    value = re.split(r"\s+(?:with|from|of)\s+|\s+-\s+|\s+\([^)]*\)", value, maxsplit=1, flags=re.IGNORECASE)[0]
    names: list[str] = []
    for part in expand_person_names(value):
        cleaned = clean_person_name(part).strip(" .-:,;")
        if cleaned and cleaned.casefold() not in {name.casefold() for name in names}:
            names.append(cleaned)
    return names
