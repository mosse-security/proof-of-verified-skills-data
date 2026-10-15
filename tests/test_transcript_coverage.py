from __future__ import annotations

import json
import re
import zipfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INDIVIDUALS = ROOT / "data" / "individuals"
ENRICHMENTS = ROOT / "data" / "enrichments"
TRANSCRIPTS = ROOT / "data" / "archives" / "yt-transcripts"


def _video_id(url: str) -> str | None:
    match = re.search(r"[?&]v=([\w-]{6,})", url)
    return match.group(1) if match else None


def _endorsement_video_ids(assessor_id: str) -> set[str]:
    result: set[str] = set()
    for path in INDIVIDUALS.glob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        for endorsement in document.get("endorsements", []):
            if endorsement.get("assessor-id") != assessor_id:
                continue
            for link in endorsement.get("evidence-links", []):
                video_id = _video_id(str(link.get("url", "")))
                if video_id:
                    result.add(video_id)
    return result


class TranscriptCoverageTests(unittest.TestCase):
    def test_black_hat_missing_transcripts_are_reported_with_urls(self) -> None:
        """Keep the Black Hat gap report actionable while its archive is built."""
        assessor_id = "black-hat"
        archive_path = TRANSCRIPTS / f"{assessor_id}-transcripts.zip"
        enrichment_path = ENRICHMENTS / f"{assessor_id}-youtube-recordings" / "data.zip"
        if not archive_path.is_file() or not enrichment_path.is_file():
            self.skipTest("Black Hat transcript or video archive is not present yet")
        with zipfile.ZipFile(archive_path) as archive:
            transcript_ids = {
                Path(member).stem
                for member in archive.namelist()
                if member.startswith("transcripts/") and member.endswith(".txt")
            }
        with zipfile.ZipFile(enrichment_path) as enrichment:
            catalog = json.loads(enrichment.read("data.json"))
        catalog_urls = {
            str(item.get("video-id")): str(item.get("url", ""))
            for item in catalog
            if item.get("video-id") and item.get("url")
        }
        missing = sorted(_endorsement_video_ids(assessor_id) - transcript_ids)
        details = ", ".join(f"{video_id} ({catalog_urls.get(video_id, 'URL unavailable')})" for video_id in missing)
        self.assertFalse(missing, f"Black Hat videos missing transcripts: {details}")

    def test_transcript_archives_cover_every_captured_talk_video(self) -> None:
        for archive_path in sorted(TRANSCRIPTS.glob("*-transcripts.zip")):
            assessor_id = archive_path.name.removesuffix("-transcripts.zip")
            with self.subTest(assessor=assessor_id), zipfile.ZipFile(archive_path) as archive:
                members = set(archive.namelist())
                transcript_ids = {
                    Path(member).stem for member in members if member.startswith("transcripts/") and member.endswith(".txt")
                }
                captured_ids = _endorsement_video_ids(assessor_id)
                missing = sorted(captured_ids - transcript_ids)
                self.assertFalse(
                    missing,
                    f"{assessor_id} has captured talk videos without transcripts: {', '.join(missing)}",
                )

    def test_transcript_members_are_in_the_video_catalog_and_unique(self) -> None:
        for archive_path in sorted(TRANSCRIPTS.glob("*-transcripts.zip")):
            assessor_id = archive_path.name.removesuffix("-transcripts.zip")
            enrichment_path = ENRICHMENTS / f"{assessor_id}-youtube-recordings" / "data.zip"
            with self.subTest(assessor=assessor_id), zipfile.ZipFile(archive_path) as archive:
                manifest = json.loads(archive.read("manifest.json"))
                manifest_ids = [str(item["video-id"]) for item in manifest.get("videos", []) if item.get("status") == "archived"]
                self.assertEqual(len(manifest_ids), len(set(manifest_ids)), "duplicate video IDs in transcript manifest")
                with zipfile.ZipFile(enrichment_path) as enrichment:
                    catalog_ids = {str(item.get("video-id")) for item in json.loads(enrichment.read("data.json"))}
                self.assertTrue(set(manifest_ids) <= catalog_ids)


if __name__ == "__main__":
    unittest.main()
