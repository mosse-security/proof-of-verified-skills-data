# POVS data pipeline — HOWTO

This is the maintainer and operator guide for capturing assessor records,
validating identities, rebuilding individual records, and checking changes.
For an explanation of POVS itself, start with the repository [README](../README.md).

When adding or enriching endorsements, follow the [endorsement data contract](data-contracts.md#endorsements) for evidence links, bands and properties.

## Identity review policy

> **IDENTITY REVIEW RULE — DO NOT AUTOMATE ALLOW-LIST CHANGES**
>
> Scraper runs may add newly discovered names only to the relevant assessor's
> `individuals-not-validated.txt`. They must never edit, append to, or promote
> names into `data/individuals-enumeration.txt`. The repository owner manually
> reviews those pending names and is the only person authorized to update the
> global allow list. False positives in that file become canonical individual
> records, so preserving this boundary is mandatory.

Read the [identity review policy](identity-review-policy.md) before running
parsers or merging individual records.

## Install and run the local capture pipeline

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

## Optional enrichment refreshes

External video refreshes use `yt-dlp`:

```powershell
python -m scrapers.enrichment_cli --list
python -m scrapers.enrichment_cli --overwrite
```

## Contact and name maintenance

Recovered and assessor-sourced contact links are stored separately from the
canonical individual records:

```text
data/contact-information/{individual}.json
```

To merge assessor contact links into that store:

```powershell
python scripts/import_assessor_contacts.py
```

Automatically discovered LinkedIn links include a contact-level
`"source": "povs-linkedin-discovery"` marker. See
[operations](operations.md#public-contact-discovery) for the conservative discovery
and write workflow.

To apply the repository's display-name casing convention to generated records:

```powershell
python scripts/normalize_person_names.py
```

Do not edit `data/individuals-enumeration.txt` from automation. Names pending
review belong in the assessor-local `individuals-not-validated.txt` file.

## Verify a change

```powershell
python -m unittest discover -s tests -p 'test_*.py' -q
python -m compileall -q scrapers tests
```

## Further maintainer documentation

- [Architecture](architecture.md) — stages, ownership, and filesystem layout.
- [Data contracts](data-contracts.md) — JSON shapes, timestamps, and merge rules.
- [Identity and quality](identity-and-quality.md) — whitelist, blacklist, parser quality, and mojibake protection.
- [Scraper development](scraper-development.md) — archive inventory, parser boundaries, and tests.
- [Enrichment and transcripts](enrichment-and-transcripts.md) — local datasets, optional refreshes, and transcripts.
- [CVE operations](cve-operations.md) — yearly processing and cleanup.
