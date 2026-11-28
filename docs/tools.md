# Tools index

Run Python commands from the repository root. This index describes the tools;
see the linked guides for prerequisites, options, and full workflows. Use
`--help` on tools that accept arguments before running them.

## Capture and publish data

| Tool | Purpose and output |
| --- | --- |
| `python -m scrapers` | Runs assessor scrapers, captures source material, and writes assessor snapshots and run statistics. See [operations](operations.md#standard-run). |
| `python -m scrapers.archive_cli --assessor <id>` | Captures the configured source pages for one assessor in its local archive. |
| `python -m scrapers.individuals` | Merges assessor snapshots into `data/individuals/`; the normal merge rebuilds those files. See [operations](operations.md#standard-run). |
| `python -m scrapers.enrichment_cli` | Collects optional enrichment such as video links; see [enrichment and transcripts](enrichment-and-transcripts.md). |
| `python -m scripts.backfill_endorsement_locations` | Checks endorsement locations; defaults to a dry run, and `--apply` writes changes. See [location status](endorsement-location-status.md). |
| `python -m scripts.generate_page_source_links` | Rebuilds the derived `data/assessors/<id>/page-source-links.json` mappings used by the website's per-page endorsement counts. It reads archived pages and published records, does not fetch the network, and does not change endorsements. Run after changing those inputs. See [operations](operations.md#review-outputs). |
| `python -m scripts.generate_page_parsers` | Legacy generator for standalone page-parser modules. It expects assessor JSON directly under `data/assessors/`, whereas the current metadata is in assessor subdirectories; check its assumptions before using it. See [scraper development](scraper-development.md). |
| `python scripts/normalize_person_names.py` | Updates name casing in individual, contact, and assessor snapshot JSON files. |

## Public contact information

Contact discovery uses search providers and may use a paid API. Keep credentials
in the ignored `.env` file. See [public contact discovery](operations.md#public-contact-discovery)
for setup, output, and confidence limitations.

| Tool | Purpose and output |
| --- | --- |
| `scripts/discover_public_contacts.py` | Searches for public profile links and writes an audit; `--auto-apply` can also update contact-information JSON. |
| `scripts/discover_linkedin_profiles.py` | LinkedIn-specific discovery and application helper; supports a review file or high-confidence automatic application. |
| `scripts/corroborate_linkedin_sample.py` | Checks a saved LinkedIn sample against indexed Black Hat work; can apply candidates with `--auto-apply`. |
| `scripts/review_public_contact_candidates.py` | Reviews candidates from a saved public-contact audit against independently saved search results. |
| `scripts/import_assessor_contacts.py` | Merges contact links captured in assessor data into `data/contact-information/`. |
| `scripts/recover_contact_information.py` | One-off recovery from a hard-coded historical Git revision; it creates a temporary archive and writes contact files. Inspect its assumptions before reuse. |

## Website and checks

Run these from `website/`. The normal build generates the site, sitemap, and
search index; personalized social cards are a separate build step used by the
deployment workflow. See [social cards](social-cards.md).

| Tool | Purpose |
| --- | --- |
| `npm run dev` | Starts the local development server. |
| `npm run build` | Builds the website, sitemap, and search index locally. |
| `npm run build:social` | Generates personalized social cards; may use substantial disk space for a full dataset. |
| `npm run check:pages-size` | Checks the size of the generated site. |
| `node tests/assessor-stats.test.mjs` | Checks assessor totals, domain counts, and source-page mappings against published records. |

The Python tests live in `tests/`; run a focused module with, for example,
`python -m unittest tests.test_schema`. CVE-specific commands and their storage
requirements are documented separately in [CVE operations](cve-operations.md).
