from __future__ import annotations

import json
import zipfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSESSORS = ROOT / "data" / "assessors"
ENRICHMENTS = ROOT / "data" / "enrichments"


def _video_sources(document: dict) -> bool:
    links = document.get("links", {})
    if not isinstance(links, dict):
        return False
    for key in ("youtubeUrl", "youtubePlaylistUrl", "youtubePlaylistUrls"):
        value = links.get(key)
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, list) and any(isinstance(item, str) and item.strip() for item in value):
            return True
    return False


class VideoEnrichmentCoverageTest(unittest.TestCase):
    """Every assessor advertising video sources must have a usable dataset."""

    def test_video_sources_have_nonempty_enrichment_archives(self) -> None:
        missing: list[str] = []
        empty: list[str] = []
        for assessor_path in sorted(ASSESSORS.glob("*.json")):
            document = json.loads(assessor_path.read_text(encoding="utf-8"))
            if not _video_sources(document):
                continue
            assessor_id = document.get("id") or assessor_path.stem
            archive_path = ENRICHMENTS / f"{assessor_id}-youtube-recordings" / "data.zip"
            if not archive_path.is_file():
                missing.append(str(archive_path.relative_to(ROOT)))
                continue
            try:
                with zipfile.ZipFile(archive_path) as archive:
                    records = json.loads(archive.read("data.json"))
            except (KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
                self.fail(f"Invalid video enrichment archive {archive_path}: {exc}")
            if not isinstance(records, list) or not records:
                empty.append(str(archive_path.relative_to(ROOT)))
        self.assertFalse(missing, "Assessors with video sources have no enrichment archive: " + ", ".join(missing))
        self.assertFalse(empty, "Video enrichment archives contain no records: " + ", ".join(empty))


if __name__ == "__main__":
    unittest.main()
