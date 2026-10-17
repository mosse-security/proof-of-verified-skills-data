import unittest

from scrapers.assessors.usenix_security import parse_usenix_security


class UsenixSecurityParserTests(unittest.TestCase):
    def test_splits_conjoined_authors_without_emitting_and_prefix(self) -> None:
        rows = parse_usenix_security(
            """
            <article class="node-paper">
              <h2><a href="/paper/example">Example Paper</a></h2>
              <div class="field-name-field-paper-people-text">
                <p>Simon Langowski, Kaiwen He, and Srinivas Devadas, <em>MIT</em></p>
              </div>
            </article>
            """,
            "https://www.usenix.org/conference/usenixsecurity26/technical-sessions",
        )
        self.assertEqual([row[1] for row in rows], [
            "Simon Langowski", "Kaiwen He", "Srinivas Devadas"
        ])
        self.assertFalse(any(name.casefold().startswith("and ") for _, name, *_ in rows))


if __name__ == "__main__":
    unittest.main()
