# Astra v8.1: resilient settlements and practical cooperation

Analysis dated 2026-09-07. GPT-6 Astra, medium effort, participant-v8-revised,
ten agents per world, 60 ticks, seeds 11/41, no healing. This concerns
`gpt-6-astra-v8-revised-20260907`, not the later v6-labeled Astra study.

## Result and comparison frame

Astra's admitted capability is 80.105 under endpoint-winter-damage-v1,
execution 96.68%, and production 244.67 fixed accounting units per 100 original
agent-ticks. All 20 agents survived; final mean health was 81.25. Seed capability
scores were 81.39 and 78.82. The original full-horizon health score was 92.3825;
that answers a different question and must not replace the current projection.

The metrics database verified with zero foreign-key errors and SQLite integrity
ok. Both Astra cells are finalized ready, clean, and have 100% usage coverage.
Model provenance is accepted requested-only. The job's original cost-unavailable
flag predates the subsequently verified rate-card calculation: cost is $43.27
API-list equivalent per world, including 20 discarded attempts, not subscription
charges. Mean time per resolved decision including recorded attempts is 10.98 s.
See [cost evidence](astra-v81-cost.json) and [the admitted leaderboard](model-leaderboard.md).

The broader [nine-model frozen projection](v81-endpoint-winter-rescoring.json)
contains accepted managed studies beyond the compact catalog projection. Compare
only its unchanged no-healing recipe, medium effort, and matched seeds here;
provider boundaries differ, including the documented Gemini evidence exception.

| Model | Capability | Execution | Production | Survivors | Winter damage per original agent |
|---|---:|---:|---:|---:|---:|
| Astra | 80.11 | 96.68% | 244.67 | 20/20 | 11.45 |
| Gemini 3.7 Flash | 50.29 | 92.37% | 171.50 | 17/20 | 24.15 |
| Sol | 37.91 | 91.39% | 202.25 | 20/20 | 38.45 |

Execution and production in this comparison pool report raw numerators and
denominators, not rounded seed scores. Survival alone would miss much of the
Astra-Sol difference. Astra lost less than half Gemini 3.7's winter health and
finished almost 30 capability points ahead. Two seeds establish replication,
not a broad statistical claim of universal superiority.

## The distinguishing behavior

Astra completed 40 structures across both worlds: 16 farms, 15 shelters, eight
stores, and one well. Gemini 3.7 completed seven shelters and Sol four. Astra
performed 106 successful maintenance actions, compared with 38 and 67. These
are associations supporting an infrastructure-and-upkeep interpretation, not
an intervention isolating their causal effects.

Astra suffered no starvation damage in either ledger. Winter and storm exposure
and occasional thirst account for nearly all losses, with one exhaustion event
in seed 41. More strikingly, neither world lost any health during action ticks
48–59. Every other model in the nine-model comparison lost additional health
during this final spring: Gemini 3.7 lost 8.30 points per original agent and Sol
2.75. Astra's advantage persisted after winter rather than merely delaying deaths.

## A settlement that worked

In seed 11, agents 1, 5 and 6 assembled a small shared settlement at (8,8).
At ticks 11–15 they divided the remaining shelter requirements into wood, stone,
and fiber, granted access, and completed structure-9. A failed handoff caused by
a full pack was followed by a dropped-material workaround and direct construction
contributions. They jointly completed storage structure-15 at tick 24, shared
access, supplied upkeep, and stored food and water for winter. All three ended
at 100 health. Their shared store ended with 61 food, 73 water, seven fiber and
two wood. This is observed coordination with completed actions and beneficiaries,
not simply agreeable messages. The favorable location is a confounder: these
agents also had convenient water access.

## Useful exchange without a formal market

Seed 41 contains a fulfilled informal procurement bargain. Agent 5 repeatedly
needed two stone for a shelter and at tick 35 offered four coins plus shelter
access. Agent 3 delivered and contributed the stone at tick 36, completing
structure-14; agent 5 paid four coins at tick 37. Later they continued sharing
upkeep tasks and water. The ledger records payment even though the formal
accepted-trade counter is zero.

At the same winter transition, agent 7 delivered four water to agent 9 at tick
36 after an urgent request. Agent 9 drank three at tick 37 and granted shelter
access to another neighbor. The attempted onward gift to agent 6 failed because
of carrying capacity. Practical mutual aid existed alongside execution errors.

Across the two worlds there were six cooperative builds and 35 access grants,
but no created groups, accepted formal trades, or fulfilled formal contracts.
Astra did not build an elaborate market or governance system. Its high production
mostly came from gathering, wood extraction, and other physical resource output;
the production score does not measure commerce.

## Limits and counterexamples

Some infrastructure was late. In seed 11 several shelters completed during
winter; agent 2's completed at tick 49, after winter. That agent's food-for-stone
trade proposal and subsequent contract did not result in delivery. There were
140 invalid proposals and 23 contention failures across the two worlds, despite
clean model/provider integrity. Final individual health ranged from 55 to 100.
The evidence supports unusually reliable subsistence and functional local
cooperation, not flawless planning or a self-sustaining economy beyond tick 60.

## Primary evidence

- [Seed 11 report](../runs/managed/gpt-6-astra-v8-revised-20260907/seed-11/run-report.json),
  [snapshot](../runs/managed/gpt-6-astra-v8-revised-20260907/seed-11/run-snapshot.json),
  [ledger](../runs/managed/gpt-6-astra-v8-revised-20260907/seed-11/run.jsonl):
  shelter completion line 1045; storage completion line 1644; shared winter
  preparation around lines 1749–1752.
- [Seed 41 report](../runs/managed/gpt-6-astra-v8-revised-20260907/seed-41/run-report.json),
  [snapshot](../runs/managed/gpt-6-astra-v8-revised-20260907/seed-41/run-snapshot.json),
  [ledger](../runs/managed/gpt-6-astra-v8-revised-20260907/seed-41/run.jsonl):
  procurement offer line 2407, stone contribution/completion lines 2521–2522,
  payment line 2607; water delivery line 2494 and consumption line 2578.
- [Readiness](../runs/jobs/gpt-6-astra-v8-revised-20260907/job.json),
  [source catalog](../data/run-sources.json), and verified
  `data/model-benchmarks.sqlite` (Astra run IDs ending `:seed-11` and `:seed-41`).
