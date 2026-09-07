# GPT-5.5 and GPT-5.4 Mini high-effort Capability probes

Question: does increasing requested effort improve GPT-5.5 reasoning allocation
and sustained survival in the current world? This is an authorized ordinary
experiment, not leaderboard evidence. Only seed 11 is requested.

Job: gpt-5-5-v81-high-capability-probe-20260906.
Config: configs/run-configs/gpt-5-5-v81-high-capability-probe-20260906.json.
Source and orchestrator: 39232e4729d28111b794054c48895c527bf0ad07.
The dashboard's existing pinned-source launch-checkout helper supplies an
independent local clone and shared job registry; the managed CLI owns cell
isolation, supervision and recovery.

Baseline: runs/managed/gpt-5-5-v8-revised-20260906/seed-11/run-report.json.
Same source, model, world seed, ten agents, 60 ticks, no board, recipe defaults,
fresh conversations and four workers; change only requested medium -> high.
Primary outcome: equal-weight original-population health over completed ticks.
Secondary outcomes: exact per-action Execution, productive value added, survivors,
damage causes, reasoning tokens per call and zero-reasoning frequency.
Do not change the Capability formula after seeing the result or admit this
controlled reasoning variant to the medium-effort leaderboard.

Confirm completion and integrity before analysis, including full usage coverage.
Check whether high actually changes token allocation; an effort label alone is
not evidence of more deliberation. Compare matched trajectories and failures.
A single historical before/after pair is exploratory, not proof of causation.
No additional replications are included. The explicitly authorized Mini extension below adds the matched second model.

The existing low-effort monitoring task should follow this job to completion,
repair routine infrastructure faults, and remove it from the worklist after a
verified handoff. It remains a general experiment: use the experiment skill
and do not require benchmark certification for high effort.

## Matched Mini extension (2026-09-06)

The user requested GPT-5.4 Mini at high effort alongside GPT-5.5. This creates
a two-model by two-effort exploratory comparison using completed medium worlds
and newly launched high worlds, all on seed 11. Each new condition uses one
world only to conserve usage. Retain the same 60-tick horizon to include all
five seasons.

Job: gpt-5-4-mini-v81-high-capability-probe-20260906.
Config: configs/run-configs/gpt-5-4-mini-v81-high-capability-probe-20260906.json.
Medium baseline: runs/managed/gpt-5-4-mini-v8-revised-20260905/seed-11/run-report.json.
High comparator: runs/managed/gpt-5-5-v81-high-capability-probe-20260906/seed-11/run-report.json.
The Mini high config differs from the 5.5 high config only in model identity,
run identity and study question. Both pin source and orchestrator
39232e4729d28111b794054c48895c527bf0ad07, with four Codex workers.
The older Mini medium baseline pins 783341aad5cf195209091652f6eb25420f4af0b8;
retain that provenance and verify relevant source/config differences during
analysis rather than describing it as an identical-source intervention.

Compare each model's medium-to-high change, then compare the between-model gap
at each effort. Preserve the predeclared Capability formula. Report Execution,
Production, survival trajectories, reasoning allocation, API-equivalent cost
and per-decision latency as diagnostics. Labels do not establish equal compute;
verify actual reasoning usage. One historical pair per model cannot establish
a causal interaction or generalize across seeds.

Both high conditions remain diagnostic_only and excluded from the medium
leaderboard. The existing low-effort monitor owns startup-gate inspection,
terminal verification and routine recovery for both jobs. Do not launch more
seeds or models.
