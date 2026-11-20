"""Allowlist-gated portrait extraction for archived GrrCON presentation pages."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup

from scrapers.identity_registry import IdentityRegistry

ALLOWLIST_PATH = Path("data/individuals-enumeration.txt")


def parse_portraits(html: bytes | str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    known = _allowlisted_names()
    aliases = {_compact(display): identity for identity, display in known.items()}
    name_pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(display) for display in sorted(known.values(), key=len, reverse=True)) + r")(?!\w)",
        re.IGNORECASE,
    )
    portraits: dict[str, str] = {}
    next_h2 = ""
    next_h3 = ""
    for item in reversed(soup.find_all(["img", "h2", "h3"])):
        if item.name == "h2":
            next_h2 = item.get_text(" ", strip=True)
            continue
        if item.name == "h3":
            next_h3 = item.get_text(" ", strip=True)
            continue
        image = item
        image_url = (
            image.get("data-src")
            or image.get("data-tf-src")
            or image.get("data-orig-src")
            or image.get("src")
        )
        if not isinstance(image_url, str) or "grrcon.com/wp-content/uploads/" not in image_url:
            continue
        labels = [
            image.get("alt", ""),
            image.get("title", ""),
            Path(urlsplit(unquote(image_url)).path).stem,
            next_h2,
            next_h3,
        ]
        for label in labels:
            identity = _candidate_identity(label, known, aliases, name_pattern)
            if identity is not None:
                portraits.setdefault(known[identity], image_url)
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
        if identity not in allowed:
            continue
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
            "conference": "GrrCON",
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


def _candidate_identity(value: str, known: dict[str, str], aliases: dict[str, str], name_pattern: re.Pattern[str]) -> str | None:
    raw = " ".join(str(value).split()).casefold()
    compact = _compact(raw)
    if compact in aliases:
        return aliases[compact]
    match = name_pattern.search(raw)
    if match:
        return aliases.get(_compact(match.group(0)))
    return None


def _compact(value: str) -> str:
    value = re.sub(r"\b(?:head\s*shot|speaker|portrait|photo|scaled|square|profile|image|img)\b", " ", str(value), flags=re.I)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _slug(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "individual"
