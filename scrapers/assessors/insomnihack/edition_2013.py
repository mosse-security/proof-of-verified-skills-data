"""Parser for the archived Insomni'hack 2013 talks page."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..insomnihack_runner import InsomnihackEndorsement

PAGE_ID = "edition-2013"
YEAR = 2013


def parse_page(body: bytes | str, source_url: str) -> list[InsomnihackEndorsement]:
    soup = BeautifulSoup(body, "html.parser")
    rows: list[InsomnihackEndorsement] = []
    for row in soup.select("table tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all("td")]
        for cell in cells:
            match = re.match(r"^(?P<speaker>[^â€“â€”-]+?)\s+[-â€“â€”]\s+(?P<title>.+)$", cell)
            if not match:
                continue
            speaker = match.group("speaker").strip()
            title = match.group("title").strip()
            if not _is_person(speaker) or not _is_title(title):
                continue
            for name in re.split(r"\s+(?:&|and)\s+", speaker, flags=re.I):
                rows.append(InsomnihackEndorsement(name.strip(), title, title, source_url, YEAR))
    return _unique(rows)


def _is_person(value: str) -> bool:
    words = value.split()
    return 1 <= len(words) <= 5 and len(value) < 70 and any(ch.isupper() for ch in value) and not any(ch in value for ch in ":;!?()")


def _is_title(value: str) -> bool:
    lowered = value.casefold()
    return 8 <= len(value) <= 220 and not lowered.startswith(("welcome", "introduction ", "time "))


def _unique(rows: list[InsomnihackEndorsement]) -> list[InsomnihackEndorsement]:
    seen: set[tuple[str, str]] = set()
    result = []
    for row in rows:
        key = (row.name.casefold(), row.title.casefold())
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result

