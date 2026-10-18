# Proof of Verified Skills Data

This repository captures conference endorsements, validates individual names,
and builds canonical individual records.

## Use the tool

Install dependencies and run the local capture pipeline:

```powershell
python -m pip install -r requirements.txt
python -m scrapers --overwrite --workers 1
python -m scrapers.individuals --assessors-dir data/assessors --output-dir data/individuals
```

The scraper reads archived conference pages from `data/archives/html` and
existing local enrichment archives. It does not require a network refresh when
the required archives already exist.

To run one assessor:

```powershell
python -m scrapers --assessor insomnihack --overwrite --workers 1
```

Optional external video refreshes use `yt-dlp`:

```powershell
python -m scrapers.enrichment_cli --list
python -m scrapers.enrichment_cli --overwrite
```

## Verify a change

```powershell
python -m unittest discover -s tests -p 'test_*.py' -q
python -m compileall -q scrapers tests
```

The full documentation is in [`docs/`](docs/README.md). Start with
[`docs/architecture.md`](docs/architecture.md) for the storage model and
[`docs/operations.md`](docs/operations.md) for the normal run sequence.
