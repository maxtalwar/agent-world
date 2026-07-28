# Agent World benchmark: agent-world-participant-v4

| Model | Seeds | Execution | Competence | Entrepreneurship | Invalid proposals | Status |
|---|---:|---:|---:|---:|---:|---|
| gpt-5.3-codex-spark | 11 | 71.5 | 30.2 | 0.0 | 444 (33.2%) | provisional with declared deviation |

## Per-replication scores

| Model | Seed | Role | Execution | Competence | Entrepreneurship |
|---|---:|---|---:|---:|---:|
| gpt-5.3-codex-spark | 11 | certification | 71.5 | 30.2 | 0.0 |

Descriptive spread:

- gpt-5.3-codex-spark: official competence range 30.2–30.2, absolute seed difference n/a.

## Declared deviations

- **gpt-5.3-codex-spark** (seed 11) ran under `participant-v3`, accepted as v4 evidence after audit.
  - Deviation: static_context_mechanics_text: ore was described as a 'high-value raw material' rather than as smeltable into an ingot. Same one-line static-context difference accepted for the GPT-5.4 pair. See also the attribution override recorded in BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES for this trial.
  - Audit: Every difference from commit 60c4143 to v4 was examined. The run built zero structures, so the contributor-share change never fired. Engine trade values never reached agents, verified at 60c4143 itself. The ACCOUNTING_VALUES rename changed no value. The models.py and cli.py edits are a comment and seed-validation text. The decision-contract validator does not alter the prompt, so the model faced the same world; it alters failure attribution only, which is covered by the separate attribution override.
- **gpt-5.3-codex-spark** (seed 11) ran under `participant-v3`, accepted as v4 evidence after audit.
  - Deviation: unverified_model_output_attribution: two decision failures at ticks 7 and 28 record only the production adapter's parse error. The trial predates the independent contract validator and no response payload was retained, so malformed model output cannot be distinguished from adapter rejection of valid output.
  - Audit: Scoring both failures against the model gives effective execution 71.46; excluding them entirely gives 71.54. The disputed span is 0.08 points over 1,331 submitted actions. Owner decision, 2026-07-26: Spark inference is usage constrained, and a 0.08-point gap does not justify spending a full 50-tick trial to resolve it.
