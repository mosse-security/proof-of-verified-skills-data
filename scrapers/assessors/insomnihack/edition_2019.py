"""Independent parser for the archived Insomni'hack 2019 talks page."""
from __future__ import annotations

import re
from bs4 import BeautifulSoup
from ..insomnihack_runner import InsomnihackEndorsement

PAGE_ID = "edition-2019"
YEAR = 2019

def parse_page(body: bytes | str, source_url: str) -> list[InsomnihackEndorsement]:
    soup = BeautifulSoup(body, "html.parser")
    rows: list[InsomnihackEndorsement] = []
    for row in soup.select("table tr"):
        for cell_node in row.find_all(["td", "th"]):
            cell = " ".join(cell_node.get_text(" ", strip=True).split())
            match = re.match(r"^(?P<title>.+)\s+by\s+(?P<speaker>.+)$", cell, flags=re.I)
            if not match:
                continue
            title = match.group("title").strip(" -")
            speakers = match.group("speaker").split(",", 1)[0].strip()
            if not _title(title):
                continue
            for name in re.split(r"\s+(?:&|and)\s+", speakers, flags=re.I):
                if _person(name):
                    rows.append(InsomnihackEndorsement(name.strip(), title, title, source_url, YEAR))
    return _dedupe(rows)

def _person(value: str) -> bool:
    words = value.split()
    return 1 <= len(words) <= 6 and 3 < len(value) < 80 and any(ch.isupper() for ch in value) and not any(c in value for c in ":;!?()/")

def _title(value: str) -> bool:
    low = value.casefold()
    return 8 <= len(value) <= 240 and not low.startswith(("welcome", "introduction ", "time ", "coffee", "lunch", "keynote by"))

def _dedupe(rows: list[InsomnihackEndorsement]) -> list[InsomnihackEndorsement]:
    seen: set[tuple[str, str]] = set()
    result: list[InsomnihackEndorsement] = []
    for row in rows:
        key = (row.name.casefold(), row.title.casefold())
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result
