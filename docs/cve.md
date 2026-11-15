# CVE data pipeline

This page is the durable memory for the CVE integration. It describes where the
source data lives, how names are approved, and how CVE evidence becomes the
individual JSON records.

## Source

The source is the `CVEProject/cvelistV5` Git repository, linked as the
`external/cvelistV5` submodule. The source JSON is never copied into this
repository as loose files. Only one year should normally be checked out at a
time with sparse checkout. The current working year is disposable; durable
processed output is stored under `data/archives/cve/`.

The project currently processes years 1999 through 2025. 2026 is deliberately
excluded until it is explicitly requested.

## Name decisions

`data/individuals-enumeration.txt` is the global, manually reviewed whitelist.
It is an allowlist, not a request to create an empty individual record. A name
is persisted only when it is both whitelisted and actually found in a CVE
record.

Names found by parsing but not yet approved are written to
`data/assessors/mitre/individuals-not-validated.txt`. Obvious non-person or
malformed values go to `data/assessors/mitre/parsing-errors.txt`. After manual
review, approved names are added to the global whitelist and the affected years
must be rerun because the whitelist signature invalidates their processing
ledgers.

The CVE parser searches contributor-oriented fields such as credits, authors,
finders, reporters, researchers, submitters, and contacts. It also checks the
whole JSON document for exact matches to already-whitelisted names. It does not
turn every whitelist entry into a CVE record.

## Evidence records

Each accepted match becomes an endorsement with:

- `assessor-id`: `mitre`
- `label`: the CVE identifier
- `description`: the CVE description
- `subtitle`: CVSS severity and score when available
- `endorsement-type`: `vulnerability_discovery`
- `year`: the CVE year
- `evidence-links`: the CVE record URL
- all four POV values set to true under the MITRE assessor policy

The existing schema is used; no CVE-specific fields are introduced.

## Output layers

1. `tmp/endorsements/mitre/cve-records-YYYY.json` is temporary yearly staging.
2. `data/archives/cve/cve-records-YYYY.zip` is the durable compressed yearly
   collection for historical years.
3. `data/assessors/mitre/individuals/*.json` is a generated assessor-local
   snapshot and is Git-ignored.
4. `data/individuals/*.json` is the canonical committed output. The canonical
   merge combines all assessor-local snapshots and creates or updates one file
   per individual.

The CVE archive contains source-derived endorsement records, not raw CVE
repository files. The raw repository can therefore be removed after a run and
rechecked out later when another year needs processing.

## Historical memory

When resuming this work, read this page together with:

- [`cve-operations.md`](cve-operations.md) for commands and recovery;
- [`identity-and-quality.md`](identity-and-quality.md) for name decisions;
- [`data-contracts.md`](data-contracts.md) for JSON validation;
- [`architecture.md`](architecture.md) for the general merge model.

The most important invariant is: source CVE files stay outside the repository
working tree except for the one sparse year being processed; processed years
are represented by ZIP archives, and canonical individual files are produced
only by the canonical merge.
