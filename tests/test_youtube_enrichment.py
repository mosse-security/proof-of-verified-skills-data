import unittest
from pathlib import Path
import zipfile
import json


class YouTubeEnrichmentOutputTests(unittest.TestCase):
    def test_cansecwest_and_layer_one_outputs_exist_when_collected(self):
        for name in ("cansecwest-youtube-recordings", "layer-one-youtube-recordings"):
            path = Path("data/enrichments") / name / "data.zip"
            if not path.exists():
                continue
            with zipfile.ZipFile(path) as archive:
                records = json.loads(archive.read("data.json"))
            self.assertTrue(records)
            self.assertTrue(all(str(record.get("url", "")).startswith("https://www.youtube.com/") for record in records))


if __name__ == "__main__":
    unittest.main()
