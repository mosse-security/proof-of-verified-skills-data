# POVS transcript assessor

`level_prompt.md` is the canonical prompt for assigning a POVS level to a
presentation transcript. It is deliberately transcript-only: the model may
not infer production impact, reviewer independence, or industry adoption from
the speaker's reputation or from facts outside the supplied transcript.

Before calling the model, normalize the transcript deterministically:

1. Decode as UTF-8 with replacement for invalid bytes.
2. Normalize CRLF and CR to LF.
3. Remove WebVTT headers, cue timing lines, markup tags, and blank lines.
4. Deduplicate repeated scrolling-caption lines while preserving first-seen
   order.
5. Prefix each remaining line with a one-based line number.

The caller should set temperature to `0` and use a fixed seed when the model
supports one. Validate the response against the JSON contract in the prompt;
reject extra keys, invented citations, non-contiguous line ranges, or quotes
that do not exactly match the numbered transcript.

For Codex review, submit work in deterministic batches of 100 endorsements
(or the final smaller remainder). Sort each batch by the stable identity rules
in `level_prompt.md`, and require one independently cited result per input.

## Running analysis

Use the analysis runner once an OpenAI-compatible API key is configured:

```powershell
python -m endorsement_scraper.povs_analysis --assessor def-con
```

The runner considers only endorsements whose YouTube video ID has a transcript
member. Each analyzed output record contains `endorsement-key`, `person-file`,
`endorsement-index`, `assessor-id`, `video-id`, `transcript-member`, and a
transcript hash, followed by the validated POVS analysis. These stable
references allow a later updater to modify the exact endorsement without
depending on a person's name or list position alone.

`--prepare-only` writes mappings under `pending`; those records deliberately
have no level and are not analysis results. Only records under `results` with
`status: "analyzed"` contain `povs-level` and cited evidence.

Results are written to `data/enrichments/<assessor-id>-youtube-recordings/povs-analysis.json`.
Use `--prepare-only` to generate and inspect the matched record set without
calling a model. Existing results are reused when both the transcript hash and
prompt hash are unchanged.
