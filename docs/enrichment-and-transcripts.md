# Enrichment and transcripts

Enrichers are plugins under `scrapers/enrichers/`. Each writes a JSON array as
`data.json` inside `data/enrichments/<enricher-id>/data.zip`. Endorsement
builders load these local catalogs and attach matched recordings as
`evidence-links`.

YouTube collection uses `yt-dlp` and may require network access. It is an
optional external refresh, not part of local archive parsing. Existing local
catalogs remain valid when refresh access is unavailable.

Transcript archives are separate from video catalogs:

```powershell
python -m scrapers.transcripts --assessor <id> --matched-only
python -m unittest tests.test_transcript_coverage -v
```

Transcript ZIPs are stored under `data/archives/yt-transcripts/`. Repeated runs
are intended to be idempotent and only add new or changed video transcripts.
