"""Standalone parser for archive page https://blackhat.com/archive/europe/2019/briefings/schedule/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-037-archive-europe-2019-briefings-schedule'
SOURCE_URL = 'https://blackhat.com/archive/europe/2019/briefings/schedule/'
YEAR = 2019


import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from scrapers.archives import ArchiveStore
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record
from scrapers.enrichment import EnrichmentCatalog
from scrapers.identity_registry import IdentityRegistry, clean_person_name


@dataclass(frozen=True, slots=True)
class BlackHatResult:
    year: int
    region: str
    endorsements: int
    cache: str
    output: Path


class BlackHatScraper:
    assessor_id = "black-hat"
    scraper_id = "black-hat-briefings"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/black-hat/black-hat.json"),
        html_directory: Path = Path("data/archives/html/black-hat.zip"),
        output_directory: Path = Path("tmp/endorsements/black-hat"),
        profile_directory: Path = Path("tmp/profiles/black-hat"),
        contact_information_directory: Path = Path("data/contact-information"),
        fetch: Callable[[Request], object] | None = None,
        overwrite: bool = True,
        timeout: float = 30,
        retries: int = 2,
        backoff: float = 0.5,
        delay: float = 0,
        user_agent: str = "verified-endorsement-scraper/0.1",
    ) -> None:
        self.assessor_file = assessor_file
        self.assessor = AssessorMetadata.from_file(assessor_file)
        self.enrichment_catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.html_directory = html_directory
        self.output_directory = output_directory
        self.profile_directory = profile_directory
        self.contact_information_directory = contact_information_directory
        self.overwrite = overwrite
        if fetch is None:
            fetch = HttpClient(
                assessor_id=self.assessor_id,
                scraper_id=self.scraper_id,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
                delay=delay,
                user_agent=user_agent,
            ).fetch
        self.fetch = fetch

    def conference_urls(self) -> list[tuple[int, str, str]]:
        document = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        urls = document.get("links", {}).get("processUrls", [])
        result = []
        for url in urls:
            try:
                year, region = _event_identity(url)
            except ValueError:
                # The MEA landing page is an index, not a conference program.
                # Its event-specific pages are still processed below.
                if "blackhatmea.com" in url and url.rstrip("/").endswith("blackhatmea.com"):
                    continue
                if "blackhatmea.com" in url:
                    year, region = 2025, "middle-east"
                else:
                    raise
            result.append((year, region, url))
        return result

    def run(self) -> list[BlackHatResult]:
        results = []
        for year, region, url in self.conference_urls():
            member = _archive_member(url)
            archive = ArchiveStore(self.html_directory)
            body = archive.read(member)
            cache = "local"
            if body is None:
                response = self.fetch(Request(url, meta={"year": year, "region": region}))
                body = getattr(response, "body", None)
                if not isinstance(body, bytes):
                    raise TypeError("Black Hat fetch function must return bytes body")
                archive.write(member, body)
                cache = "fetched"
            rows = parse_black_hat_page(body, url, year, region)
            if not rows:
                # Some current landing/schedule pages legitimately contain no
                # published sessions yet; leave them cached for a later run.
                continue
            records = [row.to_record(self.assessor, self.enrichment_catalog) for row in rows]
            output = self.output_directory / f"blackhat-{region}-{year}.json"
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self._write_profiles(rows, year, region)
            merge_black_hat_images(rows, self.contact_information_directory, year, region)
            results.append(BlackHatResult(year, region, len(records), cache, output))
        return results

    def _write_profiles(self, rows: list["BlackHatEndorsement"], year: int, region: str) -> None:
        profiles = sorted({row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}.values(), key=lambda x: x["name"].casefold())
        output = self.profile_directory / f"blackhat-{region}-{year}.json"
        if self.overwrite or not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

@dataclass(frozen=True, slots=True)
class BlackHatEndorsement:
    name: str
    title: str
    description: str
    url: str
    year: int
    subtitle: str
    evidence_links: tuple[dict[str, str], ...] = ()
    image_url: str | None = None
    image_source_url: str | None = None

    def to_record(self, assessor: AssessorMetadata, enrichment_catalog: EnrichmentCatalog | None = None) -> dict[str, object]:
        return build_endorsement_record(
            name=self.name,
            label=self.title,
            description=self.description or self.title,
            endorsement_type="presentation",
            assessor=assessor,
            subtitle=self.subtitle,
            url=self.url,
            year=self.year,
            domains=(),
            evidence_links=self.evidence_links or (enrichment_catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=self.subtitle) if enrichment_catalog else ()),
        )


def merge_black_hat_images(
    rows: list[BlackHatEndorsement],
    contact_information_directory: Path,
    year: int,
    region: str,
    *,
    verified_at: str | None = None,
) -> int:
    """Merge Black Hat images into existing contact-information records.

    This never creates a new profile file and never replaces an existing image.
    Ambiguous or unmatched names are skipped instead of being guessed.
    """

    contact_information_directory = Path(contact_information_directory)
    by_identity: dict[str, Path] = {}
    ambiguous: set[str] = set()
    for path in contact_information_directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = document.get("name")
        if not isinstance(name, str):
            continue
        identity = IdentityRegistry.normalize(name)
        if identity in by_identity:
            ambiguous.add(identity)
        else:
            by_identity[identity] = path

    timestamp = verified_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    changed = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if not row.image_url or not row.image_source_url:
            continue
        identity = IdentityRegistry.normalize(row.name)
        path = by_identity.get(identity)
        if not path or identity in ambiguous or (identity, row.image_url) in seen:
            continue
        seen.add((identity, row.image_url))
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("image"):
            continue
        document["image"] = {
            "url": row.image_url,
            "source_url": row.image_source_url,
            "source_type": "conference",
            "conference": "Black Hat",
            "year": year,
            "region": region,
            "verified": True,
            "verified_at": timestamp,
        }
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed += 1
    return changed


def parse_black_hat_page(html: bytes | str, source_url: str, year: int, region: str) -> list[BlackHatEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    rows = _parse_modern(soup, source_url, year, region)
    if not rows:
        rows = _parse_legacy(soup, source_url, year, region)
    unique = {(row.name.casefold(), row.title.casefold(), row.url): row for row in rows}
    return list(unique.values())


def _parse_modern(soup: BeautifulSoup, source_url: str, year: int, region: str) -> list[BlackHatEndorsement]:
    rows = []
    for container in soup.select(".data-container"):
        title = container.select_one(".session-title a, .session-title")
        speakers = container.select(".session-speakers a.speaker_link")
        if not title or not speakers:
            continue
        description = container.select_one(".search_description")
        talk = title.get_text(" ", strip=True)
        desc = description.get_text(" ", strip=True) if description else talk
        link = urljoin(source_url, title.get("href", ""))
        for speaker in speakers:
            for name in _speaker_names(speaker.get_text(" ", strip=True)):
                rows.append(BlackHatEndorsement(
                    name,
                    talk,
                    desc,
                    link,
                    year,
                    f"Black Hat {region.title()} {year}",
                    image_url=_black_hat_speaker_image(speaker, source_url),
                    image_source_url=source_url,
                ))
    return rows


def _parse_legacy(soup: BeautifulSoup, source_url: str, year: int, region: str) -> list[BlackHatEndorsement]:
    rows = []
    for block in soup.select("div.span-14"):
        heading = block.select_one("h2.briefing-title")
        if not heading:
            continue
        title = heading.get_text(" ", strip=True)
        description = next((p.get_text(" ", strip=True) for p in block.select("p") if p.get_text(" ", strip=True)), title)
        link = urljoin(source_url, f"#{heading.get('id', '')}")
        presenter = block.find_next_sibling("div", class_=lambda value: value and "presented-by" in value)
        names = presenter.select("a") if presenter else []
        if not names and presenter:
            text = presenter.get_text(" ", strip=True)
            text = re.sub(r"^presented\s+by\s*:?\s*", "", text, flags=re.I)
            names = [text] if text else []
        for speaker in names:
            value = speaker.get_text(" ", strip=True) if isinstance(speaker, Tag) else str(speaker)
            for name in _speaker_names(value):
                rows.append(BlackHatEndorsement(
                    name,
                    title,
                    description,
                    link,
                    year,
                    f"Black Hat {region.title()} {year}",
                    image_url=_black_hat_speaker_image(speaker, source_url) if isinstance(speaker, Tag) else None,
                    image_source_url=source_url if isinstance(speaker, Tag) else None,
                ))
    for block in soup.select("div.span-13, div.span-14"):
        heading = block.select_one("h2 a, h2")
        if not heading:
            continue
        title = heading.get_text(" ", strip=True)
        if title.casefold() in {"briefings", "media legend", "white paper", "presentation", "source", "audio", "video"}:
            continue
        description = next((p.get_text(" ", strip=True) for p in block.select("p") if p.get_text(" ", strip=True)), title)
        link = urljoin(source_url, heading.get("href", ""))
        sibling = block.find_next_sibling("div", class_=lambda value: value and "span-5" in value)
        speakers = sibling.select("a") if sibling else []
        for speaker in speakers:
            for name in _speaker_names(speaker.get_text(" ", strip=True)):
                rows.append(BlackHatEndorsement(
                    name,
                    title,
                    description,
                    link,
                    year,
                    f"Black Hat {region.title()} {year}",
                    image_url=_black_hat_speaker_image(speaker, source_url),
                    image_source_url=source_url,
                ))
    return rows


def _speaker_names(value: str) -> list[str]:
    """Split comma-joined speaker fields and remove honorific prefixes."""

    return [
        cleaned
        for part in re.split(r"\s*,\s*", value)
        if (cleaned := clean_person_name(part))
    ]


def _black_hat_speaker_image(speaker: Tag, source_url: str) -> str | None:
    """Return an image only when it is nested in Black Hat's speaker node."""

    image = speaker.find("img", recursive=True)
    if image is None:
        return None
    value = next((image.get(attribute) for attribute in ("src", "data-src", "data-lazy-src") if image.get(attribute)), None)
    if not isinstance(value, str) or not value.strip():
        return None
    alt = image.get("alt")
    speaker_name = clean_person_name(speaker.get_text(" ", strip=True))
    if isinstance(alt, str) and alt.strip() and clean_person_name(alt) != speaker_name:
        return None
    return urljoin(source_url, value.strip())


def _event_identity(url: str) -> tuple[int, str]:
    path = urlsplit(url).path.casefold()
    match = re.search(r"(?:19|20)\d{2}", path)
    if match:
        value = int(match.group(0))
    else:
        short = re.search(r"(?:usa|us|europe|eu|ad|archives?)[/-]?(\d{2})(?:[^\d]|$)", path)
        if not short:
            short = re.search(r"-(\d{2})(?:[^\d]|$)", path)
        if not short:
            raise ValueError(f"Cannot determine Black Hat year from {url}")
        value = 2000 + int(short.group(1))
    year = value
    region = "europe" if "europe" in path or "/eu" in path else "middle-east" if "/ad-" in path or "bh-ad" in path else "usa"
    return year, region


def _archive_member(url: str) -> str:
    return urlsplit(url).path.strip("/") or "index.html"




def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_black_hat_page(body, source_url, 2019, 'usa')
