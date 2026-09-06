---
name: run-agent-world-benchmark
description: Launch, resume, monitor, finalize, or report status on standardized Agent World benchmark trials. Use when the user explicitly asks for a benchmark, leaderboard result, certification, provisional benchmark, or named participant protocol; not for general simulations, smoke tests, or experiments.
---

# Run Agent World Benchmark

Use for explicit benchmark, leaderboard, certification, or named-protocol requests.
Ordinary simulations belong to run-agent-world-experiment; interpretation and
admission of completed evidence belong to report-agent-world-runs.

## Select the study

Launch model-backed work only within the user's authorized scope. Resolve the
exact model and connector; never silently substitute a model or effort.

For new benchmarks, consult docs/model-benchmarks.md for the current suite and
explicitly select its recipe. Inspect it with python3 -m agent_world recipes
RECIPE_ID. Honor an explicitly named older recipe. A requested single seed is
provisional; otherwise use the recipe's required seeds. Worker count controls
throughput, not eligibility. Apply AGENTS.md's usage policy.

Preserve recipe and source identity on recovery. Keep changed conditions
separate; do not relabel historical evidence.

## Operate and hand off

Use python3 -m agent_world run --config CONFIG.json --dry-run, then the same
command without --dry-run. Consult docs/run-quickstart.md when authoring configs
or resolving syntax. The managed runner owns isolation, supervision, startup
release, recovery, quota waits and finalization.

Inspect status on request or meaningful events, not ticks. Arrange follow-up
using the user's monitoring preferences; remove verified completed studies
from its worklist and stop when none remain. Do not duplicate controller work.

Read the relevant section of docs/benchmark-run-protocol.md for attention or
finalization blockers. A quota wait preserves the world; it is not a reason
to restart. Recover the existing study only after resolving its blocker.

Report readiness from the job manifest, not elapsed time or process exit.
Include remaining seeds/blockers and artifact location. Readiness requires
completion, integrity, usage, provenance and recipe-specific accounting.
Hand ready evidence to report-agent-world-runs; this workflow does not admit
leaderboard results. Follow AGENTS.md for repository changes.
