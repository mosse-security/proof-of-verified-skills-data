"""Insomni'hack historical talks archive parser."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from ..archives import ArchiveStore
from ..enrichment import EnrichmentCatalog
from ..http import HttpClient
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

    def __init__(self, *, assessor_file=Path("data/assessors/insomnihack.json"), html_directory=Path("data/archives/html/insomnihack.zip"), output_directory=Path("data/tmp/endorsements/insomnihack"), profile_directory=Path("data/tmp/profiles/insomnihack"), overwrite=True, timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.archive = ArchiveStore(Path(html_directory).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8")).get("links", {}).get("processUrls", [])
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id, timeout=timeout, retries=retries).fetch

    def run(self) -> list[InsomnihackResult]:
        results = []
        for source in self.sources:
            member = _member(source)
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            year = _year(source)
            rows = parse_insomnihack(body, source, year)
            if not rows:
                continue
            output = self.output_directory / f"insomnihack-{year}.json"
            records = [row.to_record(self.assessor, self.catalog) for row in rows]
            if self.overwrite or not output.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            profiles = {row.name: {"name": row.name, "biography": "", "contact": []} for row in rows}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"insomnihack-{year}.json").write_text(json.dumps(list(profiles.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(InsomnihackResult(source, len(rows), output))
        return results


def parse_insomnihack(html: bytes | str, source_url: str, year: int) -> list[InsomnihackEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    # The older editions use heading pairs, while newer editions use agenda
    # tables.  Parsing every heading as a talk caused times and biography
    # sentences to become people, so only explicit speaker headings and
    # agenda cells are accepted here.
    rows = _parse_agenda_rows(soup, source_url, year)
    rows.extend(_parse_heading_pairs(soup, source_url, year))
    rows.extend(_parse_heading_sections(soup, source_url, year))
    unique = {(r.name.casefold(), r.title.casefold(), r.url): r for r in rows if _valid_name(r.name)}
    return list(unique.values())


def _section_text(heading: Tag) -> str:
    parts = []
    for node in heading.find_all_next():
        if node is not heading and node.name in {"h2", "h3"}:
            break
        if node.name in {"p", "li", "strong", "b"}:
            text = node.get_text(" ", strip=True)
            if text and text not in parts:
                parts.append(text)
    return "\n".join(parts)


def _extract_names(text: str) -> list[str]:
    match = re.search(r"(?:speakers?)\s*[:]\s*([^\n]+)", text, flags=re.I)
    if match:
        candidate = match.group(1)
    else:
        before_bio = re.split(r"\bspeaker\s+bio\b", text, maxsplit=1, flags=re.I)[0]
        lines = [line.strip() for line in before_bio.splitlines() if line.strip()]
        candidate = lines[0] if lines else ""
    candidate = re.sub(r"^(?:speaker\s*[:]?|speakers\s*[:]?)\s*", "", candidate, flags=re.I)
    candidate = re.sub(r"^by\s+", "", candidate, flags=re.I)
    # Affiliations and job descriptions are frequently placed in
    # parentheses after a name. They are not part of the person identity.
    candidate = re.sub(r"\([^)]*\)", "", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" .")
    return [part.strip(" .") for part in re.split(r"\s*&\s*|\s+and\s+|\s*,\s*", candidate) if _valid_name(part)]


def _extract_description(text: str) -> str:
    match = re.search(r"abstract\s*:?\s*(.*?)(?:\n(?:speaker\s+bio|speaker|organized by)\b|$)", text, flags=re.I | re.S)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _parse_agenda_rows(soup: BeautifulSoup, source_url: str, year: int) -> list[InsomnihackEndorsement]:
    rows: list[InsomnihackEndorsement] = []
    heading_names = _heading_speaker_names(soup)
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
        for cell in cells[1:]:
            if _non_talk_cell(cell):
                continue
            # Use the final "by" as the speaker delimiter; talk titles can
            # legitimately contain the word earlier (for example, "Baffled
            # By Bloated Complexity by Mathias Payer").
            match = re.search(r"(.+)\s+by\s+(.+)$", cell, flags=re.I)
            if match:
                title = re.sub(r"\s+", " ", match.group(1)).strip(" -")
                names = _extract_names(match.group(2))
                if not names:
                    trailing = _trailing_speaker(cell)
                    if trailing is None:
                        continue
                    title, names = trailing
            else:
                # Some 2015 tables put title and speaker in one cell without
                # the word "by". Match only names explicitly listed in a
                # speaker heading; never guess from arbitrary cell text.
                matches = [n for n in heading_names if _contains_name(cell, n)]
                if not matches:
                    trailing = _trailing_speaker(cell)
                    if trailing is None:
                        continue
                    title, names = trailing
                else:
                    first = min(cell.casefold().find(n.casefold()) for n in matches)
                    title = cell[:first].strip(" -:()")
                    names = matches
            if not _is_talk_title(title):
                continue
            for name in names:
                rows.append(InsomnihackEndorsement(name, title, title, source_url, year))
    return rows


def _parse_heading_pairs(soup: BeautifulSoup, source_url: str, year: int) -> list[InsomnihackEndorsement]:
    headings = [h for h in soup.find_all(["h2", "h3"]) if _clean_title(h.get_text(" ", strip=True)).casefold() not in {"past events"}]
    rows: list[InsomnihackEndorsement] = []
    for index, heading in enumerate(headings):
        value = _clean_title(heading.get_text(" ", strip=True))
        if not value or not _is_talk_title(value):
            continue
        speaker_match = re.match(r"speakers?\s*:\s*(.+)$", value, flags=re.I)
        if speaker_match:
            # 2015 has speaker headings, with the title available in the
            # agenda table. Agenda parsing handles those records.
            continue
        next_heading = headings[index + 1] if index + 1 < len(headings) else None
        next_value = _clean_title(next_heading.get_text(" ", strip=True)) if next_heading else ""
        if re.match(r"speakers?\s*:", next_value, flags=re.I):
            names = _extract_names(re.sub(r"^speakers?\s*:\s*", "", next_value, flags=re.I))
            for name in names:
                rows.append(InsomnihackEndorsement(name, value, value, source_url, year))
        elif year <= 2014 and _looks_like_person_heading(value) and next_heading:
            title = next_value
            if _is_talk_title(title):
                for name in _extract_names(value):
                    rows.append(InsomnihackEndorsement(name, title, title, source_url, year))
    return rows


def _parse_heading_sections(soup: BeautifulSoup, source_url: str, year: int) -> list[InsomnihackEndorsement]:
    rows: list[InsomnihackEndorsement] = []
    for heading in soup.find_all(["h2", "h3"]):
        title = _clean_title(heading.get_text(" ", strip=True))
        if not _is_talk_title(title):
            continue
        sibling = heading.find_next_sibling()
        if not sibling or sibling.name not in {"p", "div"}:
            continue
        text = sibling.get_text(" ", strip=True)
        names = _extract_names(text)
        if not names or any(len(name.split()) > 6 for name in names):
            continue
        explicit_speakers = re.match(r"^speakers?\s*:", text, flags=re.I)
        if not (explicit_speakers or _looks_like_person_heading(text)):
            continue
        description = _extract_description(_section_text(heading)) or title
        for name in names:
            rows.append(InsomnihackEndorsement(name, title, description, source_url, year))
    return rows


def _heading_speaker_names(soup: BeautifulSoup) -> list[str]:
    names: list[str] = []
    for heading in soup.find_all(["h2", "h3"]):
        value = _clean_title(heading.get_text(" ", strip=True))
        if re.match(r"speakers?\s*:", value, flags=re.I):
            names.extend(_extract_names(re.sub(r"^speakers?\s*:\s*", "", value, flags=re.I)))
    return list(dict.fromkeys(names))


def _contains_name(text: str, name: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", text, flags=re.I))


def _trailing_speaker(cell: str) -> tuple[str, list[str]] | None:
    """Split legacy agenda cells with a title followed by a person's name."""

    prefix = cell.split(",", 1)[0].strip()
    if ":" in prefix:
        words = prefix.split()
        if len(words) >= 4:
            name = " ".join(words[-2:])
            if _valid_name(name):
                return " ".join(words[:-2]).strip(" -:()"), [name]
    match = re.match(
        r"^(?P<title>.+?)\s+(?P<name>[A-Z][\wÀ-ÖØ-öø-ÿ'’-]+(?:\s+[A-Z][\wÀ-ÖØ-öø-ÿ'’-]+){1,3})(?:,\s*.+)?$",
        cell,
    )
    if not match:
        return None
    name = match.group("name").strip()
    if not _valid_name(name):
        return None
    return match.group("title").strip(" -:()"), [name]


def _non_talk_cell(value: str) -> bool:
    return bool(re.match(r"^(?:time|closed|coffee(?: break)?|lunch|\(continued\)|intro|keynote)$", value.strip(), flags=re.I)) or bool(re.search(r"capture\s+the\s+flag", value, flags=re.I))


def _looks_like_person_heading(value: str) -> bool:
    if not _valid_name(value):
        return False
    words = value.split()
    return (
        1 <= len(words) <= 4
        and all(word[:1].isupper() or any(ch.isdigit() for ch in word) for word in words)
        and not any(ch in value for ch in ".!?;:")
        and " by " not in value.casefold()
    )


def _is_talk_title(title: str) -> bool:
    lowered = title.casefold()
    if len(title) < 8 or len(title) > 220:
        return False
    return not any(term in lowered for term in ("past events", "edition ", "organized by", "speaker bio", "abstract", "workshops", "contests", "sponsors", "contact", "register", "venue", "program", "about the event", "technology partners", "partner events", "thursday", "friday", "saturday", "sunday"))


def _clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -")


def _valid_name(value: str) -> bool:
    lowered = value.casefold()
    if lowered.strip(" ()").startswith("by "):
        return False
    words = value.split()
    if not (value and 2 < len(value) < 80 and 2 <= len(words) <= 6):
        return False
    if any(ch in value for ch in ":;!?/"):
        return False
    if words[0][0].islower() or not any(any(ch.isupper() for ch in word) for word in words):
        return False
    return not (lowered.startswith(("in this ", "this ", "we ", "our ", "the talk")) or any(term in lowered for term in ("time", "track", "coffee", "lunch", "closed", "room", "read more", "past events", "venue", "organized by", "technology partners", " is ", " and is ", " the ", " who ", " was ", " has ", "http")))


def _year(source: str) -> int:
    match = re.search(r"edition-(20\d{2})", source)
    return int(match.group(1)) if match else 0


def _member(url: str) -> str:
    return urlsplit(url).path.strip("/") or "index.html"
