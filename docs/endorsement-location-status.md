# Endorsement location backfill

The November 2026 backfill added event-specific `location` values to canonical
individual records and assessor-local snapshots. Country pages use these values
instead of assigning every country in an assessor's coverage to every record.
The matching rules are in `scrapers/locations.py`; new scraper output passes
through the same endorsement builder.

To check or resume the migration from the repository root:

```text
python -m scripts.backfill_endorsement_locations
python -m scripts.backfill_endorsement_locations --apply
python -m unittest tests.test_locations tests.test_schema tests.test_black_hat
```

The first command is a dry run. The write pass preserves known location values,
records `"Unknown"` when no location is established, and can be restarted. It updates `last-updated` when a canonical record
changes. The counts printed by the script include both canonical files and
assessor-local snapshots, so they must not be interpreted as distinct people.

DEF CON records are classified as `"United States"`, including its online and
hybrid editions, according to the project's requested convention. This denotes
the conference's location, not whether an individual presenter was onsite.
Additional events should be added only after checking event-specific sources
and virtual formats. To correct older DEF CON records, run the backfill with
`--refresh-def-con --apply`; this flag only overwrites DEF CON locations.

The full `tests.test_individuals` suite currently has failures involving
synthetic example identities being filtered during assessor output rebuilding;
the location, schema, and Black Hat tests pass. Recheck that suite when working
on the merge pipeline.
