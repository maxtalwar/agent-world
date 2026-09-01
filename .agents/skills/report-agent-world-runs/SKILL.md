---
name: report-agent-world-runs
description: Generate an evidence-backed performance report for completed Agent World benchmark trials or ordinary experiment runs. Score the completed run and compare it with equivalent evidence when relevant. Use only for interpreting completed run evidence and reporting how runs performed; not for launching, monitoring, setup, engineering, generic analysis, or general model selection.
---

# Report Agent World Runs

Turn completed run evidence into an accurate, readable performance report.
Ground every conclusion in repository artifacts rather than chat history,
filenames, startup manifests, or partial output.

## Require report-ready evidence

- For a benchmark study, read `docs/benchmark-run-protocol.md` and inspect the
  study manifest's `analysis_readiness` block before interpreting performance.
- For an ordinary experiment, read `docs/agent-world-experiment-runs.md` and
  confirm the run reached its intended terminal state with the evidence needed
  for the requested claims.
- If finalization, provenance, usage accounting, or required transfer
  accounting is incomplete, state the exact gap. Use the appropriate run skill
  to finish it only when the user asks.
- Already cataloged historical benchmark evidence may predate
  `analysis_readiness`; its verified catalog and database admission are the
  durable substitute.

## Assign the right scores

- Give every completed ordinary run applicable diagnostic scores. A run does
  not need benchmark intent to receive scores and useful interpretation.
- Preserve evidence class: certified, provisional, controlled variant,
  diagnostic experiment, superseded, excluded, or invalid. Never turn a
  regular run into benchmark evidence merely because it uses seed 11 or
  resembles a participant configuration.
- Use the repository's versioned scoring and reporting tools. Do not average
  rounded seed scores, pool mismatched protocols, or invent a benchmark score
  for a world whose mechanics make that score inapplicable.
- When a standard score is inapplicable, report run-native outcome and
  reliability metrics and explain the limitation rather than omitting
  evaluation altogether.

## Choose comparable evidence

- For admitted benchmark comparisons, start with
  `data/model-benchmarks.sqlite`; read `docs/model-metrics-database.md` for
  schema semantics and maintained queries. Verify it with
  `python3 -m agent_world.benchmark_db verify` before relying on it.
- Use `data/run-sources.json` to locate a cataloged run's report, usage ledger,
  manifest, integrity status, and hashes. For an unadmitted experiment, start
  from its manifest and exact run artifacts.
- Compare ordinary runs only with genuinely equivalent evidence. Check world
  preset and mechanics, scoring version, horizon, population, seed strategy,
  model and effort, connector or harness condition, and experimental treatment.
  If a useful comparison is imperfect, label the mismatch beside the claim.
- Consult `docs/insights.md` for known behavioral and harness caveats, then
  follow its evidence pointers when a claim needs confirmation.

## Interpret carefully

1. State the comparison frame and evidence class.
2. Separate model-output, provider, quota, harness, and engine failures.
3. Interpret latency using the definitions in
   `docs/model-metrics-database.md`; individual decision latency, tick wall
   span, normalized throughput, and whole-run elapsed time are different
   quantities.
4. Describe the economy visible in the ledger: survival, production, capital
   formation, trade and services, transfers, institutions, specialization, and
   the strongest evidence-backed stories of coordination or entrepreneurship.
5. Distinguish observed facts, calculations, and interpretation. Cite exact
   local reports, manifests, ledgers, or database queries for non-obvious
   claims.

## Present the report

- Lead with the result and the scores. For a model comparison, use a compact
  table with the nearest genuinely comparable runs and the material score,
  integrity, cost, latency, and coverage columns.
- Label simulated leaderboard placement as simulated and never insert an
  unadmitted result into the canonical table.
- Scale depth to information value. A rich or surprising result merits
  behavioral evidence; a weak, invalid, or uneventful result can be concise
  while still explaining why.

## Maintain durable benchmark results

When the completed evidence is a new or corrected durable benchmark result,
update `data/run-sources.json`, rebuild and verify
`data/model-benchmarks.sqlite`, and regenerate the compact projection in the
same scoped change:

```bash
python3 -m agent_world.benchmark_db build --catalog data/run-sources.json
python3 -m agent_world.benchmark_db verify
python3 -m agent_world.benchmark_db leaderboard
```

Run the relevant tests. Follow `AGENTS.md` for commits, pushes, isolated
model-backed runs, quota handling, and the evidence bar for
`docs/insights.md`.

## Workflow boundary

This skill reports on completed evidence. Use `$run-agent-world-benchmark`
for benchmark launch, resume, monitoring, or finalization, and
`$run-agent-world-experiment` for ordinary runs and harness tests. Do not use
this skill for setup, implementation work, generic benchmark engineering, or
questions that merely contain words such as analysis, performance, or model.
