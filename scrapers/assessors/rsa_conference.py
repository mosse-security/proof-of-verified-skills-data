"""RSA Conference agenda and speaker-directory scraper."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from ..archives import ArchiveStore
from ..base import CollectionScraperContext, CollectionScraperResult
from ..domains import detect_domains
from ..enrichment import EnrichmentCatalog
from ..http import FetchError, HttpClient
from ..identity_registry import clean_person_name
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class RsaEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int
    subtitle: str


@dataclass(frozen=True, slots=True)
class RsaResult:
    source: str
    year: int
    endorsements: int
    output: Path


_SESSION_PATH = re.compile(r"/session/", re.IGNORECASE)
_YEAR_RE = re.compile(r"(?:us|usa|events/)(?P<year>20\d{2}|\d{2})", re.IGNORECASE)
_NON_PERSON = re.compile(
    r"^(?:speaker|speakers|session participant(?:s)?|moderator|panelist|track|agenda|"
    r"available on demand|not recorded|reserve seat|add to schedule)$",
    re.IGNORECASE,
)


def rsa_year(source_url: str) -> int:
    match = _YEAR_RE.search(source_url)
    if not match:
        raise ValueError(f"Cannot determine RSA Conference year from {source_url}")
    value = int(match.group("year"))
    return 2000 + value if value < 100 else value


def parse_rsa(html: bytes | str, source_url: str, year: int | None = None) -> list[RsaEndorsement]:
    """Parse legacy RSA agenda tables and modern RainFocus catalogs."""

    soup = BeautifulSoup(html, "html.parser")
    resolved_year = year or rsa_year(source_url)
    rows = _parse_rainfocus(soup, source_url, resolved_year)
    if not rows:
        rows = _parse_legacy_tables(soup, source_url, resolved_year)
    unique: dict[tuple[str, str, str], RsaEndorsement] = {}
    for row in rows:
        unique[(row.name.casefold(), row.title.casefold(), row.url)] = row
    return list(unique.values())


def _parse_rainfocus(soup: BeautifulSoup, source_url: str, year: int) -> list[RsaEndorsement]:
    rows: list[RsaEndorsement] = []
    for link in soup.select("a[href]"):
        href = str(link.get("href", ""))
        if not _SESSION_PATH.search(href):
            continue
        title = _clean_text(link.get_text(" ", strip=True))
        if not _valid_title(title):
            continue
        container: Tag = link
        for _ in range(6):
            parent = container.parent
            if not isinstance(parent, Tag):
                break
            container = parent
            text = _clean_text(container.get_text(" ", strip=True))
            if len(text) >= len(title) + 20:
                break
        speakers = _speaker_nodes(container)
        description = _description(container, title)
        url = urljoin(source_url, href)
        for name in speakers:
            rows.append(RsaEndorsement(name, title, description, url, year, f"RSA Conference {year}"))
    return rows


def _parse_legacy_tables(soup: BeautifulSoup, source_url: str, year: int) -> list[RsaEndorsement]:
    rows: list[RsaEndorsement] = []
    for tr in soup.select("table tr"):
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in tr.select("th, td")]
        if len(cells) < 2:
            continue
        joined = " | ".join(cells)
        if not re.search(r"\b(?:speaker|presenter|panelist)s?\b", joined, re.I):
            continue
        title = next((cell for cell in cells if _valid_title(cell)), "")
        if not title:
            continue
        speaker_text = " | ".join(cell for cell in cells if re.search(r"\b(?:speaker|presenter|panelist)s?\b", cell, re.I))
        names = _split_names(re.sub(r"^(?:speakers?|presenters?|panelists?)\s*:\s*", "", speaker_text, flags=re.I))
        for name in names:
            rows.append(RsaEndorsement(name, title, joined, source_url, year, f"RSA Conference {year}"))
    return rows


def _speaker_nodes(container: Tag) -> list[str]:
    candidates: list[str] = []
    for node in container.select("p[data-test^='participant-info'] span[data-test='button-text']"):
        value = node.get_text(" ", strip=True)
        if value:
            candidates.append(value)
    if candidates:
        return _unique_names(candidates)
    selectors = (
        "[class*='speaker']", "[class*='participant']", "[data-testid*='speaker']",
        "a[href*='speaker']", "a[href*='Speaker']",
    )
    for selector in selectors:
        for node in container.select(selector):
            value = node.get_text("\n", strip=True)
            if value and not _NON_PERSON.fullmatch(value):
                candidates.append(value)
    return _unique_names(candidates)


def _unique_names(candidates: list[str]) -> list[str]:
    result: list[str] = []
    for value in candidates:
        for name in _split_names(value):
            if name.casefold() not in {item.casefold() for item in result}:
                result.append(name)
    return result


def _split_names(value: str) -> list[str]:
    value = re.sub(r"\b(?:speaker|speakers|presenter|presenters|panelist|panelists)\s*:\s*", "", value, flags=re.I)
    parts = re.split(r"\s*(?:\n|;|\s+and\s+|\s*&\s*)\s*", value)
    result: list[str] = []
    for part in parts:
        name = clean_person_name(part).strip(" .,:;|-\u2013")
        if not name or _NON_PERSON.fullmatch(name) or len(name.split()) < 2:
            continue
        if len(name) > 90 or any(char.isdigit() for char in name):
            continue
        if name.casefold() not in {item.casefold() for item in result}:
            result.append(name)
    return result


def _description(container: Tag, title: str) -> str:
    text = _clean_text(container.get_text(" ", strip=True))
    return text if len(text) > len(title) else title


def _clean_text(value: str) -> str:
    return " ".join(str(value).split())


def _valid_title(value: str) -> bool:
    return bool(value and len(value.split()) >= 3 and not _NON_PERSON.fullmatch(value))


class RsaConferenceScraper:
    assessor_id = "rsa-conference"
    scraper_id = "rsa-conference-agenda"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/rsa-conference/rsa-conference.json"),
        html_directory: Path = Path("data/archives/html/rsa-conference"),
        output_directory: Path = Path("tmp/endorsements/rsa-conference"),
        profile_directory: Path = Path("tmp/profiles/rsa-conference"),
        overwrite: bool = True,
        timeout: float = 30,
        retries: int = 2,
        backoff: float = 0.5,
        delay: float = 0,
        user_agent: str = "verified-endorsement-scraper/0.1",
    ) -> None:
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        document = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        self.sources = document.get("links", {}).get("processUrls", [])
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(
            assessor_id=self.assessor_id, scraper_id=self.scraper_id,
            timeout=timeout, retries=retries, backoff=backoff, delay=delay,
            user_agent=user_agent,
        ).fetch

    def run(self) -> list[RsaResult]:
        results: list[RsaResult] = []
        for source in self.sources:
            year = rsa_year(source)
            member = urlsplit(source).path.strip("/") or "index.html"
            rendered_member = f"us{str(year)[2:]}-rendered.html"
            body = self.archive.read(rendered_member) or self.archive.read(member)
            if body is None:
                try:
                    body = self.fetch(Request(source)).body
                except FetchError as exc:
                    # Historical RSAC pages are intermittently retired or
                    # protected by the current site. Keep collecting later
                    # conference years when one source is unavailable.
                    print(f"Skipping unavailable RSA source {source}: {exc}")
                    continue
                self.archive.write(member, body)
            rows = parse_rsa(body, source, year)
            if not rows:
                continue
            records = [build_endorsement_record(
                name=row.name, label=row.title, description=row.description,
                endorsement_type="presentation", assessor=self.assessor,
                subtitle=row.subtitle, url=row.url, year=row.year,
                domains=detect_domains(row.title, row.description),
                evidence_links=self.catalog.links_for(
                    assessor_id=self.assessor.id, label=row.title, subtitle=row.subtitle),
            ) for row in rows]
            output = self.output_directory / f"rsa-conference-{year}.json"
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = sorted({row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}.values(), key=lambda item: item["name"].casefold())
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(RsaResult(source, year, len(records), output))
        return results
