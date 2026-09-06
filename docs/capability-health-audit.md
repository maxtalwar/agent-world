# Capability discrimination audit

Offline analysis of five ready v8.1 studies, seeds 11/41, with one newly
authorized high-effort experiment pending. No scoring or world changes were
applied to the benchmark. See [hashed data and calculations](capability-health-audit.json)
and [the high-effort probe](capability-high-effort-probe.md).

## Findings

The source used for these studies only decreases health in survival resolution.
There is no healing action. Food, water, rest and shelter prevent future damage;
they do not undo prior damage. All five cohorts remain well below a 100-health
ceiling. Sol keeps 20/20 agents alive and scores 77.605; the near-tie between
5.5 and Mini is therefore not evidence that the entire field has saturated.

| Model | Capability | Alive agent-ticks % | Health conditional on being alive | Damage-free living ticks % | Final survivors /20 | Reasoning/call | Zero-reasoning calls % |
|---|---:|---:|---:|---:|---:|---:|---:|
| gpt-5.6-sol | 77.61 | 100.00 | 77.61 | 76.50 | 20 | 338.3 | 0.00 |
| gpt-5.6-terra | 66.05 | 89.50 | 73.80 | 60.25 | 11 | 279.0 | 11.08 |
| gpt-5.6-luna | 64.12 | 88.92 | 72.11 | 56.67 | 8 | 507.1 | 0.00 |
| gpt-5.5 | 56.43 | 80.67 | 69.96 | 48.25 | 7 | 77.1 | 81.04 |
| gpt-5.4-mini | 55.90 | 75.42 | 74.12 | 46.08 | 6 | 1327.3 | 0.00 |

Alive agent-ticks use states after each completed tick, with the original
population denominator. This differs slightly from decision counts because
an agent can make a decision and then die during that tick. Damage-free living
ticks require the agent to survive the tick and incur no survival damage;
this is an exploratory diagnostic, not a proposed leaderboard replacement.

Capability exactly equals alive-agent-tick fraction times mean health on those
living ticks. For 5.5, 0.8067 * 69.96 = 56.43; for Mini, 0.7542 * 74.12 = 55.90.
5.5 keeps agents alive longer, but their conditional health is lower. These
advantages cancel in the average. Their damage-free living percentages are
also close, 48.25 versus 46.08, suggesting similar realized needs management
rather than a hidden large survival-performance gap. Conditional survivor
health alone would reward survivor selection and must not replace Capability.

## What differs from v6

V6 competence was a geometric mean of effective execution, survival continuity
and living-accessible material outcome. Survival continuity itself combined
alive decision exposure and endpoint health. It was not the current mean-health
construct. The old larger gap can partly reflect achievements intentionally
removed from Capability. In v8.1, 5.5 produces about 34% more than Mini and builds
six farms plus one storage versus no structures; that only affects Capability
to the extent it improves health. Do not reintroduce inventory/wealth weights
merely to recreate a preferred model ranking.

The July journal reports 5.5 reasoning around 19 tokens/decision in v6, and a
short prompt probe showing higher effort increases reasoning. Current recorded
usage confirms low allocation persists: mean 77.1 tokens/call, 81.0% zero, versus
Mini 1327.3 with no zero-reasoning calls. This supports a hypothesis of insufficient
deliberation, not a proven causal explanation. The old journal phrase
“lost ... because of it” was stronger than those observational comparisons
and prompt probes alone establish. A high-effort 60-tick seed-11 experiment
now tests the same 5.5 model/source/world against its existing medium baseline.

## Irreversibility and time weighting

Let L_t be actual capped health lost by the original population during engine
tick t (zero-indexed). With no healing, mean health equals:
100 - sum(L_t * (60 - t)) / (10 * 60).
The audit verifies this identity against every recorded health trajectory.
Thus equal weighting of health snapshots still gives early damage more lasting
consequences. A 20-point injury to one agent after completed tick 10 reduces
that agent’s 60-tick mean by 17 points, even if it behaves perfectly thereafter.
This is a real long-horizon consequence, but the world gives no recovery task
through which subsequent competent behavior could reverse it.

First-season scores are 98–100 for all five models. Much of the early benchmark
has little discrimination. Later collapse does distinguish Sol from the rest,
but both 5.5 and Mini have final-season mean population health around 10–11.
Simply lengthening an irreversible-damage world can create a shared extinction
floor; shortening it can miss seasonal preparation. Neither is an automatic fix.

## Healing sensitivity experiment

A stylized 60-step health model compares perfect behavior, one 20-point injury
at step 10 followed by stable behavior, and one point of damage every step
from step 10. Recovery policies are no recovery, +2 on damage-free ticks only,
and +2 every tick. Health is capped at 100 and death is absorbing. These are
toy fixed-policy trajectories, not full-world simulations or model predictions.

| Policy | No healing | Heal on damage-free ticks | Heal every tick |
|---|---:|---:|---:|
| no mistakes | 100.00 | 100.00 | 100.00 |
| early damage then stable | 83.00 | 98.17 | 98.50 |
| persistent damage | 77.90 | 77.90 | 100.00 |

Conditional recovery distinguishes a recovered one-off mistake from continuing
mismanagement. Unconditional easy recovery entirely hides persistent small
damage in this example. Healing can therefore improve or worsen discrimination
depending on its constraints. Both worlds retain a bounded-score ceiling when
all models maintain perfect health; healing alone does not solve eventual
benchmark saturation.

## Recommended sequence

1. Keep current scores fixed while the high-effort probe tests whether 5.5’s
   realized behavior improves with increased deliberation.
2. Prototype a separate v9 recovery mechanic: slow healing only when fed,
   hydrated, rested and protected, with an action/resource opportunity cost.
   Start with one transparent mechanism; no free resurrection or automatic
   regeneration that offsets continuing deprivation.
3. Treat medicine as a later production-chain candidate if it creates real
   tradeoffs in inputs, labor, distribution and timing. It should not be a
   mandatory score token or the only way a capable self-sufficient agent wins.
4. Validate controlled behaviors before comparing model rankings: neglect,
   reactive subsistence, seasonal preparation, and recovery after a common
   setback. Check that trivial rest or healing loops cannot reach perfect scores.
5. If strong agents then saturate, vary a small predeclared set of world
   challenges and aggregate the same outcome measure across them. This can
   broaden tested capability without adding leaderboard columns or mixing
   Execution and Production back into Capability.

## Scope and validation

All existing-study job readiness, source provenance and usage coverage were
checked. The audit validates monotonic health, the loss-weighting identity,
health-count agreement and complete reasoning telemetry. Source hashes and
per-seed distributions are in the JSON. The script runs without model calls.
Health-only diagnostics are not silently admitted as new benchmark results.
No healing design or altered Capability formula has been implemented.
