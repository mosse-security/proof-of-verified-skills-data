"""Extract portraits from the archived Blue Team Con 2023 page only."""
from pathlib import Path

from scrapers.archives import ArchiveStore
from scrapers.assessors.blue_team_con_portrait_common import parse_portraits, update_contact_information

SOURCE_URL = "https://blueteamcon.com/btc-history/talks-blue-team-con-2023/"
ARCHIVE_MEMBER = "btc-history/talks-blue-team-con-2023"
YEAR = 2023


def run() -> list[str]:
    body = ArchiveStore(Path("data/archives/html/blue-team-con.zip")).read(ARCHIVE_MEMBER)
    if body is None:
        return []
    return update_contact_information(parse_portraits(body, SOURCE_URL), source_url=SOURCE_URL, year=YEAR)

