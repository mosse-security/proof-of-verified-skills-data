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
fields, and POV state. A talk title, affiliation, company, or session label is
not a person name.

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
