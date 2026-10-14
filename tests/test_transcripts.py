import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from endorsement_scraper.transcripts import _clean_vtt, archive_transcripts


class TranscriptTests(unittest.TestCase):
    def test_clean_vtt_removes_timing_and_scrolling_duplicates(self):
        source = "WEBVTT\n\n00:00.000 --> 00:01.000\nHello\nHello\n<00:01.000>world\n"
        self.assertEqual(_clean_vtt(source), "Hello\nworld\n")

    def test_rerun_skips_existing_transcript(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            enrichment = root / "enrichments" / "example-youtube-recordings"
            enrichment.mkdir(parents=True)
            with zipfile.ZipFile(enrichment / "data.zip", "w") as archive:
                archive.writestr("data.json", json.dumps([{"video-id": "abc1234", "url": "https://www.youtube.com/watch?v=abc1234", "title": "Talk"}]))
            with patch("endorsement_scraper.transcripts._download_transcript", return_value="Transcript\n") as download:
                first = archive_transcripts("example", archived_directory=root / "archived", enrichments_directory=root / "enrichments")
                second = archive_transcripts("example", archived_directory=root / "archived", enrichments_directory=root / "enrichments")
            self.assertEqual(first["downloaded"], 1)
            self.assertEqual(second["skipped"], 1)
            self.assertEqual(download.call_count, 1)


if __name__ == "__main__":
    unittest.main()
