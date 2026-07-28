# Participant v4 retrospective rescore

This applies the Participant v4 formulas to the preserved event ledgers of
every homogeneous GPT-5.3-Codex-Spark and GPT-5.4 run on record. No simulation
was re-run.

On this evidence the GPT-5.4 seed-11/41 pair is **certified with a declared
deviation**, and the Spark seed-11 trial is **provisional with declared
deviations**. The remaining runs are diagnostic.

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
| Spark | 11 | 50/50 | 71.46 | 30.22 | 0.00 | provisional (2 declared deviations) |
| Spark | 41 | 32/40 | 70.44 | 48.75 | 0.00 | diagnostic — quota-terminated |
| Spark | 11 | 34/40 | 72.45 | 43.74 | 0.00 | diagnostic — quota-terminated |

An aborted 1-tick GPT-5.4 run is omitted.

### Spark: audited 2026-07-26, promoted under an explicit override

Its complete 50-tick seed-11 run — the Saturday 2026-07-25 trial, artifacts
written 21:37 — ran at fingerprint `a79d5045…` (commit `60c4143`). Every
difference between that code state and current was examined:

| Difference | Binds? |
|---|---|
| `interface.py`: ore mechanics text | **Yes** — same one-line deviation accepted for GPT-5.4 |
| `world.py`: construction contributor shares | No — the run built **zero** structures, so the rule never fired |
| `world.py`: engine trade value removed from events | No — verified at `60c4143` itself, `_slim_event` exposed only tick/type/actor/message and `_slim_market_transaction` was already filtered to give/receive bundles |
| `rules.py`: `RESOURCE_VALUES` → `ACCOUNTING_VALUES` | No — rename and comments only, no value changed |
| `models.py`, `cli.py` | No — a comment and seed-validation text |
| `codex_brain.py` + `decision_failure.py`: contract validator | **Yes** — resolved by explicit override, below |

The validator does not change the prompt, so the model faced the same world.
What it changes is how a failed decision is attributed.

Spark logged two decision failures, at ticks 7 and 28:

```
Codex decision failed: Codex action arguments_json is invalid:
  Expecting value: line 1 column 1 (char 0)
```

That is the *production adapter's* own parse error. v4 normally requires an
independent validator to check the isolated payload before the adapter runs,
so that malformed model output (scored against the model) can be told apart
from an adapter rejecting valid output (which voids the trial). This trial
predates that validator and its usage ledger retained only `request_sha256`
and `request_payload_bytes`, so no response payload survives and the
attribution is unrecoverable.

**This was overridden by explicit owner decision on 2026-07-26.** The measured
sensitivity is 0.08 points — effective execution is 71.46 if both failures are
scored against the model and 71.54 if both are excluded, across 1,331
submitted actions — and Spark inference is usage constrained, so a full 50-tick
re-run is not a proportionate way to resolve a gap of that size.

State the residual risk plainly: if those two failures were adapter rejections
of contract-valid output rather than malformed model output, the harness
misbehaved during the trial and the run would normally be void. The evidence
does not exclude that. It is judged immaterial at this magnitude, not
disproven.

The override lives in `BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES` and matches on
model, seed, source fingerprint, **and the exact count of unverifiable
failures**. A rescore that produced a third such failure would stop matching
and the flag would return, so the entry cannot quietly widen to cover failures
nobody examined. Both deviations print in full on the leaderboard and in the
study manifest.

Promotion to replicated certification still requires a clean seed-41 run.

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
