"""SANS Holiday Hack Challenge winners parser."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup

from ..archives import ArchiveStore
from ..http import HttpClient
from ..models import Request
from ..schema import AssessorMetadata, build_endorsement_record


SOURCE_URL = "https://www.sans.org/cyber-ranges/holiday-hack-challenge/winners-and-answers"


@dataclass(frozen=True, slots=True)
class SansHolidayHackResult:
    source: str
    endorsements: int
    output: Path


class SansHolidayHackScraper:
    assessor_id = "sans-holiday-hack"
    scraper_id = "sans-holiday-hack-winners"

    def __init__(
        self,
        *,
        assessor_file: Path = Path("data/assessors/sans-holiday-hack/sans-holiday-hack.json"),
        archive_file: Path = Path("data/archives/html/sans-holiday-hack.zip"),
        output_directory: Path = Path("tmp/endorsements/sans-holiday-hack"),
        profile_directory: Path = Path("tmp/profiles/sans-holiday-hack"),
        overwrite: bool = True,
        timeout: float = 30,
        retries: int = 2,
    ) -> None:
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.archive = ArchiveStore(Path(archive_file).resolve())
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.fetch = HttpClient(
            assessor_id=self.assessor_id,
            scraper_id=self.scraper_id,
            timeout=timeout,
            retries=retries,
        ).fetch

    def run(self) -> list[SansHolidayHackResult]:
        member = "winners-and-answers.html"
        body = self.archive.read(member)
        if body is None or self.overwrite:
            response = self.fetch(Request(SOURCE_URL))
            if response.status != 200:
                raise RuntimeError(f"SANS Holiday Hack page returned HTTP {response.status}")
            body = response.body
            self.archive.write(member, body)

        rows = _parse_page(body)
        records = [self._record(row) for row in rows]
        output = self.output_directory / "sans-holiday-hack-winners.json"
        profiles = [{"name": row["name"], "biography": "", "contact": []} for row in rows]
        if self.overwrite or not output.exists():
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        profile_output = self.profile_directory / "sans-holiday-hack-winners.json"
        if self.overwrite or not profile_output.exists():
            profile_output.parent.mkdir(parents=True, exist_ok=True)
            profile_output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return [SansHolidayHackResult(SOURCE_URL, len(records), output)]

    def _record(self, row: dict[str, object]) -> dict:
        year = int(row["year"])
        award = str(row["award"])
        name = str(row["name"])
        return build_endorsement_record(
            name=name,
            label="SANS Holiday Hack Challenge Winners",
            subtitle=f"{year} — {award}",
            description=f"Publicly recognized by SANS as a {award} recipient in the {year} Holiday Hack Challenge.",
            endorsement_type="competition_placement",
            assessor=self.assessor,
            url=SOURCE_URL,
            year=year,
            domains=("penetration-testing", "vulnerability-research"),
            evidence_links=({"url": SOURCE_URL, "title": "SANS Holiday Hack Challenge winners and answers"},),
        )


def _parse_page(body: bytes) -> list[dict[str, object]]:
    soup = BeautifulSoup(body, "html.parser")
    rows: list[dict[str, object]] = []
    seen: set[tuple[int, str, str]] = set()
    for accordion in soup.select(".accordion__item"):
        heading = accordion.find("h3")
        if heading is None:
            continue
        match = re.fullmatch(r"20\d{2}", heading.get_text(" ", strip=True))
        if not match:
            continue
        year = int(match.group(0))
        rich_text = accordion.select_one(".c-rich-text")
        if rich_text is None:
            continue
        award = "Honorable Mention"
        for element in rich_text.find_all(["p", "ul"], recursive=False):
            for text, names in _element_entries(element):
                if text:
                    award = text
                for name in names:
                    key = (year, award.casefold(), name.casefold())
                    if key not in seen:
                        seen.add(key)
                        rows.append({"name": name, "year": year, "award": award})
    return rows


def _element_entries(element) -> list[tuple[str, list[str]]]:
    """Return award/name entries while retaining the page's semantic blocks."""
    if element.name == "ul":
        result: list[tuple[str, list[str]]] = []
        for item in element.find_all("li", recursive=False):
            anchors = []
            for anchor in item.find_all("a"):
                anchor_text = anchor.get_text(" ", strip=True)
                if anchor_text and anchor_text.casefold() != "report":
                    anchors.append(anchor_text)
            if anchors:
                result.append(("", _split_names(" and ".join(anchors))))
                continue
            text = re.sub(r"\s+", " ", item.get_text(" ", strip=True))
            award, names_text = _award_and_names(text)
            result.append((award, _split_names(names_text)))
        return result

    text = re.sub(r"\s+", " ", element.get_text(" ", strip=True)).strip()
    if not text:
        return []
    bold = element.find("b")
    if bold is not None and ":" in text:
        award = text.split(":", 1)[0].strip()
        return [(award, _split_names(bold.get_text(" ", strip=True)))]
    if re.fullmatch(r"(?:Super )?Honorable Mentions:?", text, flags=re.IGNORECASE):
        return [(text.rstrip(":").strip(), [])]
    return [(_award_and_names(text)[0], _split_names(_award_and_names(text)[1]))]


def _award_and_names(text: str) -> tuple[str, str]:
    if ":" in text:
        award, names = text.split(":", 1)
        return award.strip(), names.split("|", 1)[0].strip()
    return "", text.split("|", 1)[0].strip()


def _split_names(value: str) -> list[str]:
    value = re.sub(r"\([^)]*\)", "", value)
    value = value.strip(" .:-")
    if not value:
        return []
    parts = re.split(r"\s+(?:and|&|/|,\s+and)\s+", value, flags=re.IGNORECASE)
    result: list[str] = []
    for part in parts:
        part = re.sub(r"\s+\|.*$", "", part).strip(" .:-")
        if part and part.casefold() not in {x.casefold() for x in result}:
            result.append(part)
    return result
