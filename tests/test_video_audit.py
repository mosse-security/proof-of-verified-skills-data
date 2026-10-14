import json
import logging
import tempfile
import unittest
import zipfile
from pathlib import Path

from endorsement_scraper.video_audit import audit_conference_video_matching


class VideoAuditTests(unittest.TestCase):
    def test_logs_unmatched_videos_and_endorsements_without_videos(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "assessors").mkdir()
            (root / "output" / "example").mkdir(parents=True)
            (root / "enrichments" / "example-youtube-recordings").mkdir(parents=True)
            (root / "assessors" / "example.json").write_text(json.dumps({"id": "example", "category": "conference_community"}))
            (root / "output" / "example" / "records.json").write_text(json.dumps([
                {"label": "Matched", "evidence-links": [{"url": "https://www.youtube.com/watch?v=abc1234"}]},
                {"label": "Missing", "evidence-links": []},
            ]))
            with zipfile.ZipFile(root / "enrichments" / "example-youtube-recordings" / "data.zip", "w") as archive:
                archive.writestr("data.json", json.dumps([
                    {"video-id": "abc1234"}, {"video-id": "def5678"}
                ]))
            with self.assertLogs("endorsement_scraper.video_audit", level=logging.WARNING) as captured:
                audit_conference_video_matching(
                    assessors_directory=root / "assessors",
                    output_directory=root / "output",
                    enrichments_directory=root / "enrichments",
                )
            self.assertIn("not matched to endorsements", "\n".join(captured.output))
            self.assertIn("endorsements have no matched YouTube video", "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
