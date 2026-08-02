# Claude Code repository guide

Read and follow [`AGENTS.md`](AGENTS.md) before changing or running this
repository.

For model selection and cross-model benchmark comparisons, start with the
canonical full table in
[`docs/model-leaderboard.md`](docs/model-leaderboard.md). It includes cost,
reasoning use, the recovered Fable result, and the controlled Luna Max variant.
For full metrics—including per-decision and per-tick latency, seed variance,
reliability, outcomes, commerce, provenance, and excluded diagnostic evidence—
query [`data/model-benchmarks.sqlite`](data/model-benchmarks.sqlite) using
[`docs/model-metrics-database.md`](docs/model-metrics-database.md).
