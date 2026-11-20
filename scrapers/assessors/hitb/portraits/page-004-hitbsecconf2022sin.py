"""Extract allowlisted portraits from the archived HITB Singapore 2022 page."""
from pathlib import Path
from scrapers.archives import ArchiveStore
from scrapers.assessors.hitb_portrait_common import parse_portraits, update_contact_information

SOURCE_URL = "https://conference.hitb.org/hitbsecconf2022sin"
ARCHIVE_MEMBER = "hitbsecconf2022sin"
YEAR = 2022


def run() -> list[str]:
    body = ArchiveStore(Path("data/archives/html/hitb.zip")).read(ARCHIVE_MEMBER)
    return update_contact_information(parse_portraits(body, SOURCE_URL), source_url=SOURCE_URL, year=YEAR) if body else []
