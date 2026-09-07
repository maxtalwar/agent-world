# Expanded regeneration results -> 2026-09-07

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

[Detailed evidence](regeneration-expanded-results.json) records exact source paths, provenance, per-agent restored health/max qualification streak, food/water/energy threshold failures, damage checks, death timing, execution and reliability. Failure categories overlap. Standard self-declared transfer accounting applies; cost comparison is outside this health-focused decision.

The arithmetic scoring check gives ten survivors at 20 HP a 20% original-population endpoint score versus 10% for one survivor at 100 HP among ten original agents. This confirms the intended population denominator; it is not a new model run.

Validation: baseline database verification passed (87 runs, integrity ok). All six existing `test_health_regeneration.py` unittest checks passed in the supplied source worktree: checkpoint streak, damage/death, disabled behavior, rate sweep, stability/cap/prompt, post-decay thresholds and shortage reset. All 16 evidence rows and report paths validated.
