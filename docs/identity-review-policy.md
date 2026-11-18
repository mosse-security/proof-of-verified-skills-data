# Identity review policy

## Non-negotiable boundary

Automated parser and merge code must not modify:

```text
data/individuals-enumeration.txt
```

That file is the manually reviewed global allow list. Only the repository
owner may add, remove, or edit entries there.

## Correct parser workflow

1. Run the parser against the archive or source page.
2. Let `scrapers.identity_registry.IdentityRegistry` record unknown names in
   the relevant assessor file:

   ```text
   data/assessors/<assessor-id>/individuals-not-validated.txt
   ```

3. The repository owner reviews those names for false positives.
4. Only after manual approval does the owner update
   `data/individuals-enumeration.txt`.
5. Run the individual merge after the allow-list review.

Parser output must not be promoted automatically, even when a source page
looks authoritative. Grouped names, aliases, report labels, malformed HTML,
and non-person text can all produce false positives.

## Change-review check

Before accepting parser changes, verify that the parser did not change the
global allow list:

```powershell
git diff -- data/individuals-enumeration.txt
```

Any unexpected diff in that file must be reverted and investigated before the
parser or merge work continues.
