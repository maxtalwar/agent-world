# V8 capability and execution scoring components

Implemented for the v8 design; enterprise and the final recipe remain pending.
No provider calls were made and no historical report or leaderboard was changed.
The score component version is outcome-execution-v1.

## What the review does

First define the observable property, then test counterexamples, then rescore
saved evidence with original provenance. Do not tune formulas to favor a model
or to reproduce the old ranking. Scoring reviews are counterfactual analyses,
not new v8 benchmark trials.

The review includes fourteen completed worlds: all eight Luna factorial
worlds plus both admitted seeds of historical Luna medium, Luna Max, and
Fable 5. An excluded historical Fable provider-failure continuation was rejected
by the integrity gate; only its catalog-admitted recovered counterpart is used.

## Capability

Rename competence to capability in the new design. Measure the society's
ability to sustain its original population alive and healthy. This is an
operational definition of capability within Agent World, not general intelligence.

For N original agents, let H(t) be their combined health after completed tick t,
divided by N. Each agent's maximum health is 100; deceased agents contribute
zero for every subsequent tick. This makes H(t) a 0–100 population-health score.

A = average H(t) across all completed ticks 1 through T.
L = average H(t) across the last twelve completed ticks.
Capability = sqrt(A * L).

The final window is one season in the proposed 50-tick world. The implementation
accepts an explicit tail length for other recipes; this is a scoring parameter,
not inferred from model behavior. Historical review windows use one recorded
season and cannot be pooled when horizons/windows differ.

Why these choices:
- Full-horizon health values maintaining agency throughout the experiment.
- Final-season health emphasizes continued resilience, not just a good start.
- The geometric mean requires both without imposing a single-tick cliff.
- Dead agents remain in the denominator. Survivor-only averages are forbidden.
- Initial health at tick zero is unearned and is not included.
- Execution, trade, prices, wealth, and enterprise scores do not enter capability.

A society that is healthy early and then completely extinct for the final
season scores zero. A society that dies on the last tick retains credit for
earlier final-season survival; extinction and endpoint health remain visible
in the detailed results. Wealth and productive capital are excluded directly:
they benefit capability only when they actually sustain health during the
measured horizon. Economic accomplishments will be assessed by enterprise.

Limitations: health is narrower than a complete description of agency. Economic
investment with benefits beyond tick 50 is not credited here; that belongs in
enterprise or a longer-horizon recipe. The final-season emphasis is an explicit
design preference, not a statistically discovered optimal weight.

## Execution

Execution = 100 * fully executable decisions / resolved decisions.

A decision passes if its output contract is valid and none of its proposed
actions or messages produces an invalid_action event. Resource contention is
excluded: a feasible plan losing a simultaneous race is not an execution error.
Provider, quota, harness, or ambiguous boundary failures make evidence
unscorable rather than becoming fictional bad decisions.

Each agent decision counts once:
- One invalid item fails the complete plan; there is deliberately no partial
  credit in the headline metric.
- Adding easy valid items cannot dilute an invalid item.
- A valid wait or deliberate empty/no-op decision can execute perfectly.
- Activity, communication volume, and the old purposeful-action list give
  no bonus. Strategically disastrous but executable behavior can score 100.
- More complicated plans face more opportunities to fail. This metric measures
  complete-plan reliability; per-action feasibility remains a useful diagnostic.

This separates technical execution from strategic outcomes. A model that
correctly rests until everybody dies can have execution 100 and capability 0.
These percentages must not be compared numerically with old execution scores.

## Offline review results

All values below apply the new components to old evidence, not v8 trials.
Raw additive numerators and denominators are pooled before scoring.

| Original evidence | New execution | New capability |
|---|---:|---:|
| Luna low, board off | 59.55 | 28.87 |
| Luna low, board on | 55.91 | 30.85 |
| Luna high, board off | 68.64 | 41.59 |
| Luna high, board on | 60.47 | 41.80 |
| Historical Luna medium v6 | 60.07 | 36.33 |
| Historical Luna Max v6 | 74.48 | 53.48 |
| Historical Fable 5 v6 | 72.20 | 73.63 |

The most informative change is the high-effort Luna board comparison. The new
capability metric nearly ties the two conditions. Board on has better
full-horizon health (72.571 versus 67.550) but worse final-season health
(24.071 versus 25.613). Removing execution and terminal wealth from capability
reveals that offset. The previously reported farm, terminal-value, and endpoint
health advantages of board off remain factual; they are not all measures of
sustained health. The lower board-on execution also becomes clearer when
additional activity cannot boost purposeful-tick credit.

This does not reverse the user's board-removal decision, but narrows the claim:
the board shifted investment and timing; these two seeds do not establish a
large negative effect on sustained population health at high effort.

## Validation and reproduction

tests/test_outcome_scoring.py tests outcome independence, legitimate rest,
valid catastrophic strategy, action padding, contention, health monotonicity,
late recovery versus collapse, fixed population denominators, raw pooling,
missing and conflicting evidence, and output/provider failure separation.
The derivation requires full living-agent observation/response coverage, exact
death evidence, a terminal snapshot, and a run_completed event at the horizon.

Run from the repository root, with a new output destination:
python3 scripts/review-outcome-scores.py --studies configs/analysis/v8-outcome-review.json --out /tmp/v8-review.json

[v8-outcome-scoring-review.json](v8-outcome-scoring-review.json) retains original
recipe/source identities, source hashes, per-seed counts, and old/new scores.
The final v8 recipe is not registered until enterprise is designed; these
implemented components can then be composed without changing old recipes.
