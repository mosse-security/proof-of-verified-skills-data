from __future__ import annotations

import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from scrapers.archive_coverage import missing_archive_urls


class ArchiveCoverageTest(unittest.TestCase):
    def test_every_configured_process_url_is_archived(self) -> None:
        missing = missing_archive_urls()
        if not missing:
            return
        details = [
            f"{assessor}:\n" + "\n".join(f"  - {url}" for url in urls)
            for assessor, urls in missing.items()
        ]
        self.fail(
            "Configured process URLs are missing from local archives. "
            "Download them manually and place them in the assessor ZIP, then rerun:\n"
            + "\n".join(details)
        )

    def test_blue_team_con_linked_talk_pages_are_archived(self) -> None:
        """Every talk detail link exposed by the historical indexes is cached."""
        archive_path = Path("data/archives/html/blue-team-con.zip")
        with zipfile.ZipFile(archive_path) as archive:
            members = set(archive.namelist())
            linked_members: set[str] = set()
            for member in members:
                if not member.startswith("btc-history/"):
                    continue
                soup = BeautifulSoup(archive.read(member), "html.parser")
                for heading in soup.find_all("h2"):
                    link = heading.find("a", href=True)
                    if not link:
                        continue
                    parsed = urlsplit(link["href"])
                    if parsed.netloc.casefold() == "blueteamcon.com":
                        path = parsed.path.strip("/")
                        if path:
                            linked_members.add(path)
        missing = sorted(linked_members - members)
        self.assertFalse(
            missing,
            "Blue Team Con index links are missing from blue-team-con.zip:\n"
            + "\n".join(f"  - {member}" for member in missing),
        )
