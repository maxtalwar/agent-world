# Participant v4 retrospective rescore

This applies the Participant v4 formulas to the preserved event ledgers of
every homogeneous GPT-5.3-Codex-Spark and GPT-5.4 run on record. No simulation
was re-run.

The GPT-5.4 seed-11/41 pair is **certified with a declared deviation** on this
evidence. Everything else here is diagnostic.

## Method

Each run's `run.jsonl`, `run-snapshot.json`, and `run-report.json` were passed
to the current `build_benchmark_results`. Every v4 metric derives from the raw
event ledger and terminal snapshot rather than from stored v1/v2/v3 aggregates,
so nothing depends on superseded scoring. The two complete GPT-5.4 seeds were
pooled by summing raw numerators and denominators before scoring, which is the
protocol's own aggregation rule.

This is possible only because the ledgers retain the underlying events:
per-action outcomes for purposeful activity, and `accept_trade`, `gift`,
`pay_access_fee`, and `harvest` records for enterprise supply.

Certified artifacts:
`runs/benchmarks/gpt-5-4-participant-v4-certified-20260726/`.

## Certified: GPT-5.4, seeds 11 and 41

| Score | Pooled | Seed 11 | Seed 41 | Range |
|---|---:|---:|---:|---:|
| Effective execution | **86.77** | 85.27 | 88.35 | 3.08 |
| Sustained competence | **71.86** | 72.13 | 70.85 | 1.28 |
| Entrepreneurial agency | **23.84** | 25.16 | 21.72 | 3.44 |
| Economic productivity (diagnostic) | 126.31 | 158.25 | 94.38 | 63.87 |

Pooled components: action feasibility 87.7, purposeful activity 85.8,
enterprise supply 0.9 per 100 agent-ticks, net value created 25.3 per 100
agent-ticks, own capital output 92 units (reported, not scored).

### The declared deviation

Both seeds ran under `participant-v3` at source fingerprint `3b4d6952…`. Three
things changed between that code and v4. Only one survives audit:

| Difference | Binds? |
|---|---|
| Static context described ore as a "high-value raw material" rather than as smeltable into an ingot | **Yes** — one line of a 6,430-character static context |
| Construction contributor shares moved from value-weighted to recipe-completion credits | No — no structure in either run had more than one contributor, so the rule never fired |
| Engine-declared trade values removed from events and market history | No — agents never saw them. `_slim_market_transaction` was already filtered to give/receive bundles, and `_slim_event` never exposed event data at all |

Trial settings, horizon, integrity status, and usage coverage all match v4
exactly. The surviving deviation is recorded in
`BENCHMARK_ACCEPTED_PRIOR_TRIALS`, printed in full on the leaderboard, and
reflected in the status label.

## Diagnostic: all rescored runs

| Model | Seed | Ticks | Exec | Comp | Entre | Status |
|---|---:|---:|---:|---:|---:|---|
| GPT-5.4 | 41 | 50/50 | 88.35 | 70.85 | 21.72 | certified (declared deviation) |
| GPT-5.4 | 11 | 50/50 | 85.27 | 72.13 | 25.16 | certified (declared deviation) |
| GPT-5.4 | 11 | 40/40 | 86.14 | 70.35 | 24.45 | diagnostic — 40-tick horizon |
| Spark | 11 | 50/50 | 71.46 | 30.22 | 0.00 | diagnostic — unverifiable failure attribution |
| Spark | 41 | 32/40 | 70.44 | 48.75 | 0.00 | diagnostic — quota-terminated |
| Spark | 11 | 34/40 | 72.45 | 43.74 | 0.00 | diagnostic — quota-terminated |

An aborted 1-tick GPT-5.4 run is omitted.

### Why Spark is not promoted (audited 2026-07-26)

Its complete 50-tick seed-11 run — the Saturday 2026-07-25 trial, artifacts
written 21:37 — ran at fingerprint `a79d5045…` (commit `60c4143`), which is
*older* than the GPT-5.4 pair's. Every difference between that code state and
current was examined:

| Difference | Binds? |
|---|---|
| `interface.py`: ore mechanics text | **Yes** — same one-line deviation as GPT-5.4 |
| `world.py`: construction contributor shares | No — the run built **zero** structures, so the rule never fired |
| `world.py`: engine trade value removed from events | No — verified at `60c4143` itself, `_slim_event` exposed only tick/type/actor/message and `_slim_market_transaction` was already filtered to give/receive bundles |
| `rules.py`: `RESOURCE_VALUES` → `ACCOUNTING_VALUES` | No — rename and comments only, no value changed |
| `models.py`, `cli.py` | No — a comment and seed-validation text |
| `codex_brain.py` + `decision_failure.py`: independent contract validator | **Yes, and blocking** |

The validator does not change the prompt, so the model faced the same world.
What it changes is how a failed decision is attributed, and that is where the
run fails.

Spark logged two decision failures, at tick 7 and tick 28:

```
Codex decision failed: Codex action arguments_json is invalid:
  Expecting value: line 1 column 1 (char 0)
```

That message is the *production adapter's* own parse error. v4 requires an
independent validator to check the isolated payload against the declared
contract before the adapter runs, precisely so that two very different events
can be told apart: a model emitting invalid JSON, which is scored against the
model, and an adapter rejecting valid output, which invalidates the trial. The
run predates that validator, and its usage ledger retains only
`request_sha256` and `request_payload_bytes` — no response payload survives.
The attribution is therefore unrecoverable, and the cohort raises
`unverified_model_output_attribution`.

Allowlisting the fingerprint would not help. That flag is raised per cohort,
independently of the protocol and fingerprint checks, so it would survive.

The score impact is negligible — scoring both failures against the model gives
effective execution 71.46, excluding them entirely gives 71.54 — but v4 treats
an unattributable failure as disqualifying regardless of magnitude, because the
question is whether the harness was behaving, not how many points moved. The
v3 suite carried a hardcoded exemption for exactly this run
(`_legacy_spark_attribution_exception`); v4 deliberately dropped it, and this
audit does not reinstate it.

**Path to a Spark v4 number:** one fresh seed-11 run under `participant-v4`
earns provisional status. That is a single trial, not a re-run of everything.

## Model comparison

| | GPT-5.4 (11+41, 50t) | Spark (11, 50t) |
|---|---:|---:|
| Effective execution | 86.77 | 71.46 |
| Sustained competence | 71.86 | 30.22 |
| Entrepreneurial agency | 23.84 | 0.00 |
| Economic productivity | 126.31 | 0.00 |
| Enterprise supply | 9.0 | 3.0 |
| — net goods to others | 9.0 | 3.0 |
| — net service income | 0.0 | 0.0 |
| Own capital output (reported) | 92.0 | 0.0 |
| Net value created | 252.6 | 0.0 |

## What the evidence shows

**Neither model trades.** Across the three complete 50-tick runs, 22 trade
offers produced **three** accepted trades in total. Enterprise supply rates are
0.6 to 1.0 per 100 agent-ticks against a 20-per-100 anchor. GPT-5.4's
entrepreneurial agency of 23.84 is almost entirely carried by value creation;
its commerce term is 4.5 out of 100. This is the headline finding, and it is
the one the old initiative count actively obscured — those same runs logged 13
to 18 "venture initiatives" that look like commerce but were overwhelmingly
unaccepted offers.

**GPT-5.4 builds capital instead.** 92 units of own capital output against 9
units supplied to other agents. It understands farms; it does not operate a
market. Capital output is reported but not scored as supply, because those
goods stay in cohort inventory and net value creation already counts them.

**Spark scores zero entrepreneurship in all three runs, for two different
reasons.** In the seed-11 runs it created no net value at all — its cohort
ended below its starting endowment. In the quota-stopped seed-41 run it *did*
create value (74 units, a 92.5 component score) but supplied nothing and built
no producing capital, so the geometric mean is still zero. Accumulating
materials alone is not entrepreneurship.

**Neither model used credit or priced access.** Net service income is zero in
all six runs.

**Score stability.** Across GPT-5.4's two seeds, execution varies by 3.08,
competence by 1.28, and entrepreneurship by 3.44 — all tight. The uncapped
economic-productivity diagnostic is the volatile one, varying by 63.87
(158.25 against 94.38). Terminal wealth is strongly world-dependent; the
bounded and geometrically-combined scores are not. Read the productivity
diagnostic with the seed range in view, never from one seed alone.

## How these differ from previously published numbers

| Run | Old | New | Cause |
|---|---|---|---|
| Spark v3 s11, execution | 66.64 | 71.46 | v3 reported feasibility alone; v4 adds a 76.63% purposeful-activity term |
| Spark v3 s11, competence | 32.68 | 30.22 | endowment revalued 80 → 135, so the 3x material target rose 240 → 405 |
| GPT-5.4 v2 s11, execution | 86.54 | 86.14 | feasibility unchanged; purposeful activity 85.75% barely moves the mean |
| GPT-5.4 v2 s11, competence | 78.45 | 70.35 | same endowment revaluation |
| GPT-5.4 v2 s11, entrepreneurship | 22.17 | 24.45 | wholly different construct; the similarity is coincidental |

The endowment revaluation is an accounting-table consequence, not a change in
what agents held. Coin is valued at exactly 19/8 units so that minting
conserves value, which raises the starting bundle's recorded worth.
