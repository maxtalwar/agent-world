---
name: analyze-agent-world-benchmarks
description: Analyze Agent World benchmark evidence, compare models, validate certification and provenance, or maintain the benchmark catalog, database, and leaderboard. Use for Agent World model-performance, cost, latency, reliability, and model-selection questions; not for generic benchmark advice.
---

# Analyze Agent World Benchmarks

Ground every conclusion in the repository's durable evidence rather than chat history, filenames, startup manifests, or partial runs.

## Choose the evidence path

- For model comparison or selection, start with `data/model-benchmarks.sqlite`. Read `docs/model-metrics-database.md` for schema semantics and maintained example queries. Use `docs/model-leaderboard.md` only as the canonical compact projection.
- For protocol, scoring, certification, or cross-version questions, read the relevant sections of `docs/model-benchmarks.md` before interpreting results.
- For behavioral claims and known harness caveats, consult `docs/insights.md`, then follow its evidence pointers to the underlying run artifacts when the claim needs confirmation.
- For a specific run, use the catalog entry in `data/run-sources.json` to locate its report, usage ledger, manifest, integrity status, and hashes. Prefer the database's typed fields; inspect raw artifacts only for details not represented there.

## Analyze carefully

1. Run `python3 -m agent_world.benchmark_db verify` before relying on the generated database. If verification fails, report the failure and diagnose provenance before making a durable claim.
2. Query the narrowest relevant layer: `leaderboard` or `model_capabilities` for certified cross-model comparisons, `evidence` for all admitted runs, and `runs`, `run_cohorts`, `benchmark_trials`, `tick_metrics`, or `decisions` for provenance and diagnostics.
3. State the comparison frame: suite/protocol, certification class, seed coverage, reasoning effort, provider/brain, world preset, connector, and launch commit when they could affect the conclusion.
4. Keep certified, provisional, controlled-variant, diagnostic, superseded, and excluded evidence distinct. Never promote an excluded, partial, degraded, or stopped run into a leaderboard result.
5. Pool benchmark scores only through the repository's benchmark tooling. Do not average rounded seed scores or combine mismatched protocols.
6. Interpret latency according to `docs/model-metrics-database.md`: individual decision latency, concurrent tick wall span, normalized tick throughput, and whole-run observed span are different measures. Never sum concurrent decision latencies to estimate elapsed run time.
7. Separate observed facts from inference. Cite the database query and the exact local report, manifest, ledger, or documentation file supporting any non-obvious claim.

## Maintain durable results

When adding or correcting durable benchmark evidence, update `data/run-sources.json`, rebuild and verify `data/model-benchmarks.sqlite`, and regenerate the compact projection in the same scoped change:

```bash
python3 -m agent_world.benchmark_db build --catalog data/run-sources.json
python3 -m agent_world.benchmark_db verify
python3 -m agent_world.benchmark_db leaderboard
```

Run the relevant tests, including `tests/test_benchmark_db.py` and `tests/test_benchmarks.py` when their behavior is affected. Follow `AGENTS.md` for commits, pushes, isolated model-backed runs, quota handling, and the evidence bar for `docs/insights.md`.

## New model-backed runs

Only launch a run when the user requests one. Read `docs/isolated-run-worktrees.md` and use `scripts/run-isolated-cohort` for every independently executing run cell, with a distinct cohort ID and a clean pinned launch commit. Preserve the worktree through completion and analysis. Treat rate limits as resumable waiting states; do not restart a run or fabricate agent decisions from failed provider calls.
