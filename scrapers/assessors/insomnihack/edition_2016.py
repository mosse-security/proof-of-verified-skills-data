"""Independent title-first agenda parser for the archived Insomni'hack 2016 talks page."""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from ..insomnihack_runner import InsomnihackEndorsement
PAGE_ID = "edition-2016"
YEAR = 2016

def parse_page(body: bytes | str, source_url: str) -> list[InsomnihackEndorsement]:
    soup = BeautifulSoup(body, "html.parser")
    out = []
    for row in soup.select("table tr"):
        for node in row.find_all(["td", "th"])[1:]:
            parsed = _cell(" ".join(node.get_text(" ", strip=True).split()))
            if parsed:
                title, names = parsed
                out.extend(InsomnihackEndorsement(n, title, title, source_url, YEAR) for n in names)
    return _dedupe(out)

def _cell(cell: str):
    if not cell or re.match(r"^(?:-|closed|coffee|lunch|time|welcome|intro|keynote\b)", cell, re.I):
        return None
    by = re.match(r"^(?P<title>.+)\s+by\s+(?P<names>.+)$", cell, re.I)
    if by:
        title, names = by.group("title").strip(" -"), _names(by.group("names"))
        return (title, names) if names and _title(title) else None
    # These pages use title followed by the final capitalized name(s), not
    # speaker-first rows. A page-specific parser must not reverse that order.
    words = cell.split()
    counts = (4, 3, 2) if "," in cell else (2, 3, 4)
    for count in counts:
        if len(words) <= count:
            continue
        candidate = " ".join(words[-count:])
        if not all(w[:1].isupper() for w in candidate.split()):
            continue
        names = _names(candidate)
        title = " ".join(words[:-count]).strip(" -")
        if names and _title(title):
            return title, names
    return None

def _names(value: str) -> list[str]:
    out = []
    for name in re.split(r"\s*(?:,|&|and)\s*", value, flags=re.I):
        name = re.sub(r"\s*\([^)]*\)$", "", name).strip(" .,")
        if _person(name) and len(name.split()) >= 2:
            out.append(name)
    return out

def _person(value: str) -> bool:
    words = value.split()
    return 1 <= len(words) <= 4 and 2 < len(value) < 90 and any(ch.isupper() for ch in value) and not any(c in value for c in ":;!?()/")

def _title(value: str) -> bool:
    low = value.casefold()
    return 8 <= len(value) <= 240 and not low.startswith(("welcome", "introduction ", "time ", "coffee", "lunch", "closed", "keynote"))

def _dedupe(rows):
    seen = set()
    out = []
    for row in rows:
        key = (row.name.casefold(), row.title.casefold())
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out
