# Identity and quality

## Name decisions

The registry applies this order:

1. A globally whitelisted name is allowed.
2. An assessor-local blacklisted name is denied.
3. Any other encountered name is written once to the assessor-local
   `individuals-not-validated.txt` and is not persisted.

The global whitelist is `data/individuals-enumeration.txt`. It is manually
vetted UTF-8 data and must contain no duplicate normalized names. Preserve
Unicode characters exactly. Never rewrite it through an implicit PowerShell
encoding conversion; use an explicit UTF-8 writer or a Unicode-safe editor.
The registry rejects likely mojibake before a run can write records.

Academic prefixes such as `Dr.` are removed for matching and output names.
Aliases and nicknames must be handled by the relevant parser when the source
page identifies them as aliases rather than part of the person's name.

## Parser quality

The quality gate rejects titles, affiliation fragments, schedule prose, event
sessions, and other obvious non-people. Fix the responsible archive parser and
regenerate; do not manually patch generated JSON.

Every unknown name is a review item. After manual classification, rerun the
relevant assessor so the local snapshot and canonical merge reflect the new
decision.
