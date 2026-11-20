"""Shared, allowlist-gated helpers for Blue Team Con portrait pages."""
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
    portraits: dict[str, str] = {}
    for image in soup.find_all("img"):
        image_url = image.get("data-orig-src") or image.get("src")
        if not isinstance(image_url, str) or not image_url.startswith(("http://", "https://")):
            continue
        labels = [image.get("title", ""), image.get("alt", ""), Path(urlsplit(unquote(image_url)).path).stem]
        for label in labels:
            identity = _candidate_identity(label, known)
            if identity is None:
                continue
            name = known[identity]
            portraits.setdefault(name, urljoin(source_url, image_url))
            break
    return portraits


def update_contact_information(
    portraits: dict[str, str], *, source_url: str, year: int,
    contact_directory: Path = Path("data/contact-information"),
) -> list[str]:
    contact_paths: dict[str, Path] = {}
    for path in Path(contact_directory).glob("*.json"):
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
            "url": image_url, "source_url": source_url, "source_type": "conference",
            "conference": "Blue Team Con", "year": year, "verified": True,
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


def _slug(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "individual"


def _existing_allowlisted_contacts() -> dict[str, tuple[str, Path]]:
    allowed = {
        IdentityRegistry.normalize(line.strip())
        for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    result: dict[str, tuple[str, Path]] = {}
    for path in Path("data/contact-information").glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = document.get("name")
        if isinstance(name, str) and IdentityRegistry.normalize(name) in allowed:
            result[IdentityRegistry.normalize(name)] = (name, path)
    return result


def _candidate_identity(value: str, known: dict[str, tuple[str, Path]]) -> str | None:
    cleaned = re.sub(r"\b(?:head\s*shot|speaker|portrait|photo)\b", " ", str(value), flags=re.I)
    cleaned = re.sub(r"(?:^|[-_])e\d{8,}(?=$|[-_.])", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"(?:^|[-_])(?:scaled|square|profile|image|img|photo|1)(?=$|[-_.])", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"^20\d{2}", "", cleaned)
    cleaned = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", cleaned)
    cleaned = re.sub(r"[_.-]+", " ", cleaned)
    identity = IdentityRegistry.normalize(cleaned)
    return identity if identity in known else None
