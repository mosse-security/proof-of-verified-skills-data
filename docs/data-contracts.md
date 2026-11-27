# Data contracts

## Assessor geography

Each `data/assessors/<id>/<id>.json` has a `countries` array. For in-person
conferences, list the countries in which the event has been held; for global
online or international programs, use `["Worldwide"]`. Use full English country
names, with `"United States"` and `"United Kingdom"` rather than abbreviations.
Place the primary or most representative location first; the website displays
it before the other entries. Country lists record known locations and may need
updating as events move or additional historical locations are verified.
Use `[]` when coverage is not yet established; it does not mean worldwide. Do
not combine `"Worldwide"` with country names. The field describes the assessor,
not the location or nationality of an individual or a particular endorsement.
For examples of source material, see the [ACM CCS event history](https://www.sigsac.org/ccs/ccs-history.html),
the [HITB conference archive](https://conference.hitb.org/), and the
[National Cyber League eligibility rules](https://nationalcyberleague.org/competition/rules).

An endorsement has a `location` string identifying its specific event's country,
`"Worldwide"` for a global program, or `"Unknown"` when not established. Legacy
records without the field are treated as unknown. It is independent of the assessor's broader `countries`
array: a multi-country conference does not put every record in every country.
The website's country search uses endorsement `location`; the domain filter
counts matching records from that location and domain. `Worldwide` is a
separate category, not a match for every country. These matches do not identify
where a person lives. The website also supports a future explicitly recorded individual
`countries` array; adding that field to canonical individual records requires a
separate change to their data contract and collection pipeline.

`scrapers/locations.py` contains the conservative event rules used by the
endorsement builder. Run `python -m scripts.backfill_endorsement_locations` for
a dry run, then add `--apply` to update canonical individuals and existing
assessor-local snapshots. The backfill preserves known locations, can upgrade
`"Unknown"` when new evidence is added, validates
changed endorsements, refreshes changed canonical timestamps, and is safe to
rerun after interruption. Unmatched events remain unset. Verify event editions
before expanding the rules; the event's assessor may operate in many countries.
For example, Black Hat Europe [2015 was in the Netherlands](https://blackhat.com/archive/europe/2015/resources.html),
while [2024 was in the United Kingdom](https://blackhat.com/archive/europe/2024/).

## Canonical individual

Each `data/individuals/*.json` contains exactly:

```json
{
  "name": "Alice Example",
  "last-updated": "2026-01-01T00:00:00Z",
  "biography": "",
  "contact": [],
  "stats": {},
  "endorsements": []
}
```

`last-updated` is an ISO-8601 UTC timestamp. It is preserved across clean
rebuilds only when every other field is deeply equal. Endorsement additions or
changes, enrichment changes, contact changes, and other persisted changes
refresh it.

## Assessor-local individual

Files under `data/assessors/<id>/individuals/` contain the same individual
content but omit `last-updated`. They are generated merge inputs, ignored by
Git, and must never be treated as the canonical public output.

## Endorsements

Endorsements are template-shaped records. They require a person name, label,
description, type, assessor metadata, source URL, year, domains, evidence
links, and a `povs-taxonomy` object. A talk title, affiliation, company, or session label is
not a person name.

The schema stores one evidence band and four independent properties. For example,
a presentation with a recording can carry this object:

```json
{
  "povs-taxonomy": {
    "evidence": "observable",
    "trusted": "unknown",
    "production": "unknown",
    "competition": false,
    "verifiable": true,
    "explanation": "The linked recording lets a reader review the presentation."
  }
}
```

The allowed bands are `indirect`, `observable` and `independently-reviewed`.
Property values are JSON booleans or the string `"unknown"`. The source
`url` identifies the issuing record. In `evidence-links`, use a descriptive
title and a direct URL for the work. The classifier recognises common video,
paper and repository URLs and artifact labels such as `Paper`, `Recording`
and `Source code`. Links to the work establish an observable floor and set
`verifiable` to true. A leaderboard or acknowledgement can establish credit
while leaving the work unavailable. See the [band definitions](../README.md#evidence-bands).

CVE endorsements use the existing `subtitle` field to show the published CVSS
severity, base score, and version. The endorsement `description` is the CVE
record's published vulnerability description.

CVE collection staging is partitioned by year. Each completed historical
yearly JSON collection is compressed as a durable ZIP under
`data/archives/cve/` after assessor-local individual files are built. The
current year remains as temporary JSON for refreshes. Individual JSON records
remain uncompressed for the normal merge pipeline.

## Stats

Individual stats are derived from the final deduplicated endorsements. They
include endorsement count, distinct assessor count, evidence counts, and counts
for every allowed domain. Do not hand-edit generated JSON.
