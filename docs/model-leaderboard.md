# Agent World model leaderboard

Participant v8 is finalized for new benchmark runs: medium effort, ten agents,
60 ticks, seeds 11 and 41, no message board, and explicit commerce labels.
Two models have completed both required seeds and passed finalization.
Rows are ordered by Capability; there is no composite overall score.

| Model | Capability | Execution | Production | Cost/run | Mean time/decision |
|---|---:|---:|---:|---:|---:|
| GPT-5.6 Terra | 31.4 | 63.3 | 112.5 | $7.44 | 11.07s |
| GPT-5.6 Luna | 8.9 | 63.1 | 79.0 | $0.55 | 14.91s |

Capability and Execution are 0–100 scores. Production is unbounded fixed
accounting value added per 100 original-population agent-ticks. Cost/run is
API-list equivalent per world, including recorded retries; it is not a
subscription charge. Mean time/decision includes recorded attempts per
resolved decision, excluding between-call quota waits.

See the [v8 specification](model-benchmarks.md) and
[production formula](v8-production.md).
Historical [v6](model-leaderboard-v6.md) and [v7](model-leaderboard-v7.md)
leaderboards remain available. Their results are unchanged and are not v8
comparison data. The [source catalog](../data/run-sources.json) and generated
[database](../data/model-benchmarks.sqlite) preserve those original suites.

Luna seed 41 includes one confirmed model-output contract failure, retained in
Execution scoring. Both studies have clean benchmark integrity and 100% usage
coverage. Native CLI identity is labelled requested-only. See the
[batch evidence handoff](v8-initial-benchmark-batch-2026-09-05.md).
