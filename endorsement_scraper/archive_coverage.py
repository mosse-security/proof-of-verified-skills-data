"""Validate that configured source URLs have local archive documents."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import urlsplit


def archive_member(assessor_id: str, url: str) -> str:
    """Return the archive member used for a configured source URL.

    DEF CON archives predate the ZIP layout and use ``defcon-N/speakers.html``
    for URLs whose public path is ``html/defcon-N/dc-N-speakers.html``.
    Other assessors use the normalized URL path directly.
    """
    path = urlsplit(url).path.strip("/") or "index.html"
    if assessor_id == "def-con":
        match = re.search(r"(?:^|/)defcon-(\d+)(?:/|$)", path)
        if match:
            return f"defcon-{match.group(1)}/speakers.html"
        if "defcon-safemode" in path.casefold():
            return "defcon-safemode/speakers.html"
    # Match ArchiveStore, which normalizes members through PurePosixPath.
    return PurePosixPath(path).as_posix()


def missing_archive_urls(
    *,
    assessors_directory: Path = Path("data/assessors"),
    archive_directory: Path = Path("data/archives/html"),
) -> dict[str, list[str]]:
    """Return configured URLs that do not have a member in their assessor ZIP."""
    missing: dict[str, list[str]] = {}
    for assessor_path in sorted(assessors_directory.glob("*.json")):
        document = json.loads(assessor_path.read_text(encoding="utf-8"))
        urls = document.get("links", {}).get("processUrls", [])
        if not urls:
            continue
        archive_path = archive_directory / f"{assessor_path.stem}.zip"
        members = set()
        if archive_path.is_file():
            with zipfile.ZipFile(archive_path) as archive:
                members = set(archive.namelist())
        absent = [
            url
            for url in urls
            if archive_member(assessor_path.stem, url) not in members
        ]
        if absent:
            missing[assessor_path.stem] = absent
    return missing
