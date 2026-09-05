# Participant v7 leaderboard rebuild — 2026-09-05

This batch benchmarks seven user-selected models under Participant v7 on seeds
11 and 41. Every cell uses the frozen recipe: 50 ticks, 10 generalists,
frontier world, low reasoning, connector-v3, and fresh conversations.

All studies were launched from clean commit
`bf5b0a188e80883b02a67436af5fed1ad63fcbdc` through the managed interface.
These are benchmark candidates; launch does not establish certification.

| Requested model | Connector | Workers per seed | Run ID |
|---|---|---:|---|
| GPT-5.6 Terra | Codex | 4 | gpt-5-6-terra-v7-20260905 |
| GPT-5.6 Luna | Codex | 4 | gpt-5-6-luna-v7-20260905 |
| GPT-5.5 | Codex | 4 | gpt-5-5-v7-20260905 |
| GPT-5.4 Mini | Codex | 4 | gpt-5-4-mini-v7-20260905 |
| Grok 4.5 | Grok CLI | 2 | grok-4-5-v7-20260905 |
| Grok 4.6 | Grok CLI | 2 | grok-4-6-v7-20260905 |
| Muse Spark 1.1 | Muse Code | 2 | muse-spark-1-1-v7-20260905 |

The second seed is released only after its model's first seed passes the
startup health gate. The batch permits at most 32 concurrent Codex decisions,
eight Grok decisions, and four Muse decisions. Limits are per cell, not a
shared provider-wide semaphore.

## Evidence and operations

Local predeclared configs and study manifests are under
`runs/launch-plans/v7-rebuild-20260905/`. Managed job manifests are
`runs/jobs/RUN_ID/job.json`; simulation evidence is under
`runs/managed/RUN_ID/seed-11/` and `seed-41/`. Each cohort ID is
`RUN_ID-seed-SEED`. Raw evidence and credentials remain local.

Codex's native catalog listed all four exact model IDs with low reasoning.
Grok's authenticated OAuth catalog listed both requested versions; its local
native configuration was aligned with the existing OAuth login. No new account
or alternative billing boundary was introduced.

Muse has no native model-list command. The exact requested
`muse-spark-1.1` was launched without substituting 1.3. Its initial requests
returned HTTP 429 service-unavailable/rate-limit errors, so the world remains
frozen under the standard quota-wait policy. This does not prove that the model
ID is unavailable.

Grok 4.5 initially paused at tick zero with unusable native completion
envelopes, including cancelled structured-output responses. Grok 4.6 produced
usage-bearing decisions with backend model label `grok-4.6-build`.
These observations are availability/integrity evidence, not capability scores.

Managed controllers own recovery and per-seed finalization. A thread follow-up
checks completion and attention events every ten minutes and remains quiet
without actionable changes. Completed evidence must pass the readiness audit
before separate reporting/catalog admission; v6 and v7 results remain distinct.

## Follow-up at 03:20 UTC

All four OpenAI studies passed their startup gates and have both seeds active.
Grok 4.5 requires attention after a second unusable tick-zero response set;
its second seed remains unlaunched. Muse 1.1 remains in quota wait at tick zero.

Grok 4.6 resumed after a boundary failure at tick 3. Its resumed execution
skipped the startup-health check because the pinned session predicate excludes
all resumed runs. Seed 41 remains gated. This is an unresolved benchmark
handoff blocker; advancing seed 11 is not evidence that the startup gate passed.
The original ledger and source remain intact. See the dated insights entry.

## Corrected Grok connector validation

Commit 440c126 fixes early-resume startup checks and delivers the complete
simulation rulebook in the Grok user turn. The native Grok 4.5 path had omitted
the prior system-only rulebook. Native coding-plan mode was also removed.

Managed two-agent, two-tick smoke studies
grok-4-5-rulebook-smoke-20260905 and grok-4-6-rulebook-smoke-20260905 completed
eight of eight decisions with usage, full rulebook presence verified in every
native transcript, and no native tool events. The full regression suite passed
590 tests, including the native offline Muse test. These are diagnostics, not
leaderboard results. Initial Grok benchmark evidence is retained separately.

The replacement Grok benchmark studies use the suffix -corrected-20260905
and the same Participant v7 settings and required seeds, with four workers per
seed. Their source is pinned separately; the old studies are not relabeled.

## Additional requested model: Muse Spark 1.2

The user separately requested a Spark 1.2 benchmark after its matched generic
availability probe succeeded. Managed study muse-spark-1-2-v7-20260905 was
launched from clean commit 0be8a2e07f5d604b656f5f620c94fc9c4c1218d5 on
seeds 11 and 41, low reasoning, Muse Code, and two workers per seed. All other
settings come from Participant v7. Seed 41 remains behind the standard startup
gate. The existing Spark 1.1 evidence and backoff remain separate.

The config was validated with the managed dry-run command before launch.
The existing completion follow-up includes this eighth study.
