# Verified endorsement scrapers

This repository stores each assessor under `data/assessors/{assessor-id}/`,
including its metadata JSON, identity lists, and assessor-local `stats.json`, and
provides an extensible Python framework for collecting that assessor's
public endorsements: CVEs, conference talks, prizes, acknowledgements, and
other assessor-specific evidence.

The framework deliberately leaves HTML/API parsing to each site module. It
handles discovery, parallel execution, page traversal, retrying, optional raw
page snapshots, deterministic record IDs, atomic output, and reruns.

The repository's evolving operating knowledge is captured in
`skills/verified-endorsement-data/SKILL.md` and its architecture reference.
Update that skill when conventions, templates, domains, or scraper workflows
change.

## Quick start

The framework requires Python 3.11+. Install runtime dependencies from
`requirements.txt`:

```powershell
python -m pip install -r requirements.txt
python -m scrapers --list
python -m scrapers --workers 8
python -m scrapers --assessor black-hat --save-html
python -m scrapers --overwrite
python -m scrapers.enrichment_cli --overwrite
python -m unittest tests.test_archive_coverage -v
python -m unittest tests.test_video_enrichment_coverage -v
# Rebuild every assessor before merging individuals
python -m scrapers --overwrite --workers 1
python -m scrapers.individuals --overwrite --keep-tmp
python -m unittest tests.test_individuals_coverage -v
python -m unittest tests.test_individual_quality -v
python -m unittest tests.test_insomnihack_archives -v
```

Running `python -m scrapers` with no filters discovers and runs all
page scrapers and collection scrapers in one invocation. Use `--assessor`
or `--scraper` only when narrowing the run is intentional.

An editable install also exposes the `scrape-endorsements` command:

```powershell
python -m pip install -e .
scrape-endorsements --help
```

The generic `--list` command shows dynamically discovered `BaseScraper` and
`BaseCollectionScraper` plugins. Copy `scrapers/_template.py` to a filename
that does not begin with `_`, then fill in its parser and IDs. Collection
scrapers are useful when an assessor needs grouped output or controls its
own local cache.

Assessors are not enumerated in code. Add an assessor JSON file and a
discovered scraper module; the runner and merger accept any number of assessors
and run independent adapters concurrently.

## DEF CON speaker archive

The first collection scraper reads every URL in
`data/assessors/def-con.json` and produces one compact JSON array per
conference:

```text
tmp/endorsements/def-con/defcon-34.json
tmp/endorsements/def-con/defcon-33.json
...
```

Run it from the repository root:

```powershell
python -m scrapers
# or run only this scraper:
python -m scrapers --assessor def-con
# dedicated equivalent:
python -m scrapers.def_con
```

It reads `data/archives/html/def-con.zip` in memory first, with the equivalent
`data/archives/html/def-con/defcon-N/speakers.html` directory layout supported as
a fallback. A missing entry is downloaded from that conference's `processUrls`
entry and saved back to the selected archive before parsing. Conference files are processed in parallel. Existing JSON is
atomically overwritten by default, so reruns contain no duplicates or stale
records; pass `--no-overwrite` to preserve existing outputs. Speaker profile
fragments are written to `tmp/profiles/def-con/` for the later individual
merge.

Run the archive coverage check before parsing:

```powershell
python -m unittest tests.test_archive_coverage -v
```

The complete Blue Team Con retrieval includes 168 linked detail pages. When a
browser is needed, retrieve them conservatively: one bounded Edge process at a
time, wait for it to exit, and record failures for retry. Do not run parallel
Edge processes for this workload.

The check compares every assessor `links.processUrls` entry with the members
of `data/archives/html/<assessor-id>.zip` and prints each missing URL. This
makes manually downloaded pages easy to identify and add before a scrape run.

If a source blocks automated retrieval, save the complete main HTML page into
`tmp/` and insert it into the matching ZIP member with `ArchiveStore`; asset-only
`*_files` directories are not source pages. Remove `tmp/` after processing.

Each array item follows `data/templates/endorsement.tpl`. Assessor fields
are copied from `data/assessors/def-con.json`:

```json
{
  "name": "Alice Example",
  "label": "Breaking All The Things",
  "description": "A detailed abstract describing the talk and its security research.",
  "type": "presentation",
  "assessor": "DEF CON",
  "assessor-id": "def-con",
  "assessor-category": "conference_community",
  "reviewType": "community_review",
  "subtitle": "DEF CON 34",
  "url": "https://defcon.org/html/defcon-34/dc-34-speakers.html#content_42",
  "evidence-links": [],
  "evidence": false,
  "year": 2026,
  "domains": ["penetration-testing", "vulnerability-research"]
}
```

## Black Hat briefing archive

The Black Hat collection scraper reads USA, Europe, Abu Dhabi, and MEA URLs
from `data/assessors/black-hat.json`. It handles legacy briefing pages and
modern schedule pages, writing one JSON array per event under
`tmp/endorsements/black-hat/`:

```powershell
python -m scrapers --assessor black-hat --overwrite
```

The same local-first ZIP, coverage test, merger, and temporary-output cleanup
rules apply to every future assessor.

### Video enrichments

Independent video sources are collected by discovered enrichers and stored as
local ZIP datasets under `data/enrichments/<enricher-id>/data.zip`. YouTube
channels and playlists are configured in each assessor's `links` object using
`youtubeUrl`, `youtubePlaylistUrl`, or `youtubePlaylistUrls`; BlueHat, for
example, uses multiple playlists. Run all enrichers, or one selected enricher:

```powershell
python -m scrapers.enrichment_cli --list
python -m scrapers.enrichment_cli --overwrite
python -m scrapers.enrichment_cli --enricher bluehat-youtube-recordings --overwrite
```

The endorsement builders load these datasets and add matched recordings to
`evidence-links`. The video-enrichment coverage test fails when an assessor
declares a video source without a non-empty matching archive, preventing a
conference from silently missing its recordings.

Parser capture is local-first: it reads archived conference pages from
`data/archives/html` and existing enrichment archives. `enrichment_cli` is an
optional external refresh using `yt-dlp`; network failure there is not a
parser-capture failure and must not replace usable local data.

## Microsoft BlueHat archive

Microsoft BlueHat is inventoried in `data/assessors/bluehat.json`, including
the official MSRC schedule posts from v9 through v18, BlueHat Seattle 2019,
BlueHat 2023, and BlueHat 2024. The adapter handles both legacy HTML schedule
tables and newer session-heading posts. Pages are cached in
`data/archives/html/bluehat.zip` and parsed with:

```powershell
python -m scrapers --assessor bluehat --overwrite
```

## CanSecWest presentation archive

CanSecWest is inventoried in `data/assessors/cansecwest.json`. The official
archive currently exposes 2020, 2021, 2022, 2023, 2024, and 2025 pages; the
legacy `cansecwest.com` links are retained as research notes where the old
URLs now return 404. Source pages are cached in
`data/archives/html/cansecwest.zip` and parsed by the discovered
`cansecwest-presentations` collection scraper:

```powershell
python -m scrapers --assessor cansecwest --overwrite
```

## Blue Team Con archive

Blue Team Con is inventoried for its official 2021â€“2025 historical talks
pages in `data/assessors/blue-team-con.json`. The five pages are cached in
`data/archives/html/blue-team-con.zip` and parsed by the discovered
`blue-team-con-talks` collection scraper. Each presented speaker becomes an
endorsement; the linked talk page is retained as evidence and the parser is
safe to rerun:

```powershell
python -m scrapers --assessor blue-team-con --overwrite
```

Archive coverage tests also enumerate every `/directory/` talk link exposed by
those indexes and fail until each linked detail page has been cached:

```powershell
python -m unittest tests.test_archive_coverage -v
```

## OffensiveCon archive

OffensiveCon is inventoried from the official 2018, 2019, 2020, 2022, 2023,
2024, 2025, and 2026 agenda/speaker pages. Its local source archive is
`data/archives/html/offensivecon.zip`; linked talk pages are cached as they
are discovered. The parser handles both agenda rows and speaker-card pages,
and the YouTube enricher stores recordings in
`data/enrichments/offensivecon-youtube-recordings/data.zip`:

```powershell
python -m scrapers.enrichment_cli --enricher offensivecon-youtube-recordings --overwrite
python -m scrapers --assessor offensivecon --overwrite
```

## Insomni'hack archive

Insomni'hack is inventoried for published talk pages from 2013â€“2020 and
2022â€“2026. The live site currently redirects those historical paths to its
2027 site, so the archive must be populated from manually saved historical
HTML (the coverage test reports every missing URL) before parsing. Once pages
are inserted into `data/archives/html/insomnihack.zip`, run:

```powershell
python -m unittest tests.test_archive_coverage -v
python -m scrapers --assessor insomnihack --overwrite
python -m scrapers.enrichment_cli --enricher insomnihack-youtube-recordings --overwrite
```

The Insomni'hack YouTube enrichment archive is ready at
`data/enrichments/insomnihack-youtube-recordings/data.zip` and contains 215
recordings. The parser supports the historical schedule/table and talk-section
layouts, including multi-speaker sessions and abstracts.

## Cyber-domain mapping

Every endorsement record must contain a non-empty `domains` array and a
`subspecialties` object keyed exactly by those domains. The core library
detects zero, one, or several values from this taxonomy:

- `cloud-security`
- `cyber-defense`
- `devsecops`
- `digital-forensics`
- `grc`
- `incident-response`
- `open-source-intelligence`
- `penetration-testing`
- `red-teaming`
- `reverse-engineering`
- `vulnerability-research`
- `identity-and-access-management`
- `iot-security`
- `operational-technology-security`
- `threat-hunting`
- `cybercrime-and-fraud`

When no rule matches, the array is `["unknown"]` and its subspecialties array
is empty. Specialty identifiers are lowercase and hyphenated, for example:

```json
"domains": ["penetration-testing"],
"subspecialties": {
  "penetration-testing": ["web-application-penetration-testing"]
}
```

Standard `Endorsement`
objects are mapped automatically from their type, label, person, description,
and details. Every endorsement must include a non-empty `description`, which
should contain the source abstract or other detailed evidence. Site parsers
should also pass that text to `detect_domains` so classification can use it.
A scraper may pass explicit domains, but unsupported values fail
validation. Collection scrapers report every generated JSON file to the core
runner, which validates every record and fails that scraper if domains or
subspecialties are missing, unsupported, duplicated, or out of canonical order.

The taxonomy, detection rules, normalization, and validators live in
`scrapers/domains.py` so site scrapers cannot silently introduce
their own incompatible domain names.

Clearly non-endorsement conference sessions (such as long-form panels,
orientation sessions, ceremonies, comedy, career, and community events) are
filtered centrally by the runners when they would otherwise be classified only
as `unknown`. Short or missing abstracts are retained as `unknown` because the
source does not provide enough evidence to decide whether the session should
be removed.

The taxonomy includes cross-cutting specialty families for AI security,
automotive security, privacy engineering, telecommunications and radio
security, mobile platform security, medical-device and drone security, and
cybercrime/fraud investigations. `cybercrime-and-fraud` is the only newly added
top-level domain; AI and automotive remain specialties that can map to more
than one operational domain.

## Adding scrapers

Every `.py` file below `scrapers/` is discovered recursively, except files
whose names begin with `_`. A file may define one or many concrete
`BaseScraper` subclasses, and one assessor may have any number of scraper
classes. `scraper_id` must be globally unique.

```python
from scrapers import BaseScraper, Endorsement, PageResult, PersonProfile, Request


class ConferenceArchive(BaseScraper):
    assessor_id = "example-conference"
    scraper_id = "example-conference-talks"

    def start_requests(self):
        # Seed as many independent archive/year pages as needed.
        for year in range(2010, 2027):
            yield Request(
                f"https://conference.example/events/{year}",
                meta={"year": year},
            )

    def parse(self, response, request):
        talks, next_url = parse_site_html(response.text)  # site-specific
        items = [
            Endorsement(
                assessor_id=self.assessor_id,
                kind="conference_presentation",
                title=talk.title,
                description=talk.abstract,
                recipient=talk.speaker,
                year=request.meta["year"],
                subtitle=f"Example Conference {request.meta['year']}",
                external_id=talk.id,
                source_url=response.url,
                details={"abstract": talk.abstract},
            )
            for talk in talks
        ]
        follow = [Request(next_url, meta=request.meta)] if next_url else []
        return PageResult.build(items, follow)
```

`start_requests()` supports multi-year archives and multiple endpoints.
`PageResult.follow` supports next-page links, cursor APIs, and other
pagination. Requests are fingerprinted, so a site that links back to an
already visited page does not create an infinite loop. The default limit is
1,000 fetched pages per scraper; use `--max-pages 0` only when an unlimited
crawl is intentional.

When a page also exposes a speaker's profile, return a `PersonProfile` in the
page result alongside the endorsement. The runner stores these fragments under
`tmp/profiles/<assessor>/<scraper>/`; the individual merger combines them
later:

```python
return PageResult.build(
    endorsements,
    follow,
    profiles=[PersonProfile("Alice Example", "", contacts)],
)
```

The standard library is enough for JSON APIs and simple HTML. Individual
scrapers may add and document dependencies such as Beautiful Soup when a site
needs them.

## Output and deduplication

Each endorsement is saved as:

```text
tmp/endorsements/<assessor-id>/<deterministic-id>.json
```

When `external_id` exists, the ID is derived from assessor, endorsement
type, and external ID. Otherwise it is derived from the normalized content.
That makes reruns idempotent across scraper classes and processes:

- Default: an existing record is skipped.
- `--overwrite`: an existing record is atomically rewritten with current
  parsed data.

Overwrite does not delete old records that are absent from the latest crawl.
That conservative behavior prevents a temporarily incomplete website response
from erasing historical data.

Example record:

```json
{
  "name": "Researcher Name",
  "label": "CVE-2026-1234",
  "type": "cve",
  "assessor": "MITRE CVE",
  "assessor-id": "mitre-cve",
  "assessor-category": "vulnerability_database",
  "reviewType": "triage_review",
  "url": "https://example.test/CVE-2026-1234",
  "evidence-links": [],
  "evidence": false,
  "year": 2026,
  "domains": ["vulnerability-research"]
}
```

`subtitle` is the only optional template field; `evidence-links` and `evidence`
are required. `evidence` must be true exactly when `evidence-links` is non-empty.
The core rejects missing,
extra, malformed, or assessor-mismatched fields before accepting scraper
output. The deterministic hash remains in the filename rather than the JSON
record.

## Individual profiles

The pipeline has three explicit stages:

```powershell
python -m scrapers                 # scrape and rebuild assessor-local files
python -m scrapers.enrichment_cli  # enrich assessor-local files
python -m scrapers.individuals     # clean-rebuild canonical files
```

The scraper stage applies each assessor's whitelist/blacklist gate and rebuilds
only that assessor's approved snapshot. The output is stored locally at
`data/assessors/{assessor-id}/individuals/*.json`; it is generated, gitignored,
and intentionally does not contain `last-updated` because it duplicates the
canonical records:

```text
data/assessors/insomnihack/individuals/alice-example.json
data/individuals/alice-example.json
```

```json
{
  "name": "Alice Example",
  "biography": "",
  "contact": [],
  "stats": {
    "endorsements": 0,
    "assessors": 0,
    "with-evidence": 0,
    "without-evidence": 0,
    "by-domain": {}
  },
  "endorsements": []
}
```

The enrichment stage updates those assessor-local JSON files in place. The final
merge reads only the assessor-local snapshots: it first removes all generated
content under `data/individuals/`, then rebuilds that directory from every
`data/assessors/*/individuals/*.json`. It does not read raw scrape staging or
reapply assessor decisions. Raw endorsement and profile staging is persistent
under `tmp/endorsements/` and `tmp/profiles/`; it is not
stored in `data/tmp`.

Each individual also includes deterministic `stats`: total endorsements,
the number of unique assessors represented, counts with and without evidence,
and an endorsement count for every cyber domain (including `unknown`).

Every merge is a clean rebuild. Existing assessor-local and canonical
individual JSON files are deleted before the approved records are written, so
removed or newly blacklisted names cannot survive from an earlier run.

Archive pages are also page-owned. Every configured non-Insomnihack archive URL
has a standalone parser at
`scrapers/assessors/{assessor-id}/page-{number}-{page-id}.py`; Insomnihack keeps
its edition-owned parser files in the same location. Each page parser declares
its source URL and exposes `parse_page`, and
`tests/test_page_parser_coverage.py` fails when a configured archive page has
no dedicated parser.

### Individual-name quality checks

The merger centrally rejects title-shaped names, reversed schedule rows,
affiliation blocks, prose fragments, and obvious session labels. After changing
a parser, regenerate its outputs and rebuild profiles; do not hand-edit generated
JSON. Run `tests.test_individuals_coverage` and `tests.test_individual_quality`
before publishing. The manually vetted global whitelist is stored in
`data/individuals-enumeration.txt` and must contain no duplicate names. Rejected names remain assessor-local in
`individuals-blacklist.txt`, and every other encountered name is recorded once in
`individuals-not-validated.txt` on each run. Only globally whitelisted names are
written to assessor-local individual or endorsement output; unknown and blacklisted names
are excluded.
The whitelist is UTF-8 data: preserve Unicode names exactly, and use an editor or
an explicitly UTF-8 writer when updating it. Do not round-trip it through
PowerShell `Get-Content`/`WriteAllLines` defaults. The registry rejects likely
mojibake and duplicate normalized names before a scrape can write records.
Individual `last-updated` values are preserved across clean rebuilds when the
complete individual document is deeply unchanged apart from that field. They
change only when an endorsement, enrichment, contact/profile data, or other
persisted content changes.
This includes short schedule titles such as `A girl`, `A SysCall to ARMs`, and
`Ansible`; their associated people remain under their speaker names with the
talk title stored in the endorsement label.
Insomni'hack archives are validated one-by-one from the local archive so a
parser change for one historical layout cannot silently pass for another.
Each configured Insomni'hack archive page has its own parser module under
`scrapers/assessors/insomnihack/`; the runner refuses to process a
page without a registered page parser.

As a safety check, the merger refuses to rebuild into an existing empty
`data/individuals` directory, since that would make every record look new and
reset its timestamp. Use `--allow-empty-output` only when a clean-room rebuild
is intentional and timestamp preservation is not possible.

## Enrichers

Enrichers are independently discovered recursively from `scrapers/enrichers/` and collect external
datasets for later endorsement enrichment. Run all enrichers, or select one:

```powershell
python -m scrapers.enrichment_cli --overwrite
python -m scrapers.enrichment_cli --enricher def-con-youtube-recordings --overwrite
```

The DEF CON YouTube enricher reads `links.youtubeUrl` from the assessor JSON,
uses `yt-dlp`, and stores its JSON video index in
`data/enrichments/def-con-youtube-recordings/data.zip`. Matching videos appear
in endorsement records as `evidence-links` entries containing a title and URL;
the companion `evidence` flag is set automatically. Future enrichers should write a JSON array as `data.json` in their own
`<enricher-id>/data.zip` archive.

Conference-specific enricher modules live under `scrapers/enrichers/conferences/`.
Recursive discovery keeps their stable enricher IDs and CLI commands unchanged.

## Run statistics

Every scraper run writes the global `data/stats.json` and the corresponding
`data/assessors/{assessor-id}/stats.json` with run state. The global file stores
the UTC run timestamp, duration,
per-scraper page and endorsement counts, totals, errors, and sanity checks.
It also reports how many endorsements have evidence links versus no evidence
links, plus endorsement counts grouped by every canonical cyber domain and by
each detected subspecialty within that domain (`totals.by-domain` and
`totals.by-subspecialty`).
Use `--stats-file` to choose another location. The DEF CON sanity check marks a
run failed when zero endorsements are produced, making accidental empty crawls
visible to operators and automated tests.

## HTML snapshots

To archive all configured historical pages for an assessor:

```powershell
python -m scrapers.archive_cli --assessor black-hat
```

The command stores pages in `data/archives/html/<assessor>.zip`, skips existing
members on reruns, and retries failed requests. Add `--overwrite` to refresh
the archive.

`--save-html` writes every successful response plus metadata to the configured
HTML archive. The archive can be either a directory:

```text
data/archives/html/<assessor-id>/<scraper-id>/<request-hash>.html
data/archives/html/<assessor-id>/<scraper-id>/<request-hash>.json
```

or a ZIP file with the same paths as member names, such as
`data/archives/html/def-con.zip`. ZIP entries are read directly without
extraction. The archive interface is byte-oriented so future CSV/XLSX source
readers can be added without changing scraper storage or caching behavior.

The request hash is stable, so a rerun refreshes the same snapshot rather than
creating unbounded copies. Curated source caches may also be kept in
`data/archives/html/`, such as the year-specific DEF CON pages. Change the runtime
snapshot location with `--html-dir` when those responses should live elsewhere.

## Operational notes

- Scraper classes run concurrently; pages inside a scraper run in queue order.
- One failed scraper is reported without stopping independent scrapers.
- Use `--delay`, a descriptive `--user-agent`, and assessor filters to
  keep crawls polite.
- Site-specific scrapers remain responsible for applicable terms, robots
  directives, authentication, and parsing correctness.
- `python -m unittest discover -s tests -v` runs the framework tests without
  accessing the network.

### Assessor scope

Conference recommendations and next-target decisions must use only the
shortlisted assessor inventory under `data/assessors/*.json`. Do not propose a
conference found outside that local list, including one discovered through web
search or general research. A new conference becomes eligible only after its
assessor JSON is deliberately added to the inventory.

## YouTube transcript archives

For conferences with a YouTube enrichment archive, capture English subtitles
for videos that are actually linked from endorsements:

```powershell
python -m scrapers.transcripts --assessor def-con --matched-only
```

Archives are written to `data/archives/yt-transcripts/<assessor>-transcripts.zip`.
Each archive contains `transcripts/<video-id>.txt` and a `manifest.json` with
the catalog URL, title, and capture status. Runs are resumable and idempotent:
existing video IDs are skipped, checkpoints are written every ten records, and
the manifest is merged rather than replaced on later runs. Use repeated
`--video-id` options to retry a small set of gaps without scanning the full
catalog. Run one conference at a time to avoid YouTube throttling and archive
file contention.

The transcript coverage tests cross-reference endorsement evidence-link video
IDs with transcript members and report missing IDs. Failed or unavailable
subtitle records remain in the manifest and are not treated as successful
captures. Runtime logs are written to ignored `logs/general.log`,
`logs/warnings.log`, and `logs/errors.log`; warnings include missing subtitles
and unmatched conference videos.


