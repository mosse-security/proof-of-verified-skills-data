"""Standalone parser for archive page https://conference.hitb.org/hitbsecconf2024bkk/conference/."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-001-hitbsecconf2024bkk-conference'
SOURCE_URL = 'https://conference.hitb.org/hitbsecconf2024bkk/conference/'
YEAR = 2024

"""HITB Security Conference archive scraper."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.archives import ArchiveStore
from scrapers.domains import detect_domains
from scrapers.enrichment import EnrichmentCatalog
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record


@dataclass(frozen=True, slots=True)
class HitbResult:
    source: str
    endorsements: int
    output: Path


class HitbScraper:
    assessor_id = "hitb"
    scraper_id = "hitb-presentations"

    def __init__(self, *, assessor_file=Path("data/assessors/hitb.json"),
                 html_directory=Path("data/archives/html/hitb.zip"),
                 output_directory=Path("tmp/endorsements/hitb"),
                 profile_directory=Path("tmp/profiles/hitb"), overwrite=True,
                 timeout=30, retries=2):
        self.assessor_file = Path(assessor_file)
        self.assessor = AssessorMetadata.from_file(self.assessor_file)
        self.sources = json.loads(self.assessor_file.read_text(encoding="utf-8"))["links"]["processUrls"]
        self.archive = ArchiveStore(Path(html_directory))
        self.output_directory = Path(output_directory)
        self.profile_directory = Path(profile_directory)
        self.overwrite = overwrite
        self.catalog = EnrichmentCatalog.from_directory(Path("data/enrichments"))
        self.fetch = HttpClient(assessor_id=self.assessor_id, scraper_id=self.scraper_id,
                                timeout=timeout, retries=retries).fetch

    def run(self) -> list[HitbResult]:
        results: list[HitbResult] = []
        seen: set[tuple[str, str, int]] = set()
        for source in self.sources:
            main_member = urlsplit(source).path.strip("/")
            body = self.archive.read(main_member)
            if body is None:
                body = self.fetch(Request(source)).body
                self.archive.write(main_member, body)
            detail_urls = _session_urls(body, source)
            rows: list[tuple[str, str, str, str]] = []
            for detail_url in detail_urls:
                member = urlsplit(detail_url).path.strip("/")
                detail = self.archive.read(member)
                if detail is None:
                    detail = self.fetch(Request(detail_url)).body
                    self.archive.write(member, detail)
                rows.extend(parse_hitb_session(detail, detail_url))
            unique = {(title.casefold(), name.casefold()): (title, name, description, url)
                      for title, name, description, url in rows}
            records = []
            names: dict[str, dict[str, object]] = {}
            year_match = re.search(r"20\d{2}", source)
            year = int(year_match.group()) if year_match else 0
            for title, name, description, url in unique.values():
                dedupe_key = (title.casefold(), name.casefold(), year)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                subtitle = f"HITB {year}" if year else "HITB"
                records.append(build_endorsement_record(
                    name=name, label=title, description=description or title,
                    endorsement_type="presentation", assessor=self.assessor,
                    subtitle=subtitle, url=url, year=year,
                    domains=detect_domains(title, description),
                    evidence_links=_merge_links(
                        self.catalog.links_for(assessor_id=self.assessor.id, label=title, subtitle=subtitle),
                        _hitb_video_links(self.catalog, title, year),
                    ),
                ))
                names[name] = {"name": name, "biography": "", "contact": []}
            member_parts = Path(main_member).parts
            output_stem = "-".join(member_parts[-2:]) if member_parts[-1] == "conference" else member_parts[-1]
            output = self.output_directory / f"{output_stem}.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            if self.overwrite or not output.exists():
                output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.profile_directory.mkdir(parents=True, exist_ok=True)
            (self.profile_directory / output.name).write_text(
                json.dumps(list(names.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            results.append(HitbResult(source, len(records), output))
        return results


def _session_urls(html: bytes | str, source_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = {urljoin(source_url, link["href"]) for link in soup.find_all("a", href=True)
            if "/session/" in link["href"]}
    return sorted(urls)


def parse_hitb_session(html: bytes | str, source_url: str) -> list[tuple[str, str, str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    title_meta = soup.find("meta", attrs={"property": "og:title"})
    if title_meta and title_meta.get("content"):
        title = " ".join(str(title_meta["content"]).split())
        title = re.split(r"\s+-\s+HITB(?:SecConf|20\d{2})", title, maxsplit=1, flags=re.I)[0].strip()
    if not title:
        title_node = soup.find("h1")
        title = " ".join(title_node.get_text(" ", strip=True).split()) if title_node else ""
    if not title:
        return []
    speakers: list[str] = []
    for link in soup.find_all("a", href=True):
        if "/speaker/" not in link["href"]:
            continue
        name = " ".join(link.get_text(" ", strip=True).split())
        if name and name not in speakers:
            speakers.append(name)
    speaker_heading = next(
        (heading for heading in soup.find_all("h2")
         if heading.get_text(" ", strip=True).casefold() == "speakers"),
        None,
    )
    paragraph_nodes = (speaker_heading.find_all_previous("p")
                       if speaker_heading else soup.find_all("p"))
    paragraphs = [" ".join(p.get_text(" ", strip=True).split())
                  for p in reversed(paragraph_nodes)]
    paragraphs = [text for text in paragraphs if len(text) > 40]
    description = " ".join(paragraphs)
    if not description:
        meta = soup.find("meta", attrs={"property": "og:description"})
        if meta and meta.get("content"):
            description = " ".join(str(meta["content"]).replace("[&hellip;]", "").split())
    if not description:
        description = title
    return [(title, speaker, description, source_url) for speaker in speakers]


def _hitb_video_links(catalog: EnrichmentCatalog, title: str, year: int) -> tuple[dict[str, str], ...]:
    """Match HITB videos whose titles include schedule prefixes or speaker suffixes."""
    target = _title_words(title)
    if not target:
        return ()
    matches: dict[str, dict[str, str]] = {}
    for record in catalog.records:
        if record.get("assessor-id") != "hitb":
            continue
        video_title = str(record.get("title", ""))
        if year and record.get("conference") and str(record["conference"]) != str(year):
            continue
        candidate = _title_words(video_title)
        overlap = target & candidate
        if len(overlap) < 2:
            continue
        coverage = len(overlap) / max(1, min(len(target), len(candidate)))
        if coverage < 0.55 and len(overlap) < 4:
            continue
        url = record.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            matches[url] = {"title": video_title.strip(), "url": url}
    return tuple(matches[key] for key in sorted(matches))


def _merge_links(*groups: tuple[dict[str, str], ...]) -> tuple[dict[str, str], ...]:
    merged = {link["url"]: link for group in groups for link in group if link.get("url")}
    return tuple(merged[key] for key in sorted(merged))


def _title_words(value: str) -> set[str]:
    value = re.sub(r"^\s*#?HITB[^:â€“â€”-]*(?:[:â€“â€”-])?\s*", "", value, flags=re.I)
    value = re.sub(r"\s+-\s+[^-]{2,80}$", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value.casefold())
    return {word for word in value.split() if len(word) >= 4 and word not in {"with", "from", "into", "that", "this", "your", "about"}}


def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_hitb_session(body, source_url)


