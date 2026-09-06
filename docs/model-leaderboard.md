# Agent World model leaderboard

Revised Participant v8: medium effort, ten agents, 60 ticks, seeds 11 and 41,
no message board, corrected capacity feedback, per-action Execution, and
equal-weight Capability. All three models passed two-seed finalization.
Rows are ordered by Capability; there is no composite overall score.

| Model | Capability | Execution | Production | Cost/run | Mean time/decision |
|---|---:|---:|---:|---:|---:|
| GPT-5.6 Terra | 66.0 | 90.1 | 165.0 | $8.50 | 11.61s |
| GPT-5.6 Luna | 64.1 | 86.6 | 108.2 | $0.65 | 17.25s |
| GPT-5.4 Mini | 55.9 | 88.4 | 86.8 | $3.90 | 23.25s |

Capability and Execution are 0–100 scores. Capability averages health over the
original population and every completed tick; dead agents contribute zero.
Production is unbounded fixed accounting value added per 100 original-population
agent-ticks. Cost/run is token-derived API-list equivalent per world, including
retries, not a subscription charge. Mean time/decision includes recorded attempts
per resolved decision and excludes between-call quota waits.

All six worlds have clean integrity and 100% usage coverage, complete declared
transfer accounting and API-list cost. Native CLI identity is requested-only.
Simulation source is 783341aad5cf195209091652f6eb25420f4af0b8.
See the [batch handoff](v8-revised-benchmark-batch-2026-09-05.md),
[specification](model-benchmarks.md), [scoring revision](v8-revised.md),
[source catalog](../data/run-sources.json), and
[generated database](../data/model-benchmarks.sqlite).

Historical [original v8](model-leaderboard-v8-original.md),
[v7](model-leaderboard-v7.md), and [v6](model-leaderboard-v6.md) remain separate.
GPT-5.5 has no revised-v8 run yet and is therefore absent from this table.
