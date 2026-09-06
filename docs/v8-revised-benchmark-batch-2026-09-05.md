# Revised v8 initial benchmark batch

The user clarified that all three models should run the full benchmark:
Luna, Terra, and 5.4-mini each use seeds 11/41. No other models or seeds are authorized
by this batch. All use participant-v8-revised, medium reasoning, ten agents,
60 ticks, no board, per-action Execution, and equal-weight Capability.

Launch source: 783341aad5cf195209091652f6eb25420f4af0b8

Configs: configs/run-configs/v8-revised-20260905/.
Job IDs:
- gpt-5-6-luna-v8-revised-20260905
- gpt-5-6-terra-v8-revised-20260905
- gpt-5-4-mini-v8-revised-20260905

Each job manifest lives at runs/jobs/JOB_ID/job.json and records unique
cohorts, sessions, artifacts, resolved launch settings and readiness.
Artifacts live at runs/managed/JOB_ID/seed-N/. Codex uses ChatGPT subscription
authentication with connector-v3, fresh conversations and exact requested
model slugs. Medium support was verified in the native model catalog.
Requested-only provenance is accepted when the CLI has no independent echo.
Four decision workers per cell; seed 41 releases only after seed 11's health
gate. Local durable controllers own recovery, quota waits and finalization.

Luna's comparison baseline is gpt-5-6-luna-v8-20260905 seed 11 at source
75bd330bfc4027a993ba007aa16ac2effe00fccb. Use the same full-horizon health formula
on both recorded trajectories; preserve their distinct recipes and provenance.
The historical baseline lacks per-action telemetry. This paired before/after
comparison is exploratory, not an isolated estimate free of response variation.
See v8-revised.md. Do not pool old and revised benchmark scores.

The existing 15-minute low-reasoning monitor should follow these studies,
inspect each startup gate once, and react only to attention or finalization.
All three studies target ready with both required seeds.
Verify integrity, full usage coverage, requested model/effort, independent
API-list cost, deterministic declared-transfer accounting and recipe identity.
Do not admit results from the launch/monitor workflow.


## Startup recovery and expanded comparison

The first launch failed before any model calls: detached processes inherited a
PATH without the Codex installation directory. The launcher now explicitly
preserves the caller's PATH for cells and controllers. Recovery retains the
same simulation commit and cohort identities, archives the failed startup
manifest, and uses a corrected orchestration commit. Empty event and usage
ledgers are required before initial-start recovery. This is not a simulation
restart or a quota workaround.

The user explicitly added Luna seed 41. Compare all three revised studies to
their original v8 counterparts at matched seeds 11 and 41, using the same
equal-weight health calculation. Archive original outcomes; do not relabel them.
