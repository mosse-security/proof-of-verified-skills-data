"""Extract allowlisted portraits from the archived GrrCON 2022 page."""
from pathlib import Path

from scrapers.archives import ArchiveStore
from scrapers.assessors.grrcon_portrait_common import parse_portraits, update_contact_information

SOURCE_URL = "https://grrcon.com/presentations2022/"
ARCHIVE_MEMBER = "presentations2022"
YEAR = 2022


def run() -> list[str]:
    body = ArchiveStore(Path("data/archives/html/grrcon.zip")).read(ARCHIVE_MEMBER)
    if body is None:
        return []
    return update_contact_information(parse_portraits(body), source_url=SOURCE_URL, year=YEAR)
