# Healing versus matched controls — 2026-09-07

Update: Gemini has since completed both seeds. The [full damage/recovery investigation](regeneration-damage-investigation.md) supersedes the partial Gemini comparison below and qualifies the earlier recommendation to adopt healing.

Batch: `health-regeneration-expanded-20260907`. Handoff: [pilot](regeneration-expanded-pilot.md). Source context: `.worktrees/health-regeneration`; treatment commit `9f296668f779fa281e269da98f73c1683e45b467`. Diagnostic only; no leaderboard admission.

All eight Codex treatment cells and their eight controls completed 60 ticks with clean decision quality and 100% usage-record coverage. Mini finalization audited once: both manifests completed, reports/usage/checkpoints present, no LLM failures. Mini manifests label resolved identity unknown, while report usage resolves gpt-5.4-mini; preserve this metadata discrepancy. World config differences are only the three regeneration settings. Controls precede treatments, so model/provider drift and stochastic behavior are not eliminated.

All health percentages retain dead original-population slots at zero. Values below come from raw report numerators, not averaged rounded scores.

| Model | Seed | Health off -> on | Tail off -> on | Final health off -> on | Survivors off -> on | Production off -> on | HP restored |
|---|---:|---:|---:|---:|---:|---:|---:|
| sol | 11 | 73.95 -> 86.22 | 38.12 -> 59.71 | 36.50 -> 65.50 | 10 -> 9 | 180.67 -> 160.83 | 168 |
| sol | 41 | 81.26 -> 85.66 | 47.04 -> 63.95 | 47.00 -> 71.70 | 10 -> 10 | 223.83 -> 167.83 | 214 |
| terra | 11 | 67.91 -> 79.39 | 23.57 -> 53.17 | 19.50 -> 58.00 | 6 -> 9 | 179.00 -> 150.00 | 161 |
| terra | 41 | 64.19 -> 73.27 | 11.61 -> 29.46 | 10.30 -> 26.60 | 5 -> 9 | 151.00 -> 138.83 | 100 |
| luna | 11 | 61.22 -> 72.48 | 18.19 -> 35.33 | 13.10 -> 30.50 | 5 -> 7 | 104.83 -> 111.83 | 41 |
| luna | 41 | 67.02 -> 66.48 | 9.14 -> 20.73 | 3.50 -> 20.70 | 3 -> 7 | 111.67 -> 111.50 | 58 |
| mini | 11 | 55.28 -> 60.59 | 13.58 -> 25.71 | 10.30 -> 25.10 | 3 -> 5 | 82.00 -> 88.83 | 60 |
| mini | 41 | 56.52 -> 64.39 | 6.85 -> 16.61 | 5.80 -> 17.70 | 3 -> 6 | 91.50 -> 102.33 | 54 |

Mean Sol-minus-model full-horizon health gaps (off -> on):
- terra: 11.56 -> 9.61 percentage points.
- luna: 13.49 -> 16.46 percentage points.
- mini: 21.71 -> 23.45 percentage points.

Regeneration does not uniformly widen discrimination: the Sol-Terra gap narrows, while Sol-Luna and Sol-Mini gaps widen. Terra gains 3/4 survivors and Luna gains 2/4, whereas Sol loses one survivor in seed 11. Luna seed 41 slightly loses full-horizon health despite gaining four survivors and improving tail health. These are behavioral outcomes with clean harness evidence, not proof of a general model ordering. Keep the recipe unchanged pending design review; improved aggregate health alone is insufficient. No cross-provider conclusion is made.

[Detailed evidence](regeneration-expanded-results.json) records exact source paths, provenance, per-agent restored health/max qualification streak, food/water/energy threshold failures, damage checks, death timing, execution and reliability. Failure categories overlap. Standard self-declared transfer accounting applies; the supplementary comparison below includes API-equivalent cost.

The arithmetic scoring check gives ten survivors at 20 HP a 20% original-population endpoint score versus 10% for one survivor at 100 HP among ten original agents. This confirms the intended population denominator; it is not a new model run.

Validation: baseline database verification passed (87 runs, integrity ok). All six existing `test_health_regeneration.py` unittest checks passed in the supplied source worktree: checkpoint streak, damage/death, disabled behavior, rate sweep, stability/cap/prompt, post-decay thresholds and shortage reset. All 16 evidence rows and report paths validated.


## Decision-oriented comparison of all healing runs

This covers all five managed healing studies: Sol, Terra, Luna, Mini, and
Gemini 3.7 Flash. The first four completed both seeds; Gemini remains partial
at 44/60 in both seeds at this analysis. Every control uses the matching model,
medium reasoning, seed, initial ten-agent population and v8.1 world configuration.
The world configuration differs only in the three healing fields. Treatments
also tell agents the new rule; these are fresh decisions, not replayed controls.
Thus the comparison includes behavior changes and stochastic trajectories.

The health score is mean health across all 60 ticks and all originally assigned
agents, with dead agents contributing zero. Final population health is measured
at tick 60 with the same denominator. Survivors below are totals across two
worlds (20 initial agents), not a substitute scoring rule.

| Model | Health score, off → on | Change | Final population health, off → on | Survivors, off → on |
|---|---:|---:|---:|---:|
| GPT-5.6 Sol | 77.61 → 85.94 | +8.33 | 41.75% → 68.60% | 20/20 → 19/20 |
| GPT-5.6 Terra | 66.05 → 76.33 | +10.28 | 14.90% → 42.30% | 11/20 → 18/20 |
| GPT-5.6 Luna | 64.12 → 69.48 | +5.36 | 8.30% → 25.60% | 8/20 → 14/20 |
| GPT-5.4 Mini | 55.90 → 62.49 | +6.59 | 8.05% → 21.40% | 6/20 → 11/20 |

The order stays Sol > Terra > Luna > Mini. Separation does not uniformly widen:
Sol–Terra narrows 11.56 → 9.61 points; Sol–Luna widens 13.49 → 16.46;
Sol–Mini widens 21.71 → 23.45; Terra–Luna widens 1.93 → 6.85;
Luna–Mini narrows 8.22 → 6.99. These are differences within this pilot,
not evidence for a universal model capability ordering.

Final population health improves for every model in both seeds. Full-horizon
health improves in seven of eight treatment worlds. Luna seed 41 is the useful
exception: survivors increase 3 → 7 and final health 3.5% → 20.7%, while the
full-horizon score decreases 67.02 → 66.48. Its better endpoint does not erase
the health trajectory that preceded it. Sol seed 11 similarly improves health
but loses one survivor. Neither observation supports counting survivors alone.

## Does the recovery mechanism actually work?

The rule restores up to two health points after two consecutive qualifying
ticks, checked after passive decay. Qualification requires food ≥ 10/20,
water ≥ 10/20, energy ≥ 15/30 and no damage that tick. Damage or inadequate
reserves reset the streak; recovery caps at 100 and cannot resurrect dead agents.

Reconstructing end-of-tick health from damage, death and recovery events exactly
matches raw full-horizon health totals for all sixteen completed Codex treatment
and control cells. Recomputed eligibility and streaks found zero violations in
5,321 recovery checks: 4,441 completed Codex checks plus 880 partial Gemini checks.
Observed heals satisfied eligibility, streak, two-point rate and health-cap
constraints. The existing six mechanic tests cover boundaries, reset/death,
checkpoint persistence and the disabled condition. Together these support that
the implementation is behaving as specified; they do not prove an optimal rate.

| Model | Qualifying checks / all checks | Health actually restored, both worlds |
|---|---:|---:|
| GPT-5.6 Sol | 747/1199 (62.3%) | 382 HP |
| GPT-5.6 Terra | 546/1172 (46.6%) | 261 HP |
| GPT-5.6 Luna | 311/1098 (28.3%) | 99 HP |
| GPT-5.4 Mini | 284/972 (29.2%) | 114 HP |

A qualifying check includes full-health agents and the first qualifying tick,
so it does not necessarily produce a heal. Denominators also differ because
checks stop after death. This is descriptive evidence of sustained reserve
management, not an independently normalized ability score. Sol and Terra meet
the conditions much more often than Luna and Mini. Injured-agent checks show
water/food shortages and damage frequently interrupting recovery; energy also
matters, particularly for Luna. Winter exposure can interrupt a well-fed agent's
streak, as required by the current rule.

Endpoint improvements exceed the health directly restored. Changed decisions,
resource use, deaths and subsequent trajectories therefore contribute to the
observed difference; it would be wrong to attribute the full effect to adding
recovery points to otherwise identical histories.

## Gemini: comparable evidence through tick 44 only

Gemini's partial treatment reports are stale and claim zero observed ticks.
Their score/endpoint fields are not used here. Checkpoints and append-only
run events instead establish 44 completed ticks for each treatment seed.
For a fair interim comparison, both baseline and treatment are truncated to
the same first 44 ticks. See the linked trajectory artifact for exact run paths.

| Model | First-44-tick health, off → on | Change |
|---|---:|---:|
| GPT-5.6 Sol | 89.70 → 94.94 | +5.24 |
| Gemini 3.7 Flash | 91.91 → 95.91 | +4.01 |

Gemini's lead over Sol shrinks from 2.21 to 0.97 points over this matched prefix.
At tick 44 Gemini has all 20 agents alive in both conditions; population health
is 70.85% without recovery and 81.00% with it. Gemini's baseline deaths happen
later. Therefore this partial evidence cannot yet resolve the original question
about fewer healthier Gemini survivors versus more injured Sol survivors at 60.
The partial comparison must not be ranked against completed 60-tick scores.

## Secondary metrics and cost

Execution and production use the frozen v8.1 scorer on pooled raw counts.
Cost is average API-price-equivalent dollars per world reported by the local
usage estimator, not a charge to the subscription or a weekly-quota estimate.

| Model | Execution, off → on | Production, off → on | Cost/world, off → on |
|---|---:|---:|---:|
| GPT-5.6 Sol | 91.39 → 91.04 | 202.25 → 164.33 | $25.42 → $25.50 |
| GPT-5.6 Terra | 90.10 → 90.28 | 165.00 → 144.42 | $8.50 → $9.41 |
| GPT-5.6 Luna | 86.59 → 88.53 | 108.25 → 111.67 | $0.65 → $0.69 |
| GPT-5.4 Mini | 88.40 → 90.55 | 86.75 → 95.58 | $3.90 → $4.73 |

Sol's production falls 18.7%, Terra's 12.5%, while Luna's and Mini's rise 3.2%
and 10.2%. Health gains do not require higher production. That favors keeping
production visible as a diagnostic rather than assuming it is an interchangeable
measure of a healthy society. Execution changes are much smaller than health
changes. Treatment decision latency also varies under concurrent launches, so
this study does not isolate a causal speed effect of healing. Gemini's partial
report does not support a comparable completed-run cost estimate here.

## Recommendation and limits

Keep conditional regeneration as a candidate for the next benchmark: it works,
rewards maintaining reserves, allows preserved injured populations to recover,
and retains substantial performance separation instead of making every society
healthy. The completed evidence does not suggest changing the two-point rate
or stability threshold solely to maximize a desired leaderboard gap.

Do not claim it universally separates stronger and weaker models: some gaps
widen and others narrow, and two seeds are not enough to establish stable effect
sizes. The key Sol/Gemini endpoint question remains pending Gemini's final 16
ticks. Existing v8.1 results remain unchanged; this report does not launch or
certify a new recipe.

[Supplementary health trajectories and audit](regeneration-health-trajectories.json)
contain all twenty control/treatment cells, including the explicitly partial
Gemini pair, exact source paths, reconstruction results and pooled calculations.
All completed Codex cells have clean report integrity, zero model-output/provider
failures and 100% usage-record coverage. That does not resolve the separately
noted Mini manifest identity metadata discrepancy or convert experiments into
certified benchmark results.
