from __future__ import annotations

import json
import unittest
from pathlib import Path


class PageParserCoverageTests(unittest.TestCase):
    def test_every_configured_non_insomnihack_page_has_its_own_parser(self):
        assessors = Path("data/assessors")
        parser_root = Path("scrapers/assessors")
        expected = 0
        for config_path in sorted(assessors.glob("*.json")):
            assessor_id = config_path.stem
            if assessor_id == "insomnihack":
                continue
            document = json.loads(config_path.read_text(encoding="utf-8"))
            urls = document.get("links", {}).get("processUrls", [])
            expected += len(urls)
            modules = sorted((parser_root / assessor_id).glob("page-*.py"))
            self.assertEqual(len(modules), len(urls), assessor_id)
            for index, (url, module) in enumerate(zip(urls, modules), 1):
                source = module.read_text(encoding="utf-8")
                self.assertIn(f"SOURCE_URL = {url!r}", source, str(module))
                self.assertIn("def parse_page(", source, str(module))
                self.assertIn(f"page-{index:03d}-", module.name, str(module))

        actual = sum(
            len(list(path.glob("page-*.py")))
            for path in parser_root.iterdir()
            if path.is_dir()
        )
        self.assertEqual(actual, expected)

    def test_insomnihack_page_parsers_remain_page_owned(self):
        modules = sorted(Path("scrapers/assessors/insomnihack").glob("edition_*.py"))
        self.assertEqual(len(modules), 13)
        for module in modules:
            self.assertIn("def parse_page(", module.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
