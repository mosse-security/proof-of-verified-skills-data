# Repository architecture reference

## Data paths

- `data/assessors/<id>.json`: authoritative assessor metadata and
  source URLs. DEF CON uses `links.processUrls` for its historical archive.
- `data/archives/html/<assessor>/...` or `<assessor>.zip`: local source HTML.
  Scrapers are local-first and fetch missing pages over HTTP. ZIP entries are
  read in memory; the archive layer is byte-oriented so CSV/XLSX readers can
  be added later without changing scraper orchestration.
- `data/tmp/endorsements/<assessor>/...json`: canonical endorsement records.
  Collection scrapers may write arrays, usually one file per conference/year.
- `data/tmp/profiles/<assessor>/...json`: temporary profile fragments shaped as
  `{name, biography, contact}`. Standard scrapers use `PersonProfile` and
  `ProfileStore`; collection scrapers may write grouped fragments directly.
- `data/individuals/<slug>.json`: final merged records shaped as
  `{name, last-updated, biography, contact, stats, endorsements}`. `stats`
  contains endorsement total, unique assessor count, evidence counts, counts
  for every canonical domain, and nested per-domain subspecialty counts.
- The individual merger clears `data/tmp/endorsements` and
  `data/tmp/profiles` after a successful run; use `--keep-tmp` for debugging.
- The merger does not automatically delete every legacy profile-only file.
  After a full regeneration, run `tests.test_individuals_coverage` and move
  reported zero-endorsement files out of `data/individuals` before publishing.
- `data/templates/`: current user-facing contracts. Update validators and tests
  whenever these change.

## Core modules

- `base.py`: `BaseScraper`, `BaseCollectionScraper`, and collection context.
- `models.py`: `Request`, `Response`, `Endorsement`, `PersonProfile`, and
  `PageResult`. Use `PageResult.build(endorsements, follow, profiles=...)`.
- `runner.py`: concurrent scraper execution, page fingerprinting, endorsement
  validation, and profile storage.
- `storage.py`: atomic `EndorsementStore` and `ProfileStore`.
- `archives.py`: directory/ZIP source archive access. Keep this byte-oriented
  boundary when adding CSV/XLSX readers so format parsing stays out of scraper
  orchestration.
- `schema.py`: assessor metadata loading, endorsement/profile construction,
  and strict output validation.
- `domains.py`: canonical taxonomy, detection rules, normalization, and output
  validation.
- `individuals.py`: profile/endorsement aggregation and deterministic filenames.
- `discovery.py`: recursive dynamic discovery of scraper plugins under
  `scrapers/` (underscore-prefixed files are ignored).
- `archive_coverage.py`: maps every configured `links.processUrls` entry to an
  archive member and reports missing source pages across all assessors.

## Endorsement mapping

The internal `Endorsement` fields map to the template as follows:

| Internal field | Template field |
| --- | --- |
| `recipient` | `name` |
| `title` | `label` |
| `description` | `description` |
| `kind` | `type` |
| assessor JSON `name` | `assessor` |
| assessor ID | `assessor-id` |
| assessor JSON `category` | `assessor-category` |
| assessor `peerReview.rigorLevel` | `assessor-rigor-level` |
| assessor `peerReview.reviewType` | `reviewType` |
| `subtitle` | `subtitle` |
| `source_url` | `url` |
| enricher matches | `evidence-links` and `evidence` |
| `year`/date/details year | `year` |
| classifier result | `domains` |

The person name is required; do not substitute a talk title for a missing
recipient. A four-digit year is required for standard records.

## Profile extraction

When a page lists multiple speakers, create one endorsement for each speaker
and map each speaker's profile fragment separately. Do not copy one speaker's
contacts to every co-speaker. Biography fields remain empty until a later AI
summarization step. Normalize contact labels such as
`linkedin`, `website`, `twitter`, and `email`, preserve absolute URLs, and
avoid scraping navigation links such as “Return to Top”.

The merger matches names case-insensitively and tolerates whitespace changes.
It removes exact duplicate endorsement objects and unions contacts. It does
not infer aliases beyond parser-side matching or invent missing profile data.
It derives each profile's `stats` object from the final deduplicated
endorsement array, including evidence and per-domain counts.
Individual records include a `last-updated` UTC timestamp. The merger compares
all other fields with the existing file and preserves that timestamp for an
unchanged record; any content change receives a fresh timestamp.
The `stats.assessors` value counts distinct endorsement `assessor-id` values
after deduplication, so a person represented by multiple assessors remains one
individual with a cross-assessor count.

## Enrichers

Enrichers are plugins discovered recursively below `enrichers/`, independent of
the endorsement scrapers. Each has a stable `enricher_id` and writes a JSON
array as `data.json` inside `data/enrichments/<enricher-id>/data.zip`.
`EnrichmentCatalog` loads all such datasets and adapters pass matching records
into `evidence-links`, keeping collection, storage, matching, and rendering
separate as the number of enrichers grows.

## Run statistics

`endorsement_scraper.stats` writes an atomic `data/stats.json` after the main
scraper CLI completes. It records UTC timestamps, duration, per-scraper counts,
totals, evidence-link counts, errors, and validations such as the DEF CON
non-zero endorsement check.
Tests can call `validate_run_stats` against the file or synthetic reports.

## Conference adapter lessons

`endorsement_scraper/assessors/def_con.py` supports multiple historical
HTML layouts. Modern pages use `.talk`, `.speaker`, `.speaker-bio`/
`.speakerBio`, and empty abstract markers whose description is in following
siblings. DEF CON 18–21 use `h2.title`/`h4.byLine`; their speaker bios may be
`span.speakerBio`. Older layouts require dedicated parsers. Keep each layout
isolated and add a fixture test when changing it.

DEF CON output uses `type: presentation`, subtitle `DEF CON N`, and calendar
year `1992 + N` (DEF CON Safe Mode is conference 28). The source URL should
include the talk fragment when one exists.

Black Hat demonstrates a second scalable pattern: one collection adapter can
parse both legacy `h2` briefing blocks and modern `.data-container` schedule
records, while regional and historical URLs remain data in the assessor JSON.
Pages with no published sessions are cached but do not produce empty output
files. Keep layout-specific parsing functions isolated and add fixtures when a
new regional or historical layout appears.

Before parsing an assessor, run `python -m unittest tests.test_archive_coverage
-v`. If a page was downloaded manually, place the complete main HTML document
in `tmp/`, map it to the URL-derived ZIP member with `ArchiveStore`, rerun
coverage, then remove `tmp/` after processing. Asset-only `_files` folders and
blank browser `saved_resource.html` files are not source pages.

## Regeneration checklist

After parser/schema changes:

1. Run `python -m compileall -q endorsement_scraper scrapers tests`.
2. Run `python -m unittest discover -s tests -q`.
3. Run all configured scrapers with `--overwrite` when rebuilding the dataset;
   running only one assessor produces incomplete per-person histories. Use
   `--workers 1` for browser-backed retrieval.
4. Run `python -m endorsement_scraper.individuals --overwrite --keep-tmp`.
   Keep the existing `data/individuals` directory in place during this step;
   the merger can only preserve `last-updated` values when it can compare
   against the existing files. If a clean-room rebuild is unavoidable, restore
   timestamps from the previous snapshot for records whose content is
   unchanged before committing.
   The merger also refuses to write into an existing empty output directory;
   use `--allow-empty-output` only for an intentional clean-room rebuild.
5. Run `python -m unittest tests.test_individuals_coverage -v` and remove or
   quarantine stale profile-only files it identifies.
6. Validate all generated individual files through
   `endorsement_scraper.individuals._validate_individual` or the public schema
   helpers, and report record/profile counts.


