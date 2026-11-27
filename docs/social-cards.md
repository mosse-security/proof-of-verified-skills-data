# Social preview cards

The GitHub Pages workflow generates a 1200 × 630 JPEG for each individual in `dist/social/`, plus a default card. Cards use the same record and assessor counts as the profile. A normal local website build does not generate cards.

The deployment workflow checks the size of the complete output against the 1 GB GitHub Pages published-site limit. Image size varies with the name and summary, so check the build's reported size as the directory grows. A successful size check does not guarantee deployment time or artifact limits will be met.

For a local sample, run the following from `website` in PowerShell:

```powershell
$env:SOCIAL_CARD_LIMIT = '100'
$env:SOCIAL_CARD_OUTPUT = '../tmp/social-card-sample'
node scripts/generate-social-cards.mjs
Remove-Item Env:SOCIAL_CARD_LIMIT, Env:SOCIAL_CARD_OUTPUT
```

Use `SOCIAL_CARD_SLUG` to generate a single profile, or `SOCIAL_CARD_WORKERS` to change concurrency (1–8). These options are intended for testing; leave them unset for a complete production build.
