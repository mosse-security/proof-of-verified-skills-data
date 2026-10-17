"""Standalone parser for archive page https://blueteamcon.com/btc-history/talks-blue-team-con-2022/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-002-btc-history-talks-blue-team-con-2022'
SOURCE_URL = 'https://blueteamcon.com/btc-history/talks-blue-team-con-2022/'
YEAR = 2022

"""Blue Team Con historical talk-page scraper."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from scrapers.archives import ArchiveStore
from scrapers.enrichment import EnrichmentCatalog
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class BlueTeamConTalk:
    name: str
    title: str
    description: str
    url: str
    year: int

    def to_record(self, assessor: AssessorMetadata, catalog: EnrichmentCatalog):
        subtitle = f"Blue Team Con {self.year}"
        return build_endorsement_record(
            name=self.name, label=self.title, description=self.description or self.title,
            endorsement_type="presentation", assessor=assessor, subtitle=subtitle,
            url=self.url, year=self.year,
            domains=(),
            evidence_links=catalog.links_for(assessor_id=assessor.id, label=self.title, subtitle=subtitle),
        )


@dataclass(frozen=True, slots=True)
class BlueTeamConResult:
    source: str
    endorsements: int
    output: Path


class BlueTeamConScraper:
    assessor_id = "blue-team-con"
    scraper_id = "blue-team-con-talks"

    def __init__(self, *, assessor_file=Path("data/assessors/blue-team-con.json"),
                 html_directory=Path("data/archives/html/blue-team-con.zip"),
                 output_directory=Path("tmp/endorsements/blue-team-con"),
                 profile_directory=Path("tmp/profiles/blue-team-con"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        document = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        self.sources = document.get("links", {}).get("processUrls", [])
        self.archive = ArchiveStore(Path(html_directory))
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[BlueTeamConResult]:
        results = []
        for source in self.sources:
            member = _member_for_source(source)
            body = self.archive.read(member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(member, body)
            talks = parse_blue_team_con(body, source)
            if not talks:
                continue
            output = self.output_directory / f"{Path(member).stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            records = [talk.to_record(self.assessor, self.catalog) for talk in talks]
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            names = {talk.name: {"name": talk.name, "biography": "", "contact": []} for talk in talks}
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / f"{Path(member).stem}.json").write_text(json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            results.append(BlueTeamConResult(source, len(records), output))
        return results


def parse_blue_team_con(html: bytes | str, source_url: str) -> list[BlueTeamConTalk]:
    soup = BeautifulSoup(html, "html.parser")
    year_match = re.search(r"20\d{2}", source_url)
    year = int(year_match.group()) if year_match else 0
    rows: list[BlueTeamConTalk] = []
    for heading in soup.find_all("h2"):
        title_link = heading.find("a", href=True)
        title = " ".join(heading.get_text(" ", strip=True).split())
        if not title or not title_link:
            continue
        wrapper = heading
        for _ in range(5):
            wrapper = wrapper.parent if wrapper.parent else wrapper
            if isinstance(wrapper, Tag) and wrapper.find(string=re.compile(r"Presented by", re.I)):
                break
        presented = wrapper.find(string=re.compile(r"Presented by", re.I)) if isinstance(wrapper, Tag) else None
        if not presented:
            continue
        text = " ".join(str(presented).split())
        names = _names(re.sub(r"^Presented by\s*", "", text, flags=re.I))
        # The talks index has no abstract body; preserve its stable detail URL
        # and a useful non-empty description until the detail page is archived.
        for name in names:
            rows.append(BlueTeamConTalk(name, title, title, urljoin(source_url, title_link["href"]), year))
    unique = {(r.name.casefold(), r.title.casefold(), r.url): r for r in rows}
    return list(unique.values())


def _member_for_source(source: str) -> str:
    path = urlsplit(source).path.strip("/")
    return path or "index.html"


def _names(value: str) -> list[str]:
    value = re.sub(r"\([^)]*\)", "", value)
    parts = re.split(r";|\s+&\s+|\s+and\s+", value)
    return [p.strip(" ,â€“-") for p in parts if len(p.strip()) >= 3 and len(p.split()) >= 2]


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_blue_team_con(body, source_url)


