"""Allowlist-gated portrait extraction for archived HITB conference pages."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.identity_registry import IdentityRegistry

ALLOWLIST_PATH = Path("data/individuals-enumeration.txt")


def parse_portraits(html: bytes | str, source_url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    known = _allowlisted_names()
    aliases = {_compact(display): identity for identity, display in known.items()}
    name_pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(display) for display in sorted(known.values(), key=len, reverse=True)) + r")(?!\w)",
        re.IGNORECASE,
    )
    portraits: dict[str, str] = {}
    next_headings = ["", "", "", ""]
    for item in reversed(soup.find_all(["img", "h1", "h2", "h3", "h4"])):
        if item.name.startswith("h"):
            next_headings[int(item.name[1:]) - 1] = item.get_text(" ", strip=True)
            continue
        image_url = item.get("data-src") or item.get("data-lazy-src") or item.get("src")
        if not isinstance(image_url, str) or "/wp-content/uploads/" not in image_url:
            continue
        image_classes = " ".join(item.get("class") or []).casefold()
        if "logo" in image_classes or "sponsor" in image_classes or "icon" in image_classes:
            continue
        labels = [
            item.get("alt", ""),
            item.get("title", ""),
            Path(urlsplit(unquote(image_url)).path).stem,
            *next_headings,
        ]
        for label in labels:
            identity = _candidate_identity(label, aliases, name_pattern)
            if identity is not None:
                portraits.setdefault(known[identity], urljoin(source_url, image_url))
                break
    return portraits


def update_contact_information(
    portraits: dict[str, str], *, source_url: str, year: int,
    contact_directory: Path = Path("data/contact-information"),
) -> list[str]:
    contact_directory.mkdir(parents=True, exist_ok=True)
    contact_paths: dict[str, Path] = {}
    for path in contact_directory.glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = document.get("name")
        if isinstance(name, str):
            contact_paths[IdentityRegistry.normalize(name)] = path

    allowed = _allowlisted_names()
    changed: list[str] = []
    for name, image_url in portraits.items():
        identity = IdentityRegistry.normalize(name)
        path = contact_paths.get(identity) or contact_directory / f"{_slug(name)}.json"
        if path.exists():
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
        else:
            document = {"name": allowed[identity], "contact": [], "biography": ""}
        if document.get("image"):
            continue
        document["image"] = {
            "url": image_url,
            "source_url": source_url,
            "source_type": "conference",
            "conference": "HITB",
            "year": year,
            "verified": True,
        }
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed.append(name)
    return changed


def _allowlisted_names() -> dict[str, str]:
    return {
        IdentityRegistry.normalize(line.strip()): line.strip()
        for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def _candidate_identity(value: str, aliases: dict[str, str], name_pattern: re.Pattern[str]) -> str | None:
    cleaned = " ".join(str(value).split())
    if not cleaned:
        return None
    compact = _compact(cleaned)
    if compact in aliases:
        return aliases[compact]
    match = name_pattern.search(cleaned)
    if match:
        return aliases.get(_compact(match.group(0)))
    normalized = IdentityRegistry.normalize(cleaned)
    return aliases.get(_compact(normalized))


def _compact(value: str) -> str:
    value = re.sub(r"\b(?:dr|doctor|head\s*shot|speaker|portrait|photo|scaled|square|profile|image|img)\.?\b", " ", str(value), flags=re.I)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _slug(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "individual"
