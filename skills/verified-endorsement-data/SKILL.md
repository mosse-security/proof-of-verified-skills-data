---
name: verified-endorsement-data
description: Maintain this repository's assessor endorsement scrapers, HTML caches, template-shaped records, cyber-domain classification, profile fragments, and per-person individual merges. Use when adding assessors, changing templates or domains, writing parsers, regenerating data, or debugging scraper output.
---

# Verified endorsement data

Use this skill as the repository's operating contract. Preserve the existing
data pipeline and extend it deliberately as new assessors, templates, and
cyber domains are introduced.

## Workflow

1. Inspect `data/templates/endorsement.tpl` and `data/templates/individual.tpl`
   before changing output. Treat the templates as contracts, not suggestions.
2. Inspect the target assessor JSON in `data/assessors/<id>.json`.
   Keep assessor metadata in the assessor file; never duplicate or
   edit unrelated fields such as `peerReview.processUrl` while changing links.
3. Put reusable framework behavior in `endorsement_scraper/`. Put discovered
   site adapters in `scrapers/`, normally one adapter per assessor. Use a
   `BaseCollectionScraper` when one site controls grouped output or local cache
   layout.
4. Prefer cached HTML under `data/archives/html/<assessor>/` or the matching
   `<assessor>.zip`. Fetch only missing pages, save successful responses, and
   support pagination, multiple years, retries, timeouts, and bounded
   concurrency.
5. Emit one endorsement per person when one source item names multiple people.
   Emit a `PersonProfile` alongside it when contact information is present.
   Keep the required biography field empty; biographies are generated later
   from the complete endorsement set. Store profile fragments under
   `data/tmp/profiles`; do not add profile fields to the endorsement contract.
6. Run the merger after scraping. It reads all endorsement arrays and profile
   fragments, groups names case-insensitively, removes duplicate endorsements,
   combines contact data, writes one `individual.tpl` record per person under
   `data/individuals`, and clears the temporary output directories even when
   merging fails. Use `--keep-tmp` only when debugging.
7. Run tests, compile checks, and schema validation before reporting completion.

## Non-negotiable contracts

- Endorsement records must contain exactly the fields represented by
  `endorsement.tpl`; `subtitle` is the only optional field. `description`
  is required and must be non-empty: prefer the source abstract or detailed
  evidence, with a deterministic fallback only when the source has no such
  text.
- Assessor metadata comes from the assessor JSON: name, ID, category,
  `peerReview.rigorLevel`, and `peerReview.reviewType`.
- Every endorsement has a non-empty `domains` array. Use the canonical taxonomy
  in `endorsement_scraper/domains.py`; use `unknown` only when no rule matches.
  Update the central classifier and tests when expanding the taxonomy.
- Every individual record has exactly `name`, `biography`, `contact`, and
  `endorsements`. Contact entries use the template's label plus URL or email.
- Preserve deterministic output, atomic writes, and idempotent reruns. Default
  overwrite behavior must be explicit, and provide a no-overwrite option where
  generated files may be protected.
- Validate generated output centrally. A scraper must not silently introduce
  unsupported fields, domains, assessor metadata, or duplicate records.

## Commands

```powershell
# Discover and run all assessor adapters
python -m endorsement_scraper

# Run one assessor and refresh its grouped output
python -m endorsement_scraper --assessor def-con --overwrite

# Merge all endorsements and profiles into individual records
python -m endorsement_scraper.individuals --overwrite

# Preserve temporary outputs for inspection
python -m endorsement_scraper.individuals --overwrite --keep-tmp

# Run the complete test suite
python -m unittest discover -s tests -q
```

For detailed current module contracts, paths, DEF CON parser layouts, and
extension examples, read [references/architecture.md](references/architecture.md).

## Change discipline

- Add or update tests with every parser, schema, domain, or merge behavior.
- Regenerate affected output after parser changes; do not hand-edit generated
  endorsement or individual JSON.
- Keep source evidence available to domain detection and store it in the
  endorsement `description` field.
- When a source has several page layouts, add a focused parser function and a
  fixture test instead of weakening an existing layout parser.
- Keep biographies empty until the later AI summarization step; merge the
  union of unique contacts without inventing data.


