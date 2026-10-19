# Architecture

The system has three data stages:

```text
archived pages + local enrichment data
          │
          ▼
tmp/endorsements + tmp/profiles
          │  whitelist/blacklist gate
          ▼
data/assessors/<id>/individuals/*.json
          │  clean canonical merge
          ▼
data/individuals/*.json
```

## Storage layout

- `data/assessors/<id>/<id>.json` — assessor metadata and archive inventory.
- `data/archives/html/` — source HTML archives, preferably ZIPs.
- `data/assessors/<id>/individuals/` — generated, Git-ignored local snapshots.
- `data/individuals/` — canonical individual records committed to the repo.
- `data/enrichments/<id>/data.zip` — local enrichment datasets.
- `data/individuals-enumeration.txt` — global UTF-8 whitelist.
- `data/assessors/<id>/parsing-errors.txt` — assessor-local parsing-error review list.
- `data/assessors/<id>/individuals-not-validated.txt` — assessor-local review queue.
- `tmp/` — transient capture and profile data.

## Ownership rules

Scrapers own source capture and endorsement construction. Identity validation
owns whether a name may be persisted. The assessor-local snapshot stage owns
whitelisted assessor results. The canonical merger owns cross-assessor grouping
and the final committed records.

The canonical merger always clears `data/individuals` before rebuilding it, so
removed or revoked assessor records cannot survive accidentally.

Assessor-local records intentionally omit `last-updated`; they are disposable
duplicates. Canonical records retain `last-updated`, preserving it when the
complete record is deeply unchanged and refreshing it when persisted content
changes.
