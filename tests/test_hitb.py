from __future__ import annotations

import unittest
import json
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.assessors.hitb import parse_hitb_session


class HitbParserTests(unittest.TestCase):
    def test_extracts_title_description_and_multiple_speakers(self) -> None:
        rows = parse_hitb_session(
            """
            <html><head><meta property="og:description" content="A detailed talk abstract." /></head>
            <body><h1>Breaking the Sandbox</h1>
              <h2>Speakers</h2><a href="/speaker/alice/">Alice Example</a>
              <a href="/speaker/bob/">Bob Example</a>
            </body></html>
            """,
            "https://conference.hitb.org/hitbsecconf2024bkk/session/breaking-the-sandbox/",
        )
        self.assertEqual([(row[0], row[1]) for row in rows], [
            ("Breaking the Sandbox", "Alice Example"),
            ("Breaking the Sandbox", "Bob Example"),
        ])
        self.assertEqual(rows[0][2], "A detailed talk abstract.")

    def test_prefers_full_abstract_paragraphs_over_truncated_metadata(self) -> None:
        rows = parse_hitb_session(
            """
            <meta property="og:description" content="Short excerpt [&hellip;]" />
            <h1>Full Abstract</h1><p>First complete paragraph with enough detail to retain.</p>
            <p>Second complete paragraph with additional technical detail.</p>
            <h2>Speakers</h2><a href="/speaker/a/">A Speaker</a>
            """,
            "https://conference.hitb.org/hitbsecconf2024bkk/session/full-abstract/",
        )
        self.assertIn("First complete paragraph", rows[0][2])
        self.assertIn("Second complete paragraph", rows[0][2])
        self.assertNotIn("Short excerpt", rows[0][2])

    def test_uses_og_title_when_h1_is_company_name(self) -> None:
        rows = parse_hitb_session(
            """
            <meta property="og:title" content="Real Session Title - HITBSecConf2024 - Bangkok" />
            <h1>Undisclosed Co</h1><p>A full abstract with enough detail.</p>
            <h2>Speakers</h2><a href="/speaker/a/">A Speaker</a>
            """,
            "https://conference.hitb.org/hitbsecconf2024bkk/session/real-session/",
        )
        self.assertEqual(rows[0][0], "Real Session Title")

    def test_missing_title_is_not_an_endorsement(self) -> None:
        self.assertEqual(parse_hitb_session("<a href='/speaker/a/'>A</a>", "https://example/"), [])

    def test_all_linked_session_pages_are_archived(self) -> None:
        assessor = json.loads(Path("data/assessors/hitb/hitb.json").read_text(encoding="utf-8"))
        with zipfile.ZipFile("data/archives/html/hitb.zip") as archive:
            members = set(archive.namelist())
            missing = set()
            for source in assessor["links"]["processUrls"]:
                main = urlsplit(source).path.strip("/")
                soup = BeautifulSoup(archive.read(main), "html.parser")
                for link in soup.find_all("a", href=True):
                    if "/session/" not in link["href"]:
                        continue
                    member = urlsplit(urljoin(source, link["href"])).path.strip("/")
                    if member not in members:
                        missing.add(member)
        self.assertEqual(missing, set())


if __name__ == "__main__":
    unittest.main()
