"""Standalone parser for archive page https://defcon.org/html/defcon-10/defcon-10-speakers.html."""
from __future__ import annotations

# This file owns exactly one archived page; do not broaden its URL scope.
PAGE_ID = 'page-025-html-defcon-10-defcon-10-speakers-html'
SOURCE_URL = 'https://defcon.org/html/defcon-10/defcon-10-speakers.html'
YEAR = 0


import copy
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from scrapers.archives import ArchiveStore
from scrapers.domains import detect_domains
from scrapers.enrichment import EnrichmentCatalog
from scrapers.http import HttpClient
from scrapers.models import Request
from scrapers.schema import AssessorMetadata, build_endorsement_record


DEFAULT_ASSESSOR_FILE = Path("data/assessors/def-con/def-con.json")
DEFAULT_HTML_DIRECTORY = Path("data/archives/html/def-con")
DEFAULT_OUTPUT_DIRECTORY = Path("tmp/endorsements/def-con")
DEFAULT_PROFILE_DIRECTORY = Path("tmp/profiles/def-con")


class DefConParseError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DefConEndorsement:
    name: str
    label: str
    description: str
    subtitle: str
    url: str
    year: int
    domains: tuple[str, ...]
    evidence_links: tuple[dict[str, str], ...] = ()
    biography: str = ""
    contact: tuple[dict[str, str], ...] = ()

    def profile_record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "biography": self.biography,
            "contact": [dict(item) for item in self.contact],
        }

    def to_record(self, assessor: AssessorMetadata) -> dict[str, object]:
        return build_endorsement_record(
            name=self.name,
            label=self.label,
            description=self.description,
            endorsement_type="presentation",
            assessor=assessor,
            subtitle=self.subtitle,
            url=self.url,
            year=self.year,
            domains=self.domains,
            evidence_links=self.evidence_links,
        )


@dataclass(frozen=True, slots=True)
class ConferenceResult:
    year: int
    endorsements: int
    cache: str
    output: Path
    status: str


class DefConScraper:
    """Local-first scraper for all DEF CON speaker archive layouts."""

    assessor_id = "def-con"
    scraper_id = "def-con-speakers"

    def __init__(
        self,
        *,
        assessor_file: Path = DEFAULT_ASSESSOR_FILE,
        html_directory: Path = DEFAULT_HTML_DIRECTORY,
        output_directory: Path = DEFAULT_OUTPUT_DIRECTORY,
        profile_directory: Path = DEFAULT_PROFILE_DIRECTORY,
        workers: int = 8,
        overwrite: bool = True,
        fetch: Callable[[Request], object] | None = None,
        timeout: float = 30,
        retries: int = 2,
        backoff: float = 0.5,
        delay: float = 0,
        user_agent: str = "verified-endorsement-scraper/0.1",
        enrichment_directory: Path = Path("data/enrichments"),
    ) -> None:
        self.assessor_file = assessor_file
        self.assessor = AssessorMetadata.from_file(assessor_file)
        if self.assessor.id != self.assessor_id:
            raise ValueError(
                f"Expected assessor id {self.assessor_id!r}, "
                f"found {self.assessor.id!r}"
            )
        self.html_directory = html_directory
        self.output_directory = output_directory
        self.profile_directory = profile_directory
        self.workers = max(1, workers)
        self.overwrite = overwrite
        if fetch is None:
            client = HttpClient(
                assessor_id=self.assessor_id,
                scraper_id=self.scraper_id,
                timeout=timeout,
                retries=retries,
                backoff=backoff,
                delay=delay,
                user_agent=user_agent,
            )
            fetch = client.fetch
        self.fetch = fetch
        self.enrichment_catalog = EnrichmentCatalog.from_directory(enrichment_directory)

    def conference_urls(self) -> list[tuple[int, str]]:
        document = json.loads(self.assessor_file.read_text(encoding="utf-8"))
        urls = document.get("links", {}).get("processUrls")
        if not isinstance(urls, list) or not urls:
            raise ValueError(
                f"{self.assessor_file} must contain a non-empty links.processUrls array"
            )
        conferences: list[tuple[int, str]] = []
        seen: set[int] = set()
        for value in urls:
            if not isinstance(value, str):
                raise ValueError("Every links.processUrls item must be a URL string")
            year = _conference_number(value)
            if year in seen:
                raise ValueError(f"Duplicate DEF CON conference number: {year}")
            seen.add(year)
            conferences.append((year, value))
        return conferences

    def run(self) -> list[ConferenceResult]:
        conferences = self.conference_urls()
        results: list[ConferenceResult] = []
        with ThreadPoolExecutor(
            max_workers=min(self.workers, len(conferences)),
            thread_name_prefix="def-con",
        ) as executor:
            futures = {
                executor.submit(self._process_conference, year, url): year
                for year, url in conferences
            }
            for future in as_completed(futures):
                results.append(future.result())
        return sorted(results, key=lambda result: result.year, reverse=True)

    def _process_conference(self, year: int, source_url: str) -> ConferenceResult:
        cache_member = f"defcon-{year}/speakers.html"
        archive = ArchiveStore(self.html_directory)
        body = archive.read(cache_member)
        if body is not None:
            cache_status = "local"
        else:
            response = self.fetch(Request(source_url, meta={"conference": year}))
            body = getattr(response, "body", None)
            if not isinstance(body, bytes):
                raise TypeError("The DEF CON fetch function must return a response with bytes body")
            archive.write(cache_member, body)
            cache_status = "fetched"

        endorsements = parse_def_con_page(year, body, source_url, self.enrichment_catalog)
        if not endorsements:
            raise DefConParseError(
                f"DEF CON {year} produced no endorsements from "
                f"{self.html_directory}!{cache_member}"
            )

        output = self.output_directory / f"defcon-{year}.json"
        output_preexisted = output.exists()
        if output_preexisted and not self.overwrite:
            status = "skipped"
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                [item.to_record(self.assessor) for item in endorsements],
                ensure_ascii=False,
                indent=2,
            ) + "\n"
            _atomic_write(output, payload.encode("utf-8"))
            status = "overwritten" if output_preexisted else "created"

        profile_map: dict[str, dict[str, object]] = {}
        for item in endorsements:
            key = _person_key(item.name)
            profile = item.profile_record()
            existing = profile_map.get(key)
            if existing is None:
                profile_map[key] = profile
            else:
                if len(str(profile["biography"])) > len(str(existing["biography"])):
                    existing["biography"] = profile["biography"]
                existing_contacts = existing["contact"]
                for contact in profile["contact"]:
                    if contact not in existing_contacts:
                        existing_contacts.append(contact)
        profiles = sorted(profile_map.values(), key=lambda item: str(item["name"]).casefold())
        profile_output = self.profile_directory / f"defcon-{year}.json"
        if not (profile_output.exists() and not self.overwrite):
            profile_output.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(
                profile_output,
                (json.dumps(profiles, ensure_ascii=False, indent=2) + "\n").encode(
                    "utf-8"
                ),
            )

        return ConferenceResult(year, len(endorsements), cache_status, output, status)


def parse_def_con_page(
    year: int, html: bytes | str, source_url: str,
    enrichment_catalog: EnrichmentCatalog | None = None,
) -> list[DefConEndorsement]:
    soup = BeautifulSoup(html, "html.parser")
    if year == 30:
        rows = _parse_schedule(soup, source_url)
    elif soup.select_one(".talk"):
        rows = _parse_modern(soup, source_url)
    elif 18 <= year <= 21:
        rows = _parse_byline(soup, source_url)
    elif year == 16:
        rows = _parse_16(soup, source_url)
    elif year == 15:
        rows = _parse_15(soup, source_url)
    elif year == 14:
        rows = _parse_14(soup, source_url)
    elif year == 13:
        rows = _parse_13(soup, source_url)
    elif year == 12:
        rows = _parse_12(soup, source_url)
    elif year == 11:
        rows = _parse_11(soup, source_url)
    elif year == 10:
        rows = _parse_10(soup, source_url)
    elif year == 9:
        rows = _parse_9(soup, source_url)
    elif year == 8:
        rows = _parse_8(soup, source_url)
    else:
        rows = _parse_early(soup, source_url)

    conference = f"DEF CON {year}"
    calendar_year = 1992 + year
    unique: dict[tuple[str, str, str], DefConEndorsement] = {}
    for row in rows:
        names, talk, link, evidence = row[:4]
        profiles = row[4] if len(row) > 4 else {}
        talk = _clean_talk(talk)
        if not talk:
            continue
        for name in names:
            name = _clean_person_name(name)
            if not name or _is_noise_name(name):
                continue
            item = DefConEndorsement(
                name=name,
                label=talk,
                description=_description(evidence, talk),
                subtitle=conference,
                url=link,
                year=calendar_year,
                domains=detect_domains(name, talk, evidence, conference),
                contact=tuple(profiles.get(_person_key(name), {}).get("contact", ())),
                evidence_links=(
                    enrichment_catalog.links_for(
                        assessor_id="def-con", label=talk, subtitle=conference
                    )
                    if enrichment_catalog
                    else ()
                ),
            )
            unique.setdefault((name.casefold(), talk.casefold(), link), item)
    return list(unique.values())


def _description(evidence: str, title: str) -> str:
    """Return source abstract text, with a deterministic fallback."""

    return _clean(evidence) or f"No abstract provided. Talk title: {title}"


def _parse_modern(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str, dict[str, dict[str, object]]]]:
    for block in soup.select(".talk"):
        title_node = next(
            (
                node
                for node in block.select(".talk-title, .talkTitle")
                if _nearest_talk(node) is block
            ),
            None,
        )
        if not title_node:
            continue
        speakers = [
            _text_without_roles(node)
            for node in block.select(".speaker")
            if _nearest_talk(node) is block
        ]
        speakers = [name for name in speakers if name]
        if not speakers:
            continue
        evidence = _modern_abstract_text(block)
        profiles = _align_profiles(speakers, _modern_profiles(block))
        yield (
            speakers,
            _clean(title_node.get_text(" ", strip=True)),
            _node_link(block, title_node, source_url),
            evidence,
            profiles,
        )


def _parse_byline(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for title_node in soup.select("h2.title"):
        byline = title_node.find_next_sibling("h4", class_="byLine")
        if not byline:
            continue
        clone = BeautifulSoup(str(byline), "html.parser")
        for role in clone.select(".speakerTitle"):
            role.decompose()
        speakers = _name_lines(clone.get_text("\n", strip=True))
        if speakers:
            anchor = title_node.find_previous("a", attrs={"name": True})
            fragment = anchor.get("name") if anchor and anchor.get("name") != "top" else None
            abstract = title_node.find_next_sibling("p", class_="abstract")
            yield speakers, _clean(title_node.get_text(" ", strip=True)), _fragment_link(
                source_url, fragment
            ), _evidence_text(
                abstract, ".speakerBio"
            ), _align_profiles(speakers, _profiles_after_heading(title_node))


def _parse_schedule(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for title_node in soup.select(".sched-title"):
        container = title_node.find_parent("li") or title_node.parent
        speaker_nodes = container.select(".sched-speaker")
        speakers: list[str] = []
        for node in speaker_nodes:
            values = _lines_before_metadata(node)
            speakers.extend(values)
        if speakers:
            yield (
                speakers,
                _clean(title_node.get_text(" ", strip=True)),
                _node_link(container, title_node, source_url),
                _evidence_text(container),
            )


def _parse_16(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for title_node in soup.select("h3.title"):
        speakers: list[str] = []
        node = title_node.find_next_sibling()
        while node and not (isinstance(node, Tag) and node.name == "h3"):
            if isinstance(node, Tag) and node.name == "p":
                break
            if isinstance(node, Tag) and node.name == "h5":
                following = node.find_next_sibling()
                while isinstance(following, Tag) and following.name == "br":
                    following = following.find_next_sibling()
                if isinstance(following, Tag) and following.name == "em":
                    speakers.append(_clean(node.get_text(" ", strip=True)))
            node = node.find_next_sibling()
        if speakers:
            anchor = title_node.find_previous("a", attrs={"name": True})
            abstract = title_node.find_next_sibling("p")
            yield speakers, _clean(title_node.get_text(" ", strip=True)), _fragment_link(
                source_url, anchor.get("name") if anchor else None
            ), _evidence_text(abstract, ".small")


def _parse_15(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for node in soup.select(".big"):
        title_node = node.find("strong")
        anchor = node.find("a", attrs={"name": True})
        if not title_node or not anchor:
            continue
        clone = BeautifulSoup(str(node), "html.parser")
        for removable in clone.select("strong, a[name]"):
            removable.decompose()
        names = _name_lines(clone.get_text("\n", strip=True))
        if names:
            abstract = node.find_next_sibling("p")
            yield names, _clean(title_node.get_text(" ", strip=True)), _fragment_link(
                source_url, anchor.get("name")
            ), _evidence_text(abstract)


def _parse_14(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for node in soup.select("p.textblack8"):
        title_node = node.select_one(".textindigobold10")
        anchor = node.select_one("a[name], a[id]")
        if not title_node or not anchor:
            continue
        clone = BeautifulSoup(str(node), "html.parser")
        for removable in clone.select(".textindigobold10, a[name], a[id]"):
            removable.decompose()
        remainder = _clean(clone.get_text(" ", strip=True))
        names = _names_from_credit(remainder)
        if names:
            yield names, _clean(title_node.get_text(" ", strip=True)), _fragment_link(
                source_url, anchor.get("name") or anchor.get("id")
            ), _evidence_text(node.parent)


def _parse_13(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for title_node in soup.select("p.textblackbold8"):
        table = title_node.find_parent("table")
        if not table:
            continue
        speakers = [
            _clean(node.get_text(" ", strip=True)).rstrip(",")
            for node in table.select(".textdarkblubold10")
        ]
        if not speakers:
            continue
        anchor = title_node.select_one("a[name], a[id]")
        yield speakers, _clean(title_node.get_text(" ", strip=True)), _fragment_link(
            source_url, (anchor.get("name") or anchor.get("id")) if anchor else None
        ), " ".join(
            _clean(node.get_text(" ", strip=True)) for node in table.select(".textblack8")
        )


def _parse_12(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        title_node = cells[1].select_one("p.textgreenbold10")
        speaker_node = cells[0].select_one(".textkhakibold10")
        if not title_node or not speaker_node:
            continue
        anchor = row.find_previous("a", attrs={"name": True})
        yield _name_lines(speaker_node.get_text("\n", strip=True)), _clean(
            title_node.get_text(" ", strip=True)
        ), _fragment_link(source_url, anchor.get("name") if anchor else None), _evidence_text(
            cells[1], ".textlightsilver10"
        )


def _parse_11(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        title_node = cells[1].select_one(".textblackbold8")
        speaker_nodes = cells[0].select(".textmaroonbold8")
        if not title_node or not speaker_nodes:
            continue
        speakers = [_clean(node.get_text(" ", strip=True)) for node in speaker_nodes]
        anchor = cells[0].select_one("a[name]")
        yield speakers, _clean(title_node.get_text(" ", strip=True)), _fragment_link(
            source_url, anchor.get("name") if anchor else None
        ), _evidence_text(cells[1].select_one("p.textblack8"))


def _parse_10(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        title_node = cells[1].find("strong")
        speaker_node = cells[0].find("b")
        if not title_node or not speaker_node:
            continue
        speaker = _first_line(speaker_node)
        anchor = cells[0].select_one("a[name]")
        yield [speaker], _clean(title_node.get_text(" ", strip=True)), _fragment_link(
            source_url, anchor.get("name") if anchor else None
        ), _evidence_text(cells[1].find("p"))


def _parse_9(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for row in soup.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        speaker_node, title_node = cells[0].find("b"), cells[1].find("b")
        anchor = cells[0].select_one("a[name]")
        if speaker_node and title_node and anchor:
            yield [_clean(speaker_node.get_text(" ", strip=True))], _clean(
                title_node.get_text(" ", strip=True)
            ), _fragment_link(source_url, anchor.get("name")), _evidence_text(cells[1])


def _parse_8(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    for anchor in soup.select("a[name]"):
        if anchor.get("name") in {"Logos for DC 00", "Events"}:
            break
        if anchor.parent.name != "td":
            continue
        cell = anchor.parent
        speaker_node = cell.find("b")
        if not speaker_node:
            continue
        title = ""
        identity = speaker_node
        while identity.parent is not cell:
            identity = identity.parent
        candidate = identity.find_next_sibling()
        while candidate:
            if isinstance(candidate, Tag) and candidate.name != "br":
                title = _clean(candidate.get_text(" ", strip=True))
                if title:
                    break
            candidate = candidate.find_next_sibling()
        if title:
            yield [_clean(speaker_node.get_text(" ", strip=True))], title, _fragment_link(
                source_url, anchor.get("name")
            ), _evidence_text(cell, '[color="#CCCCCC"]')


def _parse_early(
    soup: BeautifulSoup, source_url: str
) -> Iterable[tuple[list[str], str, str, str]]:
    seen: set[str] = set()
    for underlined in soup.find_all("u"):
        if not underlined.find_parent("b"):
            continue
        name = _clean(underlined.get_text(" ", strip=True)).rstrip(":")
        if name.casefold() in seen or _is_noise_name(name):
            continue
        seen.add(name.casefold())
        container = underlined.find_parent("b")
        title = _early_title(container, name)
        if title:
            anchor = underlined.find_previous("a", attrs={"name": True})
            yield [name], title, _fragment_link(
                source_url, anchor.get("name") if anchor else None
            ), title


def _early_title(container: Tag, name: str) -> str:
    parent = container.find_parent("p")
    if parent and parent.find("u") is not None:
        text = _clean(parent.get_text(" ", strip=True))
        start = text.casefold().find(name.casefold())
        candidate = text[start + len(name) :] if start >= 0 else text
    else:
        pieces: list[str] = []
        node = container.next_sibling
        while node is not None and len(" ".join(pieces)) < 500:
            if isinstance(node, Tag) and node.name in {"br", "p"}:
                break
            if isinstance(node, Tag) and node.find("u"):
                break
            text = node.get_text(" ", strip=True) if isinstance(node, Tag) else str(node)
            if text.strip():
                pieces.append(text)
            node = node.next_sibling
        candidate = _clean(" ".join(pieces))
    if not candidate.strip(" \u00a0-:,."):
        for text_node in container.find_all_next(string=True):
            if container in text_node.parents:
                continue
            value = _clean(str(text_node)).strip(" \u00a0-:,")
            if not value or value.casefold() == name.casefold():
                continue
            candidate = value
            break
    candidate = re.split(
        r"\b(?:Hear it|See It|Read it|No Audio|Their Homepage)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    candidate = candidate.strip(" \u00a0-:,.")
    if " - " in candidate:
        candidate = candidate.rsplit(" - ", 1)[-1]
    sentence = re.split(r"(?<=[.!?])\s+", candidate, maxsplit=1)[0]
    return sentence[:300].strip()


def _text_without_roles(node: Tag) -> str:
    clone = copy.copy(node)
    for role in clone.select(".speaker-title, .speakerTitle"):
        role.decompose()
    return _clean(clone.get_text(" ", strip=True))


def _evidence_text(node: Tag | None, remove: str | None = None) -> str:
    if node is None:
        return ""
    clone = copy.copy(node)
    if remove:
        for unwanted in clone.select(remove):
            unwanted.decompose()
    return _clean(clone.get_text(" ", strip=True))


def _modern_abstract_text(block: Tag) -> str:
    """Read an abstract whether ``.abstract`` is content or an empty marker."""

    abstract = block.select_one(".abstract")
    if abstract is None:
        return ""
    pieces: list[str] = []
    own_text = _evidence_text(abstract, ".speaker-bio, .speakerBio")
    if own_text:
        pieces.append(own_text)

    sibling = abstract.find_next_sibling()
    while sibling is not None:
        if isinstance(sibling, Tag):
            classes = set(sibling.get("class", ()))
            if classes.intersection({"speaker-bio", "speakerBio"}):
                break
            # Speaker biographies on modern pages start with a labelled node;
            # stop there so a speaker's unrelated career history is not used.
            if sibling.select_one(".speaker-bio, .speakerBio"):
                break
            text = _evidence_text(sibling)
            if text and text.casefold() not in {"back to top", "return to top"}:
                pieces.append(text)
        sibling = sibling.find_next_sibling()
    return _clean(" ".join(pieces))


def _modern_profiles(block: Tag) -> dict[str, dict[str, object]]:
    """Extract contact links from speaker blocks; biographies are deferred."""

    profiles: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    for node in block.find_all(["p", "span"]):
        is_bio_marker = "speaker-bio" in set(node.get("class", ())) or "speakerBio" in set(
            node.get("class", ())
        )
        strong = node.find("strong") if is_bio_marker else None
        if strong is not None:
            name = _clean(strong.get_text(" ", strip=True))
            if name:
                current = profiles.setdefault(
                    _person_key(name), {"biography": "", "contact": []}
                )
        if current is None:
            continue
        links = node.find_all("a", href=True) if is_bio_marker else []
        if links:
            contacts = current["contact"]
            assert isinstance(contacts, list)
            for anchor in links:
                href = urljoin("https://defcon.org", str(anchor["href"]))
                label = _contact_label(anchor.get_text(" ", strip=True), href)
                contact: dict[str, str]
                if href.lower().startswith("mailto:"):
                    contact = {"label": label, "email": href[7:]}
                else:
                    contact = {"label": label, "url": href}
                if contact not in contacts:
                    contacts.append(contact)
    return profiles


def _profiles_after_heading(title_node: Tag) -> dict[str, dict[str, object]]:
    fragment = BeautifulSoup("<div></div>", "html.parser").div
    if fragment is None:
        return {}
    node = title_node.find_next_sibling()
    while node is not None:
        if isinstance(node, Tag) and node.name == "h2":
            break
        fragment.append(copy.copy(node))
        node = node.find_next_sibling()
    return _modern_profiles(fragment)


def _align_profiles(
    speakers: list[str], profiles: dict[str, dict[str, object]]
) -> dict[str, dict[str, object]]:
    """Match abbreviated profile names (for example ``David``) to speakers."""

    aligned: dict[str, dict[str, object]] = {}
    for speaker in speakers:
        key = _person_key(speaker)
        if key in profiles:
            aligned[key] = profiles[key]
            continue
        candidates = [
            profile
            for profile_key, profile in profiles.items()
            if profile_key in key or key in profile_key
        ]
        if len(candidates) == 1:
            aligned[key] = candidates[0]
    return aligned


def _contact_label(text: str, href: str) -> str:
    lowered = text.casefold().strip()
    if "linkedin" in lowered or "linkedin" in href.casefold():
        return "linkedin"
    if "website" in lowered or lowered in {"homepage", "web"}:
        return "website"
    if "email" in lowered or href.casefold().startswith("mailto:"):
        return "email"
    for label in ("twitter", "facebook", "youtube", "mastodon", "bluesky"):
        if label in lowered or label in href.casefold():
            return label
    return lowered or "website"


def _person_key(name: str) -> str:
    return " ".join(name.casefold().split())


def _nearest_talk(node: Tag) -> Tag | None:
    return node.find_parent(class_=lambda value: value and "talk" in value.split())


def _lines_before_metadata(node: Tag) -> list[str]:
    clone = BeautifulSoup(str(node), "html.parser")
    for unwanted in clone.select(".speaker-title, .speakerTitle"):
        unwanted.decompose()
    text = clone.get_text("\n", strip=True)
    result = []
    for line in text.splitlines():
        line = _clean(line)
        if not line or re.search(r"\b(?:minutes?|hours?|track|room)\b", line, re.I):
            continue
        result.append(line)
    return result


def _first_line(node: Tag) -> str:
    return _clean(node.get_text("\n", strip=True).splitlines()[0])


def _name_lines(text: str) -> list[str]:
    return [
        _clean(line).strip(" -:,")
        for line in text.splitlines()
        if _clean(line).strip(" -:,")
    ]


def _names_from_credit(text: str) -> list[str]:
    if not text:
        return []
    first = re.split(r"\s{2,}|\b(?:Abstract|Bio):", text, maxsplit=1)[0]
    first = first.strip(" -:,.")
    # Legacy pages put job titles after a comma. Keep aliases containing commas
    # only when they are quoted; otherwise the first field is the speaker name.
    if "," in first and '"' not in first:
        first = first.split(",", 1)[0]
    return [first] if first else []


def _node_link(container: Tag, title_node: Tag, source_url: str) -> str:
    anchor = title_node.find("a", href=True)
    if anchor:
        return urljoin(source_url, anchor["href"])
    identifier = container.get("id")
    if not identifier:
        named = container.select_one("a[name], a[id]")
        identifier = (named.get("name") or named.get("id")) if named else None
    return _fragment_link(source_url, identifier)


def _fragment_link(source_url: str, fragment: str | None) -> str:
    if not fragment:
        return source_url
    parts = urlsplit(source_url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, fragment))


def _conference_number(url: str) -> int:
    if "defcon-safemode" in url.lower():
        return 28
    matches = re.findall(r"(?:defcon|dc)-?(\d+)", url.lower())
    if not matches:
        raise ValueError(f"Cannot determine DEF CON conference number from {url}")
    return int(matches[-1])


def _clean(value: str) -> str:
    value = value.replace("\u00a0", " ")
    if any(marker in value for marker in ("Ã¢\x80", "Ãƒ", "Ã‚")):
        try:
            value = value.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return re.sub(r"\s+", " ", value).strip()
_QUOTED_ALIAS_PATTERNS = (
    re.compile(r'"[^"]*"'),
    re.compile(r"'[^']*'"),
    re.compile(r"“[^”]*”"),
    re.compile(r"‘[^’]*’"),
)
_PAREN_ALIAS_PATTERN = re.compile(r"\s*\((?:aka\s+|a\.k\.a\.\s+)?[^()]*\)", re.IGNORECASE)
_AKA_ALIAS_PATTERN = re.compile(r"\s+(?:a\.k\.a\.?|aka)\b.*$", re.IGNORECASE)


def _clean_person_name(value: str) -> str:
    """Remove speaker aliases while preserving ordinary apostrophes."""

    cleaned = _clean(value)
    for pattern in _QUOTED_ALIAS_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = _PAREN_ALIAS_PATTERN.sub(" ", cleaned)
    cleaned = _AKA_ALIAS_PATTERN.sub(" ", cleaned)
    return _clean(cleaned).strip(" -:,")


def _clean_talk(value: str) -> str:
    value = _clean(value)
    value = re.split(
        r"\b(?:Hear it|See It|Read it|No Audio|Their Homepage)\b",
        value,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return value.strip(" -:,")


def _is_noise_name(name: str) -> bool:
    lowered = name.casefold()
    return (
        len(name) < 2
        or len(name) > 100
        or bool(re.match(r"^\d{1,2}:\d{2}\b", name))
        or any(
            phrase in lowered
            for phrase in (
                "no audio",
                "recorded it",
                "pictures",
                "homepage",
                "closes down",
                "capture the flag contest",
                "the fed giveaway",
                "computer warriors",
                "speakers saturday",
                "speakers sunday",
            )
        )
    )


def _atomic_write(path: Path, content: bytes) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(content)
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)




def parse_page(body: bytes | str, source_url: str = SOURCE_URL):
    return parse_def_con_page(10, body, source_url, None)


