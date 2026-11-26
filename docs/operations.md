# Usage and operations

## Standard run

Run capture, then merge:

```powershell
python -m scrapers --overwrite --workers 1
python -m scrapers.individuals --assessors-dir data/assessors --output-dir data/individuals
```

The capture command rebuilds each successful assessor's local snapshot. The
merge command deletes and rebuilds `data/individuals` from those snapshots.
Assessor-local JSON is generated output and is ignored by Git.

Run one assessor with `--assessor <id>`. Repeat the option to select several.
Use `--workers 1` when debugging deterministic archive behavior; higher values
are safe for independent archive pages when execution time matters.

## Review outputs

- `data/stats.json` — most recent capture status and counts.
- `data/assessors/<id>/stats.json` — assessor-specific capture state.
- `data/assessors/<id>/individuals/` — local generated snapshots.
- `data/individuals/` — canonical committed records.
- `data/assessors/<id>/individuals-not-validated.txt` — names awaiting review.
- `data/assessors/<id>/parsing-errors.txt` — assessor-local names rejected as parsing errors.

Before publishing, inspect parser errors, unknown names, and the generated
canonical records. Video-audit warnings are coverage diagnostics; they do not
mean local page capture failed.

## Optional enrichment

External video collection is separate from page capture:

```powershell
python -m scrapers.enrichment_cli --list
python -m scrapers.enrichment_cli --enricher <id> --overwrite
python -m scrapers.enrichment_cli --overwrite
```

If network access is unavailable, retain and use existing local enrichment
archives. Do not treat a failed external refresh as a parser failure.

## Temporary data

Use `tmp/` for transient endorsement, profile, and debugging output. It is
ignored by Git. Do not use `.endorsements` or `.profiles` in the repository
root.

## Public contact discovery

The helper searches public web results for LinkedIn, X, and personal websites.
Copy `.env.example` to `.env` and add `SERPER_API_KEY`. The `.env` file is
ignored by Git; never commit it. Existing Google Custom Search JSON API users
can instead provide `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ID`.

Run a small test, then increase the limit:

```powershell
python scripts/discover_public_contacts.py --assessor black-hat --limit 5 --output tmp/public-contacts-test.json
python scripts/discover_public_contacts.py --assessor black-hat --limit 1000 --output tmp/public-contacts-black-hat-1000.json --auto-apply --workers 4
```

`--assessor` selects people currently lacking a LinkedIn contact. To search an
existing fixed cohort, use `--sample <audit.json>` instead. Without
`--auto-apply`, no contacts are written. `--workers` controls concurrency
(1–16; default 8). Each person may require two provider queries.

The pass writes a contact only if a search result identifies the person and
mentions a substantial portion of a title from their records. Personal websites
must be name-based homepages; social links must point to a personal profile or
identifiable post. Added contacts carry `"source":
"povs-public-contact-discovery"`. The heuristic may miss genuine profiles or
misidentify people, so inspect the audit before publishing.

The output is checkpointed after each completed person. Reuse the same output
path to skip completed slugs; failed searches can be retried. The `--assessor`
cohort is recalculated from current contacts, so it can change between runs;
use `--sample` when an exact fixed cohort matters. The audit is in ignored
`tmp/` and is not shared through Git.

The local Black Hat 1,000-person run stopped after 714 completed searches when
the provider reported exhausted credits. It added 19 links; inspect
`tmp/public-contacts-black-hat-1000.json` before publishing. After replenishing
credits, rerun the 1,000-person command above to continue; the recalculated
cohort may differ from the original selection.

### Older LinkedIn-only workflow

LinkedIn links are optional profile contact information, not evidence. The
project does not scrape LinkedIn. The discovery helper requests public result
metadata from a search provider using the simple query
`site:linkedin.com "PERSON NAME" AND "Cyber"`. It is assessor-scoped rather
than tied to any individual conference.

1. Copy `.env.example` to `.env` and add `SERPER_API_KEY` (recommended). The
   `.env` file is ignored by Git and must never be committed. The script also
   supports `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ID` for existing Google Custom
   Search JSON API accounts.
2. Generate candidates with `python scripts/discover_linkedin_profiles.py --assessor grrcon --limit 5`.
3. Corroborate those candidates with `python scripts/corroborate_linkedin_sample.py tmp/linkedin-candidates-grrcon.json --output tmp/linkedin-corroborated-grrcon.json --auto-apply`.

Do not rely on the older discovery helper's `--auto-apply` option for identity
verification: its name-and-uniqueness rule has produced a false positive.

Use `--limit N --offset M` to select batches for the older helper. Its output
is rewritten on each run, so use separate output paths for separate batches.

Every link written by this tool has `"source": "povs-linkedin-discovery"` in
its contact entry. This identifies links written by the tool; it does not
guarantee that a match was independently verified.

The older helper's automatic criteria require a sole full-name LinkedIn result
with a cybersecurity signal, but that alone does not establish identity. For a
lower-confidence candidate, a maintainer may still explicitly approve one
returned candidate URL and apply it with:

```powershell
python scripts/discover_linkedin_profiles.py --assessor grrcon --apply tmp/linkedin-candidates-grrcon.json
```

Google's Custom Search JSON API is closed to new customers. For a new setup,
use a provider such as Serper that supplies Google search results.

## CVE processing

See [`cve.md`](cve.md) for the CVE data model and
[`cve-operations.md`](cve-operations.md) for yearly processing, resumability,
the unattended 1999-2025 runner, verification, and disk cleanup. 2026 is
currently excluded.
