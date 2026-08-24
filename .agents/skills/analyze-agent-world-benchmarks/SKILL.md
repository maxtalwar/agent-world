---
name: analyze-agent-world-benchmarks
description: Analyze Agent World benchmark evidence, compare models, validate certification and provenance, or maintain the benchmark catalog, database, and leaderboard. Use for Agent World model-performance, cost, latency, reliability, and model-selection questions; not for generic benchmark advice.
---

# Analyze Agent World Benchmarks

Ground every conclusion in the repository's durable evidence rather than chat history, filenames, startup manifests, or partial runs.

## Require an analysis-ready handoff

- For a new or unadmitted benchmark study, read `docs/benchmark-run-protocol.md` and inspect the study manifest's `analysis_readiness` block before interpreting performance.
- For a general experiment, read `docs/agent-world-experiment-runs.md`, keep the analysis diagnostic, and do not infer benchmark or provisional status from seed 11. If the requested claim needs cost or transfer accounting that was intentionally skipped, finish it through `$run-agent-world-experiment` first.
- `ready` supports replicated-certification analysis. `provisional_ready` supports clearly labelled provisional analysis, including a simulated leaderboard position that never masquerades as admission.
- `waiting_quota`, `diagnostic_only`, `invalid`, and `needs_provenance_review` do not support a standard leaderboard claim. Diagnose them only in the class their evidence supports.
- For benchmark admission or placement, confirm clean integrity, 100% usage coverage, verified model provenance, independently derived API-list cost (or an explicit unavailable reason), and complete protocol-appropriate transfer accounting. For a diagnostic experiment, report actual integrity and require only the accounting needed for the claim being made.
- Participant v7 requires deterministic `self_declared_v7` accounting; do not run an LLM gift classifier. Participant v6 economic or entrepreneurship analysis requires a valid frozen classification for every gift, or `none_no_gifts` when the ledger has none; an unrelated smoke test may explicitly record `not_required`.
- Do not silently classify gifts, regenerate reports, repair provenance, or otherwise finish the run inside analysis. State that finalization is incomplete and use the appropriate benchmark or experiment run skill if the user asks to complete it.
- Already cataloged historical evidence may predate `analysis_readiness`; its verified catalog and database admission are the durable substitute.

## Choose the evidence path

- For model comparison or selection, start with `data/model-benchmarks.sqlite`. Read `docs/model-metrics-database.md` for schema semantics and maintained example queries. Use `docs/model-leaderboard.md` only as the canonical compact projection.
- For protocol, scoring, certification, or cross-version questions, read the relevant sections of `docs/model-benchmarks.md` before interpreting results.
- For behavioral claims and known harness caveats, consult `docs/insights.md`, then follow its evidence pointers to the underlying run artifacts when the claim needs confirmation.
- For a cataloged benchmark run, use its entry in `data/run-sources.json` to locate the report, usage ledger, manifest, integrity status, and hashes. Prefer the database's typed fields; for an unadmitted experiment, start from its manifest and inspect raw artifacts only for the diagnostic question.

## Analyze carefully

1. Run `python3 -m agent_world.benchmark_db verify` before relying on the generated database. If verification fails, report the failure and diagnose provenance before making a durable claim.
2. Query the narrowest relevant layer: `leaderboard` or `model_capabilities` for certified cross-model comparisons, `evidence` for all admitted runs, and `runs`, `run_cohorts`, `benchmark_trials`, `tick_metrics`, or `decisions` for provenance and diagnostics.
3. State the comparison frame: suite/protocol, certification class, seed coverage, reasoning effort, provider/brain, world preset, connector, and launch commit when they could affect the conclusion.
4. Keep certified, provisional, controlled-variant, diagnostic, superseded, and excluded evidence distinct. Never promote an excluded, partial, degraded, or stopped run into a leaderboard result.
5. Pool benchmark scores only through the repository's benchmark tooling. Do not average rounded seed scores or combine mismatched protocols.
6. Interpret latency according to `docs/model-metrics-database.md`: individual decision latency, concurrent tick wall span, normalized tick throughput, and whole-run observed span are different measures. Never sum concurrent decision latencies to estimate elapsed run time.
7. Separate observed facts from inference. Cite the database query and the exact local report, manifest, ledger, or documentation file supporting any non-obvious claim.

## Present the result

- For benchmark or comparative model analysis, lead with a compact mini-table containing the subject and its nearest meaningful leaderboard neighbors from the same comparable pool. Include the canonical score columns, tier/seed coverage, integrity, cost, and other columns material to the comparison; label any cross-protocol context separately. A narrow harness or smoke-test diagnostic may lead with the finding instead.
- If the subject is provisional or otherwise unadmitted but analytically comparable, show where it would sit as a clearly marked simulated position. Never insert it into the canonical table without admission.
- Describe what the economy actually looked like: survival, production and capital formation, trade and service income, transfer types, institutions or public goods, specialization, and the strongest ledger-backed stories of entrepreneurship or coordination.
- Scale depth to information value. A strong, unusual, or strategically rich result merits a fuller narrative and more behavioral evidence; a weak, invalid, or uneventful result can be concise while still explaining the failure mode.
- Distinguish facts, calculations, and interpretations. Explain protocol caveats that materially change the comparison rather than burying them below the score.

## Maintain durable results

When adding or correcting durable benchmark evidence, update `data/run-sources.json`, rebuild and verify `data/model-benchmarks.sqlite`, and regenerate the compact projection in the same scoped change:

```bash
python3 -m agent_world.benchmark_db build --catalog data/run-sources.json
python3 -m agent_world.benchmark_db verify
python3 -m agent_world.benchmark_db leaderboard
```

Run the relevant tests, including `tests/test_benchmark_db.py` and `tests/test_benchmarks.py` when their behavior is affected. Follow `AGENTS.md` for commits, pushes, isolated model-backed runs, quota handling, and the evidence bar for `docs/insights.md`.

## Run-workflow boundary

Only launch, resume, monitor, or finalize model-backed cells when the user asks. Use `$run-agent-world-benchmark` for explicit benchmark, leaderboard, certification, or participant-protocol work; use `$run-agent-world-experiment` for general runs and tests. Analysis may inspect raw artifacts and diagnose a stopped run, but it does not bypass either run skill's isolation, quota, completion, accounting, or evidence gates.
