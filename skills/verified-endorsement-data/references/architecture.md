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
  `{name, biography, contact, endorsements}`.
- The individual merger clears `data/tmp/endorsements` and
  `data/tmp/profiles` after a successful run; use `--keep-tmp` for debugging.
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

## DEF CON lessons

`endorsement_scraper/assessors/def_con.py` supports multiple historical
HTML layouts. Modern pages use `.talk`, `.speaker`, `.speaker-bio`/
`.speakerBio`, and empty abstract markers whose description is in following
siblings. DEF CON 18–21 use `h2.title`/`h4.byLine`; their speaker bios may be
`span.speakerBio`. Older layouts require dedicated parsers. Keep each layout
isolated and add a fixture test when changing it.

DEF CON output uses `type: presentation`, subtitle `DEF CON N`, and calendar
year `1992 + N` (DEF CON Safe Mode is conference 28). The source URL should
include the talk fragment when one exists.

## Regeneration checklist

After parser/schema changes:

1. Run `python -m compileall -q endorsement_scraper scrapers tests`.
2. Run `python -m unittest discover -s tests -q`.
3. Run the affected scraper with `--overwrite` and inspect counts/errors.
4. Run `python -m endorsement_scraper.individuals --overwrite`.
5. Validate all generated individual files through
   `endorsement_scraper.individuals._validate_individual` or the public schema
   helpers, and report record/profile counts.


