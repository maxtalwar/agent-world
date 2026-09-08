# Astra v8.1 launch — 2026-09-07

User requested Astra on v8.1 while the existing healing damage analysis ran.
Managed study: `gpt-6-astra-v8-revised-20260907`; source
`e10d1a402c3bfef60c1013d568003be7d292a2f4`; recipe
`participant-v8-revised` (public v8.1), unchanged and healing off.
Model `gpt-6-astra`, native Codex connector-v3, medium reasoning,
10 agents, 60 ticks, seeds 11/41, four workers per cell. Seed 41 follows the
standard seed-11 startup gate. This is a benchmark candidate, not a result.

Initial CLI 0.147.0 was rejected by the provider as too old for Astra. It accepted
no decisions and advanced no ticks. The existing WSL CLI was upgraded to npm
`@openai/codex@0.153.4`; authentication was retained. Upgrade instructions:
[official Codex CLI documentation](https://learn.chatgpt.com/docs/codex/cli).

Run Monitoring archived original artifacts and execution evidence under
`runs/jobs/gpt-6-astra-v8-revised-20260907/execution-migration-20260908`, verified
zero accepted decisions/ticks, and recorded the explicit executable migration
before managed resumption. World, recipe, source and model identity were
preserved; no integrity guard was relaxed. The monitor verified seed 11 advanced
to tick 1 with the controller active. Its `migration.json` and job
`operational_recovery` retain the audit. There was no replacement study.

The existing event worklist contains
`monitor-gpt-6-astra-v8-revised-20260907`, owned by Run Monitoring with Astra low
effort. One consolidated handoff covered this batch. Local controllers handle
progress, quota waits, startup release and finalization; agent follow-up is for
new terminal/attention events, not repeated healthy/quota polling.
