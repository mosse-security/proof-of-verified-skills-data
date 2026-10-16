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
   site adapters in `scrapers/`, normally one adapter per assessor. There is no
   fixed assessor list: discovery recursively loads any number of adapters and
   the merger recursively consumes any assessor directory. Use a
   `BaseCollectionScraper` when one site controls grouped output or local cache
   layout.
4. Prefer cached HTML under `data/archives/html/<assessor>/` or the matching
   `<assessor>.zip`. Fetch only missing pages, save successful responses, and
   support pagination, multiple years, retries, timeouts, and bounded
   concurrency. For browser-only retrieval, use one bounded Edge process at a
   time and wait for it to exit before starting the next URL.
5. Emit one endorsement per person when one source item names multiple people.
   Emit a `PersonProfile` alongside it when contact information is present.
   Keep the required biography field empty; biographies are generated later
   from the complete endorsement set. Store profile fragments under
   `data/tmp/profiles`; do not add profile fields to the endorsement contract.
6. Run every configured scraper before the merger, not only the assessor being
   debugged. A partial scrape can replace a person's complete history with a
   smaller set of endorsements.
7. Run the merger after scraping. It reads all endorsement arrays and profile
   fragments, groups names case-insensitively, removes duplicate endorsements,
   combines contact data, writes one `individual.tpl` record per person under
   `data/individuals`, and clears the temporary output directories even when
   merging fails. Use `--keep-tmp` only when debugging.
8. Run `tests.test_individuals_coverage` after merging. Every active
   individual must have at least one endorsement; stale profile-only files
   must be removed from `data/individuals` before publishing.
9. Run tests, compile checks, and schema validation before reporting completion.
10. Run enrichers before endorsement generation when external datasets are
   needed. Enrichers are discovered recursively under `enrichers/` and write
   one dataset archive per enricher under `data/enrichments/`.
11. For every assessor JSON that advertises a YouTube URL or playlist,
    including `archiveInventory.youtubeYears`, collect videos before
    regenerating endorsements. Run video enrichers with `--workers 1`, verify
    non-empty catalogs, and report both catalog size and matched evidence-link
    count. A large unmatched remainder requires better matching logic.
12. For every non-empty YouTube catalog, archive English transcripts with
   `python -m endorsement_scraper.transcripts --assessor <id>`. This writes
   one idempotent ZIP under `data/archives/yt-transcripts/` per assessor, skips unchanged video
   IDs, and captures newly added or changed videos on later runs.
13. Run `python -m unittest tests.test_transcript_coverage -v` whenever
    transcript archives exist. This cross-references transcript members with
    captured endorsement YouTube links and the source video catalog.
14. Inspect `data/stats.json` after each scraper run. It is the operator and
   test contract for timestamps, counts, errors, and capture sanity checks.

## Non-negotiable contracts

- Endorsement records must contain exactly the fields represented by
  `endorsement.tpl`; `subtitle` is the only optional field. `description`
  is required and must be non-empty: prefer the source abstract or detailed
  evidence, with a deterministic fallback only when the source has no such
  text.
- Every endorsement must contain an `evidence-links` array and an `evidence`
  boolean. Each evidence-link item has
  exactly a non-empty `title` and absolute HTTP(S) `url`; an empty array is
  valid when no enricher matches, and `evidence` must mirror whether it is
  empty.
- Every endorsement must contain a `povs` object with `milestones`, `level`,
  and `explanation`. Evidence-free records use four false milestones, level
  `0`, and the exact explanation `No evidence discovered for this record
  therefore it could not be verified`. Evidence-backed conference talks from
  approved assessors use `verifiable=true`, `defended=true`,
  `recognized=true`, `trusted=false`, level `2`, and explain that industry use
  in situations of real consequence could not be verified. Build and validate this centrally; never hand-edit generated
  POVS.
- Assessor metadata comes from the assessor JSON: name, ID, category,
  `peerReview.rigorLevel`, and `peerReview.reviewType`.
- Every endorsement has a non-empty `domains` array and a `subspecialties`
  object keyed exactly by those domains. Use the canonical taxonomy in
  `endorsement_scraper/domains.py`; use `unknown` only when no rule matches.
  Specialty identifiers are lowercase and hyphenated, and must remain under
  their parent domain.
  Update the central classifier and tests when expanding the taxonomy.
- Every individual record has exactly `name`, `last-updated`, `biography`,
  `contact`, `stats`, and `endorsements`. `stats` is derived from endorsements
  and includes total, unique assessor, evidence-backed, non-evidence, and
  per-domain counts.
  `last-updated` is an ISO-8601 UTC timestamp:
  unchanged merges preserve it, while content changes refresh it. Contact
  entries use the template's label plus URL or email.
- Preserve deterministic output, atomic writes, and idempotent reruns. Default
  overwrite behavior must be explicit, and provide a no-overwrite option where
  generated files may be protected.
- Validate generated output centrally. A scraper must not silently introduce
  unsupported fields, domains, assessor metadata, or duplicate records.
- The core runner removes clearly non-endorsement event sessions that would
  otherwise be `unknown`; missing-abstract records remain for later enrichment.

## Commands

```powershell
# Discover and run all assessor adapters
python -m endorsement_scraper

# Run one assessor and refresh its grouped output
python -m endorsement_scraper --assessor def-con --overwrite
python -m endorsement_scraper --assessor black-hat --overwrite

# Rebuild all assessors before merging individuals
python -m endorsement_scraper --overwrite --workers 1

# Confirm every configured source URL has a local archive member
python -m unittest tests.test_archive_coverage -v

# Merge all endorsements and profiles into individual records
python -m endorsement_scraper.individuals --overwrite

# Detect stale/profile-only individual files
python -m unittest tests.test_individuals_coverage -v

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
- When choosing the next conference to process, use only the shortlisted
  assessor inventory in `data/assessors/*.json`. Never recommend an external
  conference that is absent from that local list; add and review its assessor
  definition first if expanding scope is intended.
- Keep source evidence available to domain detection and store it in the
  endorsement `description` field.
- When a source has several page layouts, add a focused parser function and a
  fixture test instead of weakening an existing layout parser.
- Keep biographies empty until the later AI summarization step; merge the
  union of unique contacts without inventing data.


