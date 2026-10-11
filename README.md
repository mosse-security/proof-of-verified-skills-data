# Verified endorsement scrapers

This repository stores one assessor per file in `data/assessors` and
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
python -m endorsement_scraper --list
python -m endorsement_scraper --workers 8
python -m endorsement_scraper --assessor black-hat --save-html
python -m endorsement_scraper --overwrite
```

Running `python -m endorsement_scraper` with no filters discovers and runs all
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

## DEF CON speaker archive

The first collection scraper reads every URL in
`data/assessors/def-con.json` and produces one compact JSON array per
conference:

```text
data/tmp/endorsements/def-con/defcon-34.json
data/tmp/endorsements/def-con/defcon-33.json
...
```

Run it from the repository root:

```powershell
python -m endorsement_scraper
# or run only this scraper:
python -m endorsement_scraper --assessor def-con
# dedicated equivalent:
python -m scrapers.def_con
```

It reads `data/archives/html/def-con.zip` in memory first, with the equivalent
`data/archives/html/def-con/defcon-N/speakers.html` directory layout supported as
a fallback. A missing entry is downloaded from that conference's `processUrls`
entry and saved back to the selected archive before parsing. Conference files are processed in parallel. Existing JSON is
atomically overwritten by default, so reruns contain no duplicates or stale
records; pass `--no-overwrite` to preserve existing outputs. Speaker profile
fragments are written to `data/tmp/profiles/def-con/` for the later individual
merge.

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
  "additional-links": [],
  "year": 2026,
  "domains": ["penetration testing", "vulnerability research"]
}
```

## Cyber-domain mapping

Every endorsement record must contain a non-empty `domains` array. The core
library detects zero, one, or several values from this fixed taxonomy:

- `cloud security`
- `cyber defense`
- `devsecops`
- `digital forensics`
- `GRC`
- `incident response`
- `open source intelligence`
- `penetration testing`
- `red teaming`
- `reverse engineering`
- `vulnerability research`

When no rule matches, the array is `["unknown"]`. Standard `Endorsement`
objects are mapped automatically from their type, label, person, description,
and details. Every endorsement must include a non-empty `description`, which
should contain the source abstract or other detailed evidence. Site parsers
should also pass that text to `detect_domains` so classification can use it.
A scraper may pass explicit domains, but unsupported values fail
validation. Collection scrapers report every generated JSON file to the core
runner, which validates every record and fails that scraper if `domains` is
missing, empty, unsupported, duplicated, or out of canonical order.

The taxonomy, detection rules, normalization, and validators live in
`endorsement_scraper/domains.py` so site scrapers cannot silently introduce
their own incompatible domain names.

## Adding scrapers

Every `.py` file below `scrapers/` is discovered recursively, except files
whose names begin with `_`. A file may define one or many concrete
`BaseScraper` subclasses, and one assessor may have any number of scraper
classes. `scraper_id` must be globally unique.

```python
from endorsement_scraper import BaseScraper, Endorsement, PageResult, PersonProfile, Request


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
`data/tmp/profiles/<assessor>/<scraper>/`; the individual merger combines them
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
data/tmp/endorsements/<assessor-id>/<deterministic-id>.json
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
  "additional-links": [],
  "year": 2026,
  "domains": ["vulnerability research"]
}
```

`subtitle` is the only optional template field; `additional-links` is required
but may be empty. The core rejects missing,
extra, malformed, or assessor-mismatched fields before accepting scraper
output. The deterministic hash remains in the filename rather than the JSON
record.

## Individual profiles

After collecting endorsements, merge them into the `individual.tpl` shape:

```powershell
python -m endorsement_scraper.individuals
# or, after installing the package:
merge-individuals
```

The merger reads every JSON file below `data/tmp/endorsements`, groups records by
case-insensitive person name, removes duplicate endorsement objects, and sorts
each person's endorsements deterministically. It writes one file per person
to `data/individuals`, for example `data/individuals/alice-example.json`:

```json
{
  "name": "Alice Example",
  "last-updated": "2026-01-01T00:00:00Z",
  "biography": "",
  "contact": [],
  "endorsements": []
}
```

It also reads profile fragments from `data/tmp/profiles` (or `--profiles-dir`),
keeping biography empty for now and combining the union of discovered contact
links. AI-generated biography summaries will be added in a later step. This
keeps source-specific profile extraction separate from the canonical
endorsement records. The temporary endorsement and profile directories are
emptied after every merger run, including failed runs; pass `--keep-tmp` when
you need to inspect them.

Existing individual files are replaced on rerun so the result cannot accumulate
duplicates. The merger compares the content before writing: unchanged records
retain their existing `last-updated` UTC timestamp, while changed records get a
new timestamp suitable for ascending or descending database sorting. Use
`--no-overwrite` to preserve existing profile files.

## Enrichers

Enrichers are independently discovered from `enrichers/` and collect external
datasets for later endorsement enrichment. Run all enrichers, or select one:

```powershell
python -m endorsement_scraper.enrichment_cli --overwrite
python -m endorsement_scraper.enrichment_cli --enricher def-con-youtube-recordings --overwrite
```

The DEF CON YouTube enricher reads `links.youtubeUrl` from the assessor JSON,
uses `yt-dlp`, and stores its JSON video index in
`data/enrichments/def-con-youtube-recordings/data.zip`. Matching videos appear
in endorsement records as `additional-links` entries containing a title and
URL. Future enrichers should write a JSON array as `data.json` in their own
`<enricher-id>/data.zip` archive.

## Run statistics

Every scraper run writes `data/stats.json` with the UTC run timestamp, duration,
per-scraper page and endorsement counts, totals, errors, and sanity checks.
Use `--stats-file` to choose another location. The DEF CON sanity check marks a
run failed when zero endorsements are produced, making accidental empty crawls
visible to operators and automated tests.

## HTML snapshots

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

