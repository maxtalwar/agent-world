# GPT-5.3-Codex-Spark participant-v1 benchmark attempt

## Result

The 2026-07-24 attempt did not produce an official benchmark score. Both
replications stopped at clean completed-tick checkpoints when the dedicated
GPT-5.3-Codex-Spark weekly plan bucket reached 100%: seed 11 after tick 34 and
seed 41 after tick 32. Each run also had one model-decision structured-output
failure, which independently violates participant-v1's clean-quality
requirement. The benchmark aggregator rejected both runs and emitted no
leaderboard result.

Run root:
`runs/benchmarks/gpt-5-3-codex-spark-participant-v1-20260724-220724`

## Corrected objective diagnostic results

These are incomplete-run diagnostics, not official or directly comparable
Participant v2 scores. They were recomputed from the preserved v1 raw telemetry
after this run exposed three competence-formula defects: missing target-horizon
penalty, no endpoint-health component, and dead-estate wealth attribution.

| Metric | Seed 11 | Seed 41 | Pooled diagnostic |
|---|---:|---:|---:|
| Completed tick | 34/40 | 32/40 | incomplete |
| Decisions | 314 | 315 | 629 |
| Submitted actions | 965 | 994 | 1,959 |
| Contention failures | 7 | 4 | 11 |
| Invalid proposals | 299 | 347 | 646 |
| Action-point overruns | 32 | 44 | 76 |
| Planning execution | 68.79 | 64.95 | 66.84 |
| Target-horizon survival exposure | 78.50 | 78.75 | 78.62 |
| Endpoint population health | 23.90 | 12.90 | 18.40 |
| Survival continuity | 43.31 | 31.87 | 38.03 |
| Living-accessible material outcome | 35.83 | 68.75 | 52.29 |
| Sustained competence | 47.44 | 52.21 | 51.03 |
| Venture initiatives | 7 | 3 | 10 |
| Realized venture value | 0 | 0 | 0 |
| Entrepreneurial agency | 0 | 0 | 0 |
| Living at interruption | 4/10 | 8/10 | not endpoint-comparable |
| Structures / gifts / groups | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Trades offered / accepted | 7 / 0 | 3 / 0 | 10 / 0 |

The original Participant v1 reports displayed pooled competence of 82.23. That
number is retired, not an alternative interpretation. The pooled v2 score
applies the corrected formula to pooled numerators and denominators. It remains
descriptive only because the runs ended at different ticks and failed quality
certification.

## Civilization shape

Both seeds formed a dispersed, mobile extraction economy. Agents moved often
(453 moves pooled), gathered basic goods (280 gathers), and spent heavily on
immediate consumption (181 consumes). Successful extraction was concentrated
in fiber and food: across the two runs agents acquired 139 fiber, 144 food, and
46 water, but only 9 wood, 7 ore, and 3 stone.

That production mix never became capital. There were no structures,
construction contributions, claims, access policies, contracts, groups,
gifts, or successful trades. Ten trade offers were created and 14 acceptances
were attempted, but none completed; offers instead expired or failed because
the parties were not co-located, goods were unavailable, or the offerer had
died. Communication existed but was sparse and inconsistent: 47 broadcasts or
whispers across 629 agent-ticks.

The society was therefore not a town, market, or cooperative network. It was
closer to a field of autonomous foragers carrying modest, similarly valued
inventories. Low terminal wealth inequality (Gini 0.087 and 0.069) reflects
the absence of differentiated enterprise and productive assets, not broadly
shared prosperity.

## Survival and planning

Hydration was the central failure mode. At least 221 of the 646 invalid
proposals explicitly attempted unavailable water or tried to consume water
the agent did not possess. Another 76 planned beyond the available
action-point budget. Missing or invalid move directions occurred 31 times.
Only 11 failures were classified as same-tick contention, so the 646 invalid
proposals primarily reflect model planning or state-tracking failures rather
than simultaneous-resolution bad luck.

Deaths began late (ticks 23 and 25 in seed 11; ticks 27 and 30 in seed 41),
after a long period of apparently viable roaming. Seed 11 then suffered a
cluster of four deaths at tick 31 and had only four survivors at interruption.
Seed 41 retained eight at tick 32, but five of those survivors had 20 health or
less. The repeated pattern is a civilization that could harvest enough to
delay collapse but did not build a robust water strategy or collective safety
net.

The sharp survival difference between seeds is important. It prevents a
confident estimate of Spark's 40-tick survival performance, while the
replicated absence of structures, successful exchange, and venture realization
is much more convincing.

## Usage and reliability

| Usage | Seed 11 | Seed 41 | Total |
|---|---:|---:|---:|
| Calls | 314 | 315 | 629 |
| Prompt tokens | 3,483,079 | 3,491,245 | 6,974,324 |
| Output tokens | 1,605,343 | 1,650,037 | 3,255,380 |
| Reasoning tokens | 1,573,538 | 1,617,459 | 3,190,997 |
| Prompt tokens/call | 11,092.6 | 11,083.3 | 11,087.9 |
| Output tokens/call | 5,112.6 | 5,238.2 | 5,175.5 |
| Cached input share | 89.4% | 90.6% | 90.0% |

Spark produced very large reasoning outputs: reasoning accounted for about 98%
of recorded output tokens. The exact simulation-credit cost is unavailable
because the current rate card does not contain this model. The dedicated
weekly Spark bucket went from a fresh window to 100% before the pair could
finish.

The observed structured-output failure rate was low (2/629 decisions, 0.32%),
but participant-v1 intentionally requires zero decision failures. The failures
were malformed action JSON at seed 11 tick 4 and seed 41 tick 22. The startup
health gate did not stop either run because one isolated failure was below its
early-abort threshold; the final quality gate correctly rejected them.

## Interpretation and next benchmark

The attempt supports a diagnostic characterization: Spark was energetic and
productive at basic foraging, but weak at grounded multi-action planning,
resource security, and conversion of goods into civilization-scale
coordination or capital. Participant v1 incorrectly turned that into competence
of 82.23 because it treated the interrupted horizon as complete, lacked an
endpoint-health check, and counted inventory still attached to dead agents.
Participant v2 corrects all three problems. Its 51.03 diagnostic matches the
observed fragile foraging society much more closely.

A certified result requires two fresh clean 40-tick runs. Resuming these
checkpoints cannot make them official because their decision failures remain
in the audit trail. At the observed output rate, the two-run protocol also
appears larger than one weekly Spark allowance. The rate-safe route is one
fresh seed per allowance window (or an explicitly authorized alternative
billing/reset mechanism), followed by normal participant-v2 aggregation.
