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

## Stats

Individual stats are derived from the final deduplicated endorsements. They
include endorsement count, distinct assessor count, evidence counts, and counts
for every allowed domain. Do not hand-edit generated JSON.
