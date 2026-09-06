# Agent World model leaderboard

Participant v8 is finalized for new benchmark runs: medium effort, ten agents,
60 ticks, seeds 11 and 41, no message board, and explicit commerce labels.
No v8 model results have been admitted yet.

| Model | Capability | Execution | Production | Cost/run | Mean time/decision |
|---|---:|---:|---:|---:|---:|

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
