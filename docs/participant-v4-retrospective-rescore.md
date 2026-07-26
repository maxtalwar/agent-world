# Participant v4 retrospective rescore

This applies the finalized Participant v4 formulas to the preserved event
ledgers of every homogeneous GPT-5.3-Codex-Spark and GPT-5.4 run recorded
under Participant v1, v2, and v3. No simulation was re-run.

**Every result here is diagnostic only.** None is a provisional or certified
v4 benchmark, for reasons given under [Why these cannot be promoted](#why-these-cannot-be-promoted).
They are recorded because they are the only v4-shaped evidence that exists,
and because rerunning seven full model trials to recover numbers already
latent in the ledgers is not a good use of budget.

## Method

Each run's `run.jsonl`, `run-snapshot.json`, and `run-report.json` were passed
to the current `build_benchmark_results`. Every v4 metric is derived from the
raw event ledger and terminal snapshot rather than from stored v1/v2/v3
aggregates, so nothing depends on the superseded scoring. The two complete
GPT-5.4 seeds were pooled by summing raw numerators and denominators before
scoring, which is the protocol's own aggregation rule.

This is possible only because the ledgers retain the underlying events:
per-action outcomes for purposeful activity, and `accept_trade`, `gift`,
`pay_access_fee`, and `harvest` records for enterprise supply.

## Per-run diagnostic results

| Model | Seed | Ticks | Effective execution | Sustained competence | Entrepreneurial agency |
|---|---:|---:|---:|---:|---:|
| GPT-5.4 | 41 | 50/50 | 88.35 | 70.85 | 66.60 |
| GPT-5.4 | 11 | 50/50 | 85.27 | 72.13 | 92.44 |
| GPT-5.4 | 11 | 40/40 | 86.14 | 70.35 | 54.66 |
| Spark | 11 | 50/50 | 71.46 | 30.22 | 0.00 |
| Spark | 41 | 32/40 | 70.44 | 48.75 | 0.00 |
| Spark | 11 | 34/40 | 72.45 | 43.74 | 0.00 |

The 40-tick GPT-5.4 row is the former v2 trial; the two Spark rows under 40
ticks are the quota-terminated v1 trials. An aborted 1-tick GPT-5.4 run is
omitted.

## Pooled GPT-5.4, seeds 11 and 41

Both required seeds completed 50 ticks with clean integrity and full usage
coverage, so they pool under the standard rule.

| Score | Pooled | Seed 11 | Seed 41 | Range |
|---|---:|---:|---:|---:|
| Effective execution | **86.77** | 85.27 | 88.35 | 3.08 |
| Sustained competence | **71.86** | 72.13 | 70.85 | 1.28 |
| Entrepreneurial agency | **79.87** | 92.44 | 66.60 | 25.84 |
| Economic productivity (diagnostic) | 126.31 | 158.25 | 94.38 | 63.87 |

Pooled components: action feasibility 87.7, purposeful activity 85.8,
enterprise supply 10.1 per 100 agent-ticks, net value created 25.3 per 100
agent-ticks.

## What the new construct shows

**Entrepreneurial agency is by far the noisiest of the three scores.** Across
GPT-5.4's two seeds, execution varies by 3.08 and competence by 1.28, but
entrepreneurship varies by 25.84 — an eightfold wider spread than execution.
The third GPT-5.4 run reinforces it: at a 40-tick horizon the same model and
seed produced 54.66. Execution and competence are stable enough that a single
seed says something; entrepreneurship on one seed does not. This is direct
support for the certified-report range requirement, and an argument for
treating any single-seed provisional entrepreneurship figure as indicative
only.

**GPT-5.4 builds capital but has almost no customers.** Its enterprise supply
is 92 units of own capital output against 9 units of net goods supplied to
other agents, and zero service income. It understands farms; it does not
operate a market. That is a specific, actionable finding the old
initiative-count metric could not express — the same runs logged 13 to 18
venture initiatives, which looked like commerce but was mostly unaccepted
offers.

**Spark scores zero entrepreneurship in all three runs, for two different
reasons.** In the seed-11 runs it created no net value: its cohort ended below
its starting endowment. In the quota-stopped seed-41 run it *did* create value
(74 units, a 92.5 component score) but supplied nothing to anyone and built no
producing capital, so the geometric mean is still zero. That is the intended
semantics — accumulating materials alone is not entrepreneurship — and it is
the case the old formula would have scored positively.

**Neither model used credit or priced access at all.** Net service income is
zero in all seven runs.

## How these differ from the previously published numbers

| Run | Old score | New score | Cause |
|---|---|---|---|
| Spark v3 seed 11, execution | 66.64 | 71.46 | v3 reported feasibility alone; v4 adds a 76.63% purposeful-activity term |
| Spark v3 seed 11, competence | 32.68 | 30.22 | endowment revalued 80 → 135, so the 3x material target rose 240 → 405 |
| GPT-5.4 v2 seed 11, execution | 86.54 | 86.14 | feasibility unchanged; purposeful activity 85.75% barely moves the mean |
| GPT-5.4 v2 seed 11, competence | 78.45 | 70.35 | same endowment revaluation |
| GPT-5.4 v2 seed 11, entrepreneurship | 22.17 | 54.66 | wholly different construct; not comparable |

The endowment revaluation is an accounting-table consequence, not a change in
what agents held. Coin is valued at exactly 19/8 units so that minting
conserves value, which raises the starting bundle's recorded worth.

## Why these cannot be promoted

Three independent reasons, any one of which is sufficient:

1. **The agent-facing world changed.** Commit `a49c7d5` altered the mechanics
   text agents read — ore is no longer described as a "high-value raw
   material" — so v4 prompts differ from the prompts these models actually
   received.
2. **The economy changed.** The same commit replaced value-weighted
   construction contributor shares with recipe-completion credits, which
   changes dividend payouts. This is a mechanical difference in how the world
   behaves, not a reporting difference.
3. **Two runs use the wrong horizon.** The v2 GPT-5.4 trial and both v1 Spark
   trials are 40-tick or quota-terminated, and v4 requires a complete 50-tick
   run.

The first two apply even to the complete 50-tick GPT-5.4 pair, whose only
protocol flags are `benchmark_code_fingerprint_mismatch` and
`benchmark_protocol_not_declared`. Those flags are correct: the trial settings
match v4 exactly, but the code that produced the behavior does not.

A genuine v4 leaderboard needs fresh runs. What this rescore establishes is
that the v4 formulas separate these two models cleanly on all three axes, that
the anchors put a strong model mid-scale with headroom rather than at a floor
or a ceiling, and that entrepreneurship needs both required seeds before it
means anything.
