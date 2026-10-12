---
name: process-new-conference
description: Onboard a new security conference into this repository's assessor, archive, endorsement, enrichment, validation, statistics, and individual-profile pipeline. Use when the user names a conference that is not yet implemented, asks to retrieve its historical talks or speakers, or wants a new conference scraper and its generated records.
---

# Process a new conference

Use this skill when the user provides a conference name or website and expects
the repository to collect endorsements and produce individual records. Treat
the existing DEF CON implementation as the reference architecture, but verify
each new site's layouts and data sources instead of copying assumptions.

## Completion contract

Do not call a conference onboarded until all of these are true:

- An assessor file exists at `data/assessors/<id>.json` with stable metadata,
  `peerReview.rigorLevel`, `peerReview.reviewType`, and historical source URLs.
- Source pages are cached under `data/archives/html/<id>/` or an equivalent
  archive ZIP. Prefer local archives on reruns.
- Archive coverage passes for every configured `links.processUrls` entry, or
  missing pages are manually downloaded and inserted before parsing.
- A discovered adapter exists below `scrapers/` (or the collection adapter
  equivalent) and produces one validated endorsement per person.
- Every endorsement has a detailed non-empty `description`, canonical
  lowercase hyphenated `domains`, `evidence-links`, and a derived boolean
  `evidence` that is true exactly when links exist.
- Any useful external dataset has an enricher below `enrichers/`, with its own
  `data/enrichments/<enricher-id>/data.zip` dataset and matching logic.
- Every assessor with a YouTube channel or playlist has a corresponding
  non-empty `*-youtube-recordings` archive; `tests.test_video_enrichment_coverage`
  passes.
- `data/stats.json` reports a non-zero capture and evidence counts are known.
- The individual merger succeeds, profile biographies remain empty, profile
  stats match the final deduplicated endorsements (including unique assessor
  counts), and temporary directories are cleaned.

## Workflow

### 1. Identify and normalize the assessor

1. Research the official conference name, canonical website, stable URL, and
   identifier. Use lowercase hyphenated IDs such as `example-conference`.
2. Inspect `data/templates/endorsement.tpl` and `individual.tpl` before coding.
3. Create `data/assessors/<id>.json` with `id`, `name`, `url`, category,
   description, peer-review metadata, attribution, recognition, and a `links`
   object. Keep historical processing URLs in `links.processUrls`; never edit
   unrelated assessor fields while adding a source link.
4. Put official video, audio, slides, CSV, XLSX, API, or other evidence source
   URLs in `links` with descriptive names (for example `youtubeUrl`). Verify
   URLs rather than guessing them.

### 2. Discover the source inventory

Build a year/page inventory before writing a parser:

- Find every historical conference page, schedule, speaker list, talk detail,
  or proceedings endpoint.
- Record pagination links, archives, alternate layouts, and redirects.
- Determine whether a page contains abstracts, speaker bios, contact links,
  talk URLs, or only index data.
- Determine whether an external source (video channel, slides, papers,
  awards, CVE database) can independently validate an endorsement.

Use HTTP retrieval only when the local archive lacks the page. Save successful
responses and preserve a deterministic member path such as
`<conference-number>/speakers.html`. For ZIP-backed archives, use
`ArchiveStore`; keep the source layer byte-oriented so future CSV/XLSX readers
can be added without changing the scraper contract.

Run `python -m unittest tests.test_archive_coverage -v` before parsing. If a
site blocks automation, download the complete main HTML document into `tmp/`,
insert it into the assessor ZIP with `ArchiveStore`, rerun coverage, and then
remove `tmp/`. Asset-only `_files` folders and blank `saved_resource.html`
files are not source pages.

For Blue Team Con, the official historical inventory is the 2021–2025 set of
`btc-history/talks-blue-team-con-YYYY/` pages. Their ZIP members intentionally
match the URL paths exactly, which keeps archive coverage validation generic.
The pages expose talk titles and “Presented by” speaker names; linked detail
pages must also be archived before declaring the inventory complete. When Edge
is required, retrieve the queue sequentially: one bounded process, wait for
exit, then the next URL.

### 3. Implement the adapter

1. Add a module under `scrapers/`, splitting layout-specific parsing into
   focused functions. Use `BaseCollectionScraper` when one conference emits
   grouped per-year JSON; use page scrapers when pagination is naturally
   request-driven.
2. Keep historical, regional, and paginated URLs in the assessor JSON rather
   than hard-coding them in the parser. This keeps the adapter reusable as the
   number of assessors grows without limit.
3. Parse every speaker/talk pair. If one talk has multiple speakers, emit one
   endorsement per speaker and never copy one speaker's profile data to
   another.
4. Set `label` to the talk or recognition title, `subtitle` to the conference
   and year, `url` to the canonical source page, and `year` to a four-digit
   calendar year. Store the abstract or detailed source evidence in
   `description`; use a deterministic fallback only when the source has no
   abstract.
5. Pass description and relevant source text to domain detection. Outputs must
   use only these canonical values:
   `cloud-security`, `cyber-defense`, `devsecops`, `digital-forensics`, `grc`,
   `incident-response`, `open-source-intelligence`, `penetration-testing`,
   `red-teaming`, `reverse-engineering`, `vulnerability-research`, `unknown`.
6. Emit `PersonProfile` fragments only for contact information. Keep
   biographies empty; do not scrape or invent biographies.

### 4. Add enrichers

For every independent evidence source, create one stable enricher under
`enrichers/`. Enrichers must be independently discoverable and runnable:

```powershell
python -m endorsement_scraper.enrichment_cli --list
python -m endorsement_scraper.enrichment_cli --enricher <id> --overwrite
python -m endorsement_scraper.enrichment_cli --overwrite
```

Use `yt-dlp` for video channels when appropriate. Store a JSON array as
`data.json` inside `data/enrichments/<enricher-id>/data.zip`. Include stable
IDs, titles, URLs, conference/year hints, and any metadata needed for matching.
Implement matching that tolerates conference prefixes, speaker-name prefixes,
punctuation, subtitles, and meaningful title variants. Add a regression test
for every discovered mismatch.

When an assessor advertises `youtubeUrl`, `youtubePlaylistUrl`, or
`youtubePlaylistUrls`, add and run its YouTube enricher before parsing
endorsements. The coverage test must verify that the corresponding archive is
present and contains at least one record. Treat `archiveInventory.youtubeYears`
as a video source too. Run one video enricher at a time (`--workers 1`), record
the total catalog size and matched evidence-link count, and investigate a
large unmatched remainder with assessor-specific title normalization before
declaring onboarding complete.

### 5. Validate and generate

Run the complete scraper set with overwrite enabled, then merge profiles:

```powershell
python -m endorsement_scraper --overwrite --workers 1
python -m endorsement_scraper.individuals --overwrite --keep-tmp
python -m unittest tests.test_individuals_coverage -v
```

Inspect `data/stats.json`. Confirm pages and endorsements are non-zero, no
scraper failed, and evidence counts are plausible. Confirm every endorsement
has a boolean `evidence` consistent with `evidence-links` and that every link
has a title and absolute HTTP(S) URL.

Inspect at least one generated endorsement, one multi-speaker talk, one
enrichment match, and one individual profile. Verify profile `stats` contains:

- `endorsements`
- `with-evidence`
- `without-evidence`
- `assessors` (distinct assessor IDs represented)
- `by-domain` counts for every canonical domain, including `unknown`
- `by-subspecialty` counts grouped beneath each canonical domain

Never merge one assessor's temporary output into the final individuals
directory when multiple assessors are configured: that replaces complete
histories with partial histories. The zero-endorsement test also catches stale
profile-only files left by older runs.

Run tests and compilation checks before reporting completion:

```powershell
python -m unittest discover -s tests -p 'test_*.py' -q
python -m compileall -q endorsement_scraper scrapers enrichers tests
```

### 6. Add failure guards

Add tests for empty pages, malformed layouts, duplicate speakers, pagination,
missing abstracts, missing archives, evidence matching, and zero-result runs.
The stats contract must mark a run failed when a required assessor produces no
endorsements. Never silently accept an empty crawl as a successful onboarding.

Read [the repository architecture reference](../verified-endorsement-data/references/architecture.md)
for storage, schema, archive, enrichment, and merger details.

OffensiveCon is the reference for a mixed historical archive: older agenda
pages expose row-level speaker names without detail links, while newer speaker
index pages expose abstracts and linked detail pages. Keep both parsing paths
and allow unavailable detail pages to fall back to the agenda's descriptive
title without blocking the complete run.

Insomni'hack is a second archive pattern: the historical URLs can remain in
the assessor inventory even when the live site later redirects them. Never
cache the redirected current homepage as historical source data. Remove such
invalid cache entries, let `test_archive_coverage` identify the missing URLs,
and require manually saved historical HTML before generating endorsements.
