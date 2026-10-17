"""Independent parser for the archived Insomni'hack 2025 talks page."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from ..insomnihack_runner import InsomnihackEndorsement

PAGE_ID = "edition-2025"
YEAR = 2025

def parse_page(body: bytes | str, source_url: str) -> list[InsomnihackEndorsement]:
    soup = BeautifulSoup(body, "html.parser")
    rows: list[InsomnihackEndorsement] = []
    for cell_node in soup.select("table td"):
        cell = " ".join(cell_node.get_text(" ", strip=True).split())
        match = re.match(r"^(?P<title>.+)\s+by\s+(?P<speakers>.+)$", cell, flags=re.I)
        if not match:
            continue
        title = match.group("title").strip(" -")
        if not _title(title):
            continue
        for name in re.split(r"\s+(?:&|and)\s+", match.group("speakers"), flags=re.I):
            name = re.sub(r"\s+\([^)]*\)$", "", name).strip(" .")
            if _person(name):
                rows.append(InsomnihackEndorsement(name, title, title, source_url, YEAR))
    return _dedupe(rows)

def _person(value: str) -> bool:
    words = value.split()
    organization = value.casefold()
    return (
        1 <= len(words) <= 6
        and 3 < len(value) < 90
        and any(ch.isupper() for ch in value)
        and not any(c in value for c in ":;!?()/")
        and organization not in {"orange cyberdefense switzerland"}
    )

def _title(value: str) -> bool:
    low = value.casefold()
    return 8 <= len(value) <= 240 and not low.startswith(("welcome", "introduction ", "time ", "coffee", "lunch", "closed", "(continued)"))

def _dedupe(rows: list[InsomnihackEndorsement]) -> list[InsomnihackEndorsement]:
    seen: set[tuple[str, str]] = set()
    result: list[InsomnihackEndorsement] = []
    for row in rows:
        key = (row.name.casefold(), row.title.casefold())
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result
