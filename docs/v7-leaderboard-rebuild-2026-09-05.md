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
