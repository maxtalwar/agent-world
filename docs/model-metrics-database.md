# Simulation-run and model capability metrics database

The durable simulation evidence store is
[`data/model-benchmarks.sqlite`](../data/model-benchmarks.sqlite). The compact
[`model-leaderboard.md`](model-leaderboard.md) is intentionally only one
human-readable projection of its certified benchmark layer; benchmark
eligibility does not determine whether a run is admitted to the database.

The database is generated from the explicit source catalog in
[`data/run-sources.json`](../data/run-sources.json). This replaces the former
`data/model-benchmark-sources.json` name because the catalog now accepts every
simulation kind. The catalog alone is authoritative and sufficient to recreate
the generated SQLite file. It distinguishes benchmark trials, controlled
variants, experiments, and diagnostics while preserving every existing
inclusion or exclusion disposition.

The layering is deliberate: `runs` admits all final cataloged simulations;
`run_cohorts` describes each run's one or more model populations;
`benchmark_trials` declares certification and pooling eligibility; and
`experiments` groups runs under a question and factorial design. `model_results`
and `leaderboard` remain projections of rows explicitly included by the
benchmark layer. A run can therefore be useful evidence without being a
certified benchmark replication.

## What is stored

| Layer | Table/view | Important contents |
|---|---|---|
| Universal run | `runs` | Kind, experiment, seed, world/configuration, provenance, completion and integrity, global outcomes, usage, source paths and hashes, and experimental factors |
| Population | `run_cohorts` | One row per cohort, including model/provider/brain/effort, assigned agents, cohort outcomes and nullable scores, tokens, cost, latency, and retained raw metric/score trees |
| Benchmark certification | `benchmark_trials` | Protocol, suite, scoring revision, fingerprint, certification class, protocol compliance, and model-result inclusion/exclusion |
| Experiment | `experiments` | Study question, factor design, start, status, and notes |
| Model | `models`, `model_results`, `model_capabilities` | Existing benchmark-only rank eligibility, combined scores, seed ranges, survival, economic behavior, reliability, reasoning, cache, cost, and latency distributions |
| World tick | `tick_metrics` | Decisions per tick, token/cost totals, per-decision latency, and concurrent wall span |
| Decision | `decisions` | Run/cohort/agent/tick, end-to-end call latency, input/cache/output/reasoning tokens, cost, request size, provider response model, conversation state, and request hashes |
| Projection | `leaderboard`, `evidence` | The unchanged benchmark leaderboard and a flat all-kinds evidence query |

The model-result and cohort tables also retain the full frozen raw-metric and score trees
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
- `tick_metrics.concurrent_wall_span_per_deciding_agent_seconds` divides that
  tick's wall span by the number of distinct agents that actually requested a
  decision. Its model-level median and p95 are the default normalized world-tick
  comparison when populations differ or deaths reduce the active population.
- `tick_metrics.concurrent_wall_span_per_configured_agent_seconds` retains the
  same normalization against the run's configured starting population.
- `tick_metrics.concurrent_wall_span_per_worker_batch_seconds` divides by the
  number of concurrency waves implied by deciding agents and the run's worker
  limit. This helps distinguish a slow model from a run that simply queued more
  batches. Agent count and worker limits are stored alongside every result.
- `runs.usage_observed_span_seconds` runs from the earliest recorded
  call start to the final recorded call end. It is the best historical measure
  of whole-run elapsed time and includes any gaps between recorded decisions.
- `runs.wall_clock_seconds` is the manifest's start/end interval.
  For a resumed run it may describe only the last launcher segment, so it is
  retained as provenance rather than treated as authoritative total runtime.

Do not sum decision latency to estimate elapsed run time: agents decide
concurrently. Also do not describe world-tick-per-agent as individual response
latency—it is an amortized throughput measure, while
`latency_median_seconds` is the typical individual response. Retain both raw
world-tick latency and normalized latency: the raw value describes what the
user waited, while the normalized values support population-aware comparisons.
Median is the best quick “typical” number; p95 exposes the slow tail.

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

Compare population-aware world-turn speed:

```bash
sqlite3 -header -column data/model-benchmarks.sqlite '
SELECT label, configured_agents_min, configured_agents_max,
       global_max_workers_min, global_max_workers_max,
       round(tick_wall_span_median_seconds, 2) AS raw_tick_p50_seconds,
       round(tick_wall_per_deciding_agent_median_seconds, 2)
         AS tick_p50_seconds_per_deciding_agent,
       round(tick_wall_per_worker_batch_median_seconds, 2)
         AS tick_p50_seconds_per_worker_batch
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
SELECT e.models, r.seed, r.integrity_status, r.quality_status,
       bt.included_in_model_result, bt.run_exclusion_reason,
       m.leaderboard_exclusion_reason
FROM runs r
JOIN benchmark_trials bt USING (run_id)
JOIN run_cohorts rc USING (run_id)
JOIN models m ON m.model_key = rc.model
JOIN evidence e USING (run_id)
WHERE m.leaderboard_eligible = 0 OR bt.included_in_model_result = 0;'
```

Query all Luna evidence in one place—certified trials, the Max controlled
variant, and experiment cells. Competence is nullable where no benchmark score
tree exists, while cost and latency remain available from usage ledgers:

```bash
sqlite3 -header -column data/model-benchmarks.sqlite '
SELECT kind, models, seed, round(competence, 1) AS competence,
       round(api_list_cost_usd, 3) AS cost_usd,
       round(latency_median_seconds, 2) AS latency_p50_seconds,
       certification, factors_json
FROM evidence
WHERE lower(models) LIKE "%luna%"
ORDER BY kind, models, seed;'
```

Rebuild and verify after adding a source to the catalog:

```bash
python3 -m agent_world.benchmark_db build --catalog data/run-sources.json
python3 -m agent_world.benchmark_db verify
python3 -m agent_world.benchmark_db leaderboard
```

The builder writes atomically, verifies SQLite integrity, and records hashes of
the builder, source catalog, reports, usage ledgers, and manifests, plus the
effective date and sources for the USD rate card. It stores telemetry and
outcome evidence, not prompt or response bodies.

## Multiple protocol leaderboards

Model keys are protocol-specific for new v7 studies. Ranking is partitioned
by the catalog model suite; the leaderboard view exposes that suite. Use
`python3 -m agent_world.benchmark_db leaderboard --suite participant-v7`
for the current field, or participant-v6 for the historical comparison.
Unfiltered output renders separate protocol tables.

## V8 production projection (schema 4)

`run_cohorts` and `model_results` add nullable `capability` and `production`
fields. V8 populates these new fields; its legacy `competence`,
`entrepreneurship`, and `economic_productivity` fields remain null.
Historical rows retain their original named scores and numeric values.

The compatibility `leaderboard` view keeps its original columns.
`production_leaderboard` exposes the new score names and mean decision latency.
Use `python3 -m agent_world.benchmark_db leaderboard --suite participant-v8`
for the compact Model / Capability / Execution / Production / Cost/run /
Mean time/decision projection.

V8 costs include all unique recorded attempts. Latency groups those attempt
durations by resolved (run, tick, agent) decision, including retries while
excluding between-call quota waits. Missing or orphan timing makes the mean
unavailable. `decisions.committed` retains attempt disposition; raw attempt
durations and tick metrics remain available for diagnosis.
