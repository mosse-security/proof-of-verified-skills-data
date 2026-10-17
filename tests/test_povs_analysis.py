import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scrapers.povs_analysis import analyze_assessor


class PovsAnalysisTests(unittest.TestCase):
    def test_prepare_matches_transcript_to_endorsement_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_dir = root / "archives"
            archive_dir.mkdir()
            with zipfile.ZipFile(archive_dir / "example-transcripts.zip", "w") as archive:
                archive.writestr("transcripts/abc1234.txt", "A recorded line.\n")
            people = root / "individuals"
            people.mkdir()
            (people / "alice.json").write_text(json.dumps({"endorsements": [{
                "name": "Alice", "label": "Talk", "assessor-id": "example", "year": 2025,
                "url": "https://example.test/talk", "evidence-links": [{"url": "https://youtube.com/watch?v=abc1234"}],
            }]}), encoding="utf-8")
            result = analyze_assessor("example", archive_directory=archive_dir, individuals_directory=people, output_directory=root / "data", prepare_only=True)
            self.assertEqual(result["pending"], 1)
            output = json.loads((root / "data" / "example-youtube-recordings" / "povs-analysis.json").read_text(encoding="utf-8"))
            record = output["pending"][0]
            self.assertEqual(record["person-file"], str(people / "alice.json"))
            self.assertEqual(record["endorsement-index"], 0)
            self.assertEqual(record["video-id"], "abc1234")
            self.assertEqual(record["transcript-member"], "transcripts/abc1234.txt")


if __name__ == "__main__":
    unittest.main()
