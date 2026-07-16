# Turn-mode staged comparison: generalist screen

## Outcome

`shuffled-sequential-v1` did not pass the screening bar for the longer specialist
stage. It made prior same-tick state visible, but it did not make agents more
mechanically valid or produce more economic value. It also made each run roughly
six times slower.

Keep `simultaneous-v1` as the default. Keep sequential activation as an explicit
experimental treatment for narrower questions about contention, survival, or
inequality.

## Design

- Three paired world seeds: 11, 23, and 41.
- Twenty agents and 20 ticks per condition.
- Paired stratified assignments using seeds 211, 212, and 213.
- Population per run: four Luna, four Sonnet, three Terra, three Opus, three Sol,
  and three Fable agents.
- `organic-generalists`, `compact-v2`, raw decisions, low reasoning, and zero
  Claude thinking-budget tokens.
- Six intended runs completed cleanly with 400/400 usage records and no decision
  failures.
- The first seed-41 sequential launch was stopped after 12 calls because its
  command omitted Sol and misrouted Fable. It is preserved at
  `seed-41/shuffled-sequential-v1/`; the valid replacement is
  `seed-41/shuffled-sequential-v1-retry-1/`.

World seed is the experimental unit. The reported p-values use the two-sided exact
paired sign-flip test over three seed differences. With only three pairs, 0.25 is
the smallest attainable nonzero two-sided p-value, so this is a directional screen,
not a confirmatory experiment.

## Paired results

| Outcome | Simultaneous mean | Sequential mean | Mean change | Paired changes | Exact p |
|---|---:|---:|---:|---|---:|
| Invalid action rate | 26.1% | 27.3% | +1.2 pp | +0.3, +1.2, +2.1 pp | 0.25 |
| Observation-known invalids | 158.7 | 176.0 | +17.3 | +8, +13, +31 | 0.25 |
| Speech | 124.3 | 97.3 | -27.0 | -65, -20, +4 | 0.50 |
| Trade offers | 24.3 | 18.3 | -6.0 | +2, 0, -20 | 1.00 |
| Accepted trades | 0.67 | 1.00 | +0.33 | 0, 0, +1 | 1.00 |
| Accepted trade value | 7.33 | 7.33 | 0 | 0, -6, +6 | 1.00 |
| Survival damage | 62.3 | 50.3 | -12.0 | -16, -11, -9 | 0.25 |
| Mean final health | 83.37 | 86.73 | +3.37 | +2.3, +5.2, +2.6 | 0.25 |
| Wealth Gini | 0.1860 | 0.1479 | -0.0381 | -0.0343, -0.0691, -0.0110 | 0.25 |
| Complete structures | 0.67 | 0 | -0.67 | -1, -1, 0 | 0.50 |
| Runtime | 11.1 min | 69.0 min | +57.9 min | +58.8, +58.5, +56.4 | 0.25 |

No tested outcome survived Benjamini-Hochberg correction; the lowest adjusted
q-value was 0.60.

## Interpretation

The treatment worked technically. Sequential agents observed an average of 201
same-tick event sets per run, 98 decisions per run followed same-tick speech, and
the stale-state diagnostic fell from an average of 318.3 invalid actions to zero.

But stale-state invisibility was not the dominant cause of invalid behavior. Total
invalid rates rose in every seed, observation-known invalids rose in every seed,
and early/middle/late activation positions showed no consistent validity gradient.
Agents often saw fresher facts and still proposed impossible actions.

Economic results were not better. Sequential activation produced one extra accepted
trade across the three runs, but total accepted trade value was identical. Offers
fell by six per run on average, speech fell by 27, and the two structures created
under simultaneous turns disappeared.

The consistent health and inequality results are the interesting counter-signal.
Sequential worlds had 12 fewer survival-damage events, 3.37 more mean health, and a
0.038 lower Gini. Serialization may reduce resource contention or produce more
conservative behavior. Three pairs are not enough to distinguish those mechanisms.

Model-level invalid-rate changes were heterogeneous: Sol improved by 8.5 percentage
points, Luna by 1.43, and Opus by 1.1; Terra worsened by 2.6, Sonnet by 4.63, and
Fable by 10.87. These are descriptive cohort signals inside interactive worlds, not
independent model rankings.

## Cost

The six intended runs made 2,400 decisions, used 22,600,721 prompt tokens and
929,214 completion tokens, and consumed 655.0985 exact Codex simulation credits for
the Codex cohorts. Sequential conditions used 307.9839 Codex credits versus
347.1146 for simultaneous conditions, but wall-clock time rose from 11.1 to 69.0
minutes per run. The account-level weekly Codex meter moved from 1% to 8% during
the overlapping experiment window; that account figure can include oversight or
other concurrent work and cannot be summed across run reports.

## Decision and next question

Do not launch the 30-tick specialist stage from this screen. Keep
`simultaneous-v1` as the universal default and preserve
`shuffled-sequential-v1` for explicit experiments.

The next turn-structure candidate should be lighter: agents independently plan,
then resolve together, followed by a narrow reaction or settlement phase for
conflicts, messages, and physical trades. That would test whether we can keep
independent initiative while allowing agents to repair coordination failures.
