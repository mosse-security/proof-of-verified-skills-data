"""Extract featured speaker portraits from the Black Hat MEA 2026 homepage."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scrapers.identity_registry import IdentityRegistry

SOURCE_URL = "https://blackhatmea.com/"
CONFERENCE = "Black Hat MEA"
YEAR = 2026
REGION = "middle-east"
ALLOWLIST_PATH = Path("data/individuals-enumeration.txt")


def parse_portraits(html: bytes | str, source_url: str = SOURCE_URL) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    portraits: dict[str, str] = {}
    for card in soup.select(".meet-hackers-card"):
        title = card.select_one(".meet-hackers-title")
        image = card.select_one(".meet-hackers-image img[src], .meet-hackers-image img[data-src]")
        if not title or not image:
            continue
        name = title.get_text(" ", strip=True)
        alt = image.get("alt", "").strip()
        image_url = image.get("src") or image.get("data-src")
        if not name or not image_url or IdentityRegistry.normalize(name) != IdentityRegistry.normalize(alt):
            continue
        portraits.setdefault(name, urljoin(source_url, image_url))
    return portraits


def update_contact_information(portraits: dict[str, str], contact_directory: Path = Path("data/contact-information")) -> int:
    contact_paths: dict[str, Path] = {}
    for path in Path(contact_directory).glob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = document.get("name")
        if isinstance(name, str):
            contact_paths[IdentityRegistry.normalize(name)] = path
    changed = 0
    allowed = {
        IdentityRegistry.normalize(line.strip()): line.strip()
        for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    for name, image_url in portraits.items():
        identity = IdentityRegistry.normalize(name)
        if identity not in allowed:
            continue
        path = contact_paths.get(identity) or contact_directory / f"{_slug(name)}.json"
        document = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "name": allowed[identity], "contact": [], "biography": ""
        }
        if document.get("image"):
            continue
        document["image"] = {"url": image_url, "source_url": SOURCE_URL, "source_type": "conference", "conference": CONFERENCE, "year": YEAR, "region": REGION, "verified": True}
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        changed += 1
    return changed


def _slug(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "individual"
