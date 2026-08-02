# Model capability metrics database

The durable cross-model evidence store is
[`data/model-benchmarks.sqlite`](../data/model-benchmarks.sqlite). The compact
[`model-leaderboard.md`](model-leaderboard.md) is intentionally only one
human-readable projection of this database; it does not define the database
schema or limit what is retained.

The database is generated from the explicit source catalog in
[`data/model-benchmark-sources.json`](../data/model-benchmark-sources.json).
That catalog distinguishes leaderboard evidence from useful but excluded
diagnostic evidence. For example, the degraded GPT-5.1 and Grok 4.5 runs remain
queryable, as does Fable's superseded quota-corrupted continuation, but none of
them affects the comparative leaderboard.

## What is stored

| Layer | Table/view | Important contents |
|---|---|---|
| Model | `models`, `model_results`, `model_capabilities` | Rank eligibility, controlled-variant status, combined scores, seed ranges, survival, value creation, commerce, construction, cooperation, reliability, reasoning, cache, cost, and latency distributions |
| Run | `benchmark_runs` | Seed-level scores and outcomes, exact provider/model/effort, protocol and source hashes, launch commit, integrity flags, tokens, cost, latency, and source paths |
| World tick | `tick_metrics` | Decisions per tick, token/cost totals, per-decision latency, and concurrent wall span |
| Decision | `decisions` | Agent/tick, end-to-end call latency, input/cache/output/reasoning tokens, cost, request size, provider response model, conversation state, and request hashes |
| Projection | `leaderboard` | The small ranked table used in benchmark narratives and model selection |

The model and run tables also retain the full frozen raw-metric and score trees
as JSON. This lets a later agent query a familiar typed column quickly while
still reaching less-common metrics without rebuilding the database.

## Latency semantics

Latency was already captured for every historical model decision as
`duration_seconds` in each `run-usage.jsonl`; it simply was not summarized in a
cross-model store. The current database has 100% latency coverage across the
included and diagnostic Participant v6 usage ledgers.

- `decisions.duration_seconds` is end-to-end provider decision latency as seen
  by Agent World. It includes adapter retries, so it measures the wait the
  simulation actually experienced.
- Run- and model-level latency includes mean, median, p90, p95, p99, maximum,
  standard deviation, and coverage.
- `tick_metrics.concurrent_wall_span_seconds` estimates user-visible world-turn
  latency from the earliest concurrent call start to the latest call end.
- `benchmark_runs.usage_observed_span_seconds` runs from the earliest recorded
  call start to the final recorded call end. It is the best historical measure
  of whole-run elapsed time and includes any gaps between recorded decisions.
- `benchmark_runs.wall_clock_seconds` is the manifest's start/end interval.
  For a resumed run it may describe only the last launcher segment, so it is
  retained as provenance rather than treated as authoritative total runtime.

Do not sum decision latency to estimate elapsed run time: agents decide
concurrently. Median is the best quick “typical response” number; p95 exposes
the slow-tail experience.

Time to first token is **not** available from the current non-streaming CLI
connectors. When a provider exposes it reliably, record both request start and
first-token timestamps. Also separate provider compute, queue time, retry wait,
and quota wait when those boundaries become observable; today they are folded
into end-to-end latency.

## Metric priorities

The database now covers the highest-value metrics reconstructable from current
artifacts:

- capability: execution, sustained competence, entrepreneurship, and economic
  productivity;
- outcomes: completion, survival, endpoint health, terminal value, and signed
  value created;
- economic and social behavior: trade funnel/value, gifts, goods supplied,
  service income, contracts, access fees, dividends, structures, cooperative
  builds, construction contributions, groups, access grants, and communication;
- efficiency: prompt/cache/output/reasoning tokens, reasoning per decision,
  cache hit rate, API-list-price-equivalent cost, and latency distributions;
- robustness: per-seed results and score ranges, invalid actions, provider and
  model-output failures, contention, quota/harness failures, telemetry coverage,
  integrity, and quality flags;
- provenance: exact resolved model, provider, brain, effort, seed, protocol,
  launch commit, code fingerprint, connector/conversation settings, source
  paths, and artifact hashes.

The next most valuable additions require new instrumentation rather than a
historical backfill:

1. first-token latency and output/reasoning generation rate;
2. provider queue, retry, backoff, and quota-wait durations as separate fields;
3. time-to-capability milestones—first sustainable food/water source, completed
   structure, accepted trade, service business, contract, group, and death;
4. individual-agent inequality and concentration measures for wealth, health,
   production, ownership, and trade participation;
5. more than two seeds, enabling confidence intervals and a better estimate of
   rare entrepreneurial behavior than a simple two-seed range;
6. structured, evidence-linked qualitative observations for recurring model
   strategies and failure modes. These should point to ledger events rather
   than copying chat claims.

## Common queries

Inspect the leaderboard projection:

```bash
sqlite3 -header -column data/model-benchmarks.sqlite \
  'SELECT * FROM leaderboard ORDER BY rank;'
```

Compare latency, capability, and price:

```bash
sqlite3 -header -column data/model-benchmarks.sqlite '
SELECT label, rank,
       round(competence, 1) AS competence,
       round(latency_median_seconds, 2) AS p50_seconds,
       round(latency_p95_seconds, 2) AS p95_seconds,
       round(api_list_cost_per_run_usd, 2) AS cost_per_run
FROM model_capabilities
WHERE leaderboard_eligible = 1
ORDER BY rank;'
```

Inspect seed sensitivity:

```bash
sqlite3 -header -column data/model-benchmarks.sqlite '
SELECT label,
       round(execution_seed_range, 1) AS execution_range,
       round(competence_seed_range, 1) AS competence_range,
       round(entrepreneurship_seed_range, 1) AS entrepreneurship_range
FROM model_capabilities
ORDER BY competence_seed_range DESC;'
```

Find diagnostic or superseded evidence and its exclusion rationale:

```bash
sqlite3 -header -column data/model-benchmarks.sqlite '
SELECT m.label, r.seed, r.integrity_status, r.quality_status,
       r.included_in_model_result, r.run_exclusion_reason,
       m.leaderboard_exclusion_reason
FROM benchmark_runs r JOIN models m USING (model_key)
WHERE m.leaderboard_eligible = 0 OR r.included_in_model_result = 0;'
```

Rebuild and verify after adding a source to the catalog:

```bash
python3 -m agent_world.benchmark_db build
python3 -m agent_world.benchmark_db verify
python3 -m agent_world.benchmark_db leaderboard
```

The builder writes atomically, verifies SQLite integrity, and records hashes of
the builder, source catalog, reports, usage ledgers, and manifests, plus the
effective date and sources for the USD rate card. It stores telemetry and
outcome evidence, not prompt or response bodies.
