"""Pwn2Own results parser backed by the public ZDI blog archive."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..archives import ArchiveStore
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


_YEAR = re.compile(r"\b(20\d{2})\b")
_ARTICLE = re.compile(r"^/blog/20\d{2}/[^\s?#]+$")
_NAME = re.compile(
    r"\b[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+){1,3}\b"
)
_OUTCOME = re.compile(
    r"^(?:SUCCESS(?:\s*/\s*COLLISION)?|FAILURE|PARTIAL|COLLISION|BUG COLLISION|WITHDRAWN)\s*[-–:]\s*",
    re.IGNORECASE,
)
_STOPWORDS = {
    "The", "This", "That", "They", "Team", "Master", "Pwn", "Day",
    "First", "Second", "Third", "Final", "Full", "Win", "Attempt",
    "Round", "Entry", "Research", "Results", "Unfortunately", "Another",
    "Microsoft", "Google", "Apple", "Mozilla", "Windows", "Linux",
}
_ORG_WORDS = {
    "ai", "company", "corporation", "cycraft", "foundation", "group",
    "hacking", "institute", "labs", "laboratory", "limited", "network",
    "networks", "research", "security", "team", "technologies", "university",
    "vendor", " inc", "llc", "ltd",
}
_REJECT_NAMES = {
    "canon ball", "confused deputy", "exploit confirmed", "howdy buckaroos",
}
_REJECT_TERMS = {
    "access", "assistant", "attack", "autel", "buffer", "browser", "charger",
    "chargepoint", "code", "command", "confusion", "copier", "database",
    "desktop", "emporia", "home", "infotainment", "injection", "lab",
    "lexmark", "mode", "overflow", "philips", "phone", "pointer", "printer",
    "qnap", "server", "smart", "tesla", "ts", "usb", "validation",
}
_ACTION_BOUNDARY = re.compile(
    r"\s+(?:was|were|used|using|targeting|from|of|combined|leveraged|"
    r"successfully|could|earned|earn|gets|got|demonstrated|executed|"
    r"exploited|achieved|has|will|with|including|on|into|succeed|succeeded|"
    r"is unable|were able|was able|to exploit)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class Pwn2OwnResult:
    source: str
    endorsements: int
    output: Path


class Pwn2OwnScraper:
    assessor_id = "pwn2own"
    scraper_id = "pwn2own-results"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/pwn2own/pwn2own.json"),
        html_directory: Path = Path("data/archives/html/pwn2own.zip"),
        output_directory: Path = Path("tmp/endorsements/pwn2own"),
        profile_directory: Path = Path("tmp/profiles/pwn2own"),
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
        links = json.loads(self.assessor_file.read_text(encoding="utf-8")).get("links", {})
        self.sources = links.get("processUrls", ["https://www.zerodayinitiative.com/blog?tag=Pwn2Own"])
        self.fetch = HttpClient(
            assessor_id=self.assessor_id,
            scraper_id=self.scraper_id,
            timeout=timeout,
            retries=retries,
        ).fetch

    def run(self) -> list[Pwn2OwnResult]:
        pages = self._discover_articles()
        results: list[Pwn2OwnResult] = []
        for source in pages:
            body = self._read_or_fetch(source)
            if body is None:
                continue
            year_match = _YEAR.search(source)
            year = int(year_match.group(1)) if year_match else 0
            rows = _parse_article(body, source, year)
            if not rows:
                continue
            output = self.output_directory / f"pwn2own-{year}-{_slug(source)}.json"
            records = [row.to_record(self.assessor, self.catalog) for row in rows]
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = {row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"pwn2own-{year}-{_slug(source)}.json").write_text(
                json.dumps(list(profiles.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            results.append(Pwn2OwnResult(source, len(rows), output))
        expected_outputs = {result.output for result in results}
        for stale in self.output_directory.glob("*.json"):
            if stale not in expected_outputs:
                stale.unlink(missing_ok=True)
        return results

    def _discover_articles(self) -> list[str]:
        discovered: set[str] = set()
        indexes = list(self.sources)
        seen_indexes: set[str] = set()
        while indexes and len(seen_indexes) < 100:
            source = indexes.pop(0)
            if source in seen_indexes:
                continue
            seen_indexes.add(source)
            body = self._read_or_fetch(source)
            if not body:
                continue
            soup = BeautifulSoup(body, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = str(anchor["href"]).strip()
                parsed = urlsplit(href)
                if parsed.path == "/blog" and "tag=Pwn2Own" in parsed.query:
                    next_index = "https://www.zerodayinitiative.com" + href
                    if next_index not in seen_indexes:
                        indexes.append(next_index)
                    continue
                if not _ARTICLE.fullmatch(parsed.path):
                    continue
                if parsed.netloc and parsed.netloc != "www.zerodayinitiative.com":
                    continue
                discovered.add("https://www.zerodayinitiative.com" + parsed.path)
        return sorted(discovered)

    def _read_or_fetch(self, url: str) -> bytes | None:
        member = _member(url)
        body = self.archive.read(member)
        if body is not None:
            return body
        try:
            body = self.fetch(Request(url)).body
        except Exception:
            return None
        self.archive.write(member, body)
        return body


@dataclass(frozen=True, slots=True)
class Pwn2OwnEndorsement:
    name: str
    label: str
    description: str
    url: str
    year: int

    def to_record(self, assessor: AssessorMetadata, catalog: EnrichmentCatalog) -> dict[str, object]:
        subtitle = f"Pwn2Own {self.year}" if self.year else "Pwn2Own"
        links = catalog.links_for(assessor_id=assessor.id, label=self.label, subtitle=subtitle)
        return build_endorsement_record(
            name=self.name,
            label=self.label,
            description=self.description,
            endorsement_type="competition_result",
            assessor=assessor,
            subtitle=subtitle,
            url=self.url,
            year=self.year,
            domains=(),
            evidence_links=links,
        )


def _parse_article(body: bytes, source: str, year: int) -> list[Pwn2OwnEndorsement]:
    soup = BeautifulSoup(body.decode("utf-8", errors="replace"), "html.parser")
    headings = [heading.get_text(" ", strip=True) for heading in soup.find_all("h1")]
    label = next((heading for heading in headings if heading.casefold() != "blog"), None) or "Pwn2Own results"
    main = soup.find("main") or soup
    rows: dict[tuple[str, str], Pwn2OwnEndorsement] = {}
    for paragraph in main.find_all(["p", "li"]):
        text = paragraph.get_text(" ", strip=True)
        if not _OUTCOME.match(text):
            continue
        clean = _OUTCOME.sub("", text).strip()
        for name in _researcher_names(clean):
            rows.setdefault(
                (name.casefold(), label.casefold()),
                Pwn2OwnEndorsement(name, label, clean, source, year),
            )
    return list(rows.values())


def _researcher_names(text: str) -> list[str]:
    # Keep only the part that identifies the credited researcher(s). The rest
    # of a result sentence is dominated by products, techniques, vendors, and
    # exploit descriptions, all of which contain title-cased phrases.
    marker = re.search(r"\b(?:goes to|team of|known as)\b", text, re.IGNORECASE)
    if marker:
        text = text[marker.end():]
    else:
        special = re.search(r"\b(?:winner|win|researcher|debut)\b.*?\bis\s+", text, re.IGNORECASE)
        if special:
            text = text[special.end():]
    boundary = _ACTION_BOUNDARY.search(text)
    if boundary:
        text = text[:boundary.start()]
    candidates: list[str] = []
    for match in _NAME.finditer(text):
        value = re.sub(r"\s+", " ", match.group(0)).strip(" .,:;()")
        words = {part.casefold().strip(".,()") for part in value.split()}
        if (
            value
            and not any(part in _STOPWORDS for part in value.split())
            and not words.intersection(_ORG_WORDS)
            and not words.intersection(_REJECT_TERMS)
            and value.casefold() not in _REJECT_NAMES
        ):
            candidates.append(value)
    return candidates


def _member(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path.strip("/") or "index.html"
    query = parsed.query.replace("=", "-").replace("&", "_")
    return f"{path}{'_' + query if query else ''}.html"


def _slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", url.casefold()).strip("-")[-100:]
