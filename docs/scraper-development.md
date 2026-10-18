# Scraper development

## Add or repair an archive

1. Confirm the assessor is in the approved assessor metadata list.
2. Inventory every historical page and archive member before parsing.
3. Keep source pages in `data/archives/html`; use `tmp/` only for transient work.
4. Create one dedicated Python parser for every configured HTML archive page
   under `scrapers/assessors/<assessor-id>/`.
5. Validate each parser against its own page layout. Do not assume that a
   parser for one edition works for another edition.
6. Add regression tests for multi-speaker parsing, aliases, titles, affiliation
   fragments, and known false positives.
7. Run the assessor, inspect `individuals-not-validated.txt`, and verify several
   generated endorsements and individual records.

The page-parser coverage test must pass: every configured archive page needs a
dedicated parser module. Parser output must use the actual person as `name` and
the talk title as `label`.

## Tests and validation

```powershell
python -m unittest discover -s tests -p 'test_*.py' -q
python -m unittest tests.test_archive_coverage -v
python -m unittest tests.test_individual_quality -v
python -m compileall -q scrapers tests
```

When changing one assessor, run its focused tests and inspect its local output
before running the full pipeline.
