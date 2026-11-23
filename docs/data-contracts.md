# Data contracts

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
