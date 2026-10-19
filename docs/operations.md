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
