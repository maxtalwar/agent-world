# Research ledger

This is the durable index of what Agent World experiments have taught us. Raw run
artifacts are the evidence; this ledger records interpretations, uncertainty, and
product decisions so future researchers do not have to reconstruct conclusions from
chat history.

## Recording rule

Every analyzed experiment should add an entry containing:

- date and research question
- treatment and control, population, ticks, seeds, and assignment strategy
- exact artifact directories, including excluded or retried conditions
- headline measurements and statistical method
- what the evidence supports, what it does not support, and confidence
- resulting product decision and the next unresolved question

Never delete a degraded or superseded run. Keep it, mark why it was excluded, and put
the replacement in a new directory. Use independent paired world seeds as the
experimental units for causal inference; agents inside one world interact and are not
independent samples. Report unadjusted signals separately from multiple-comparison
corrected results.

Local run artifacts are intentionally gitignored because they are large. Rebuild their
searchable index with `python3 -m agent_world.cli catalog-runs`; completed CLI,
factorial, and observatory runs refresh `runs/catalog.json` and `runs/catalog.md`
automatically. The catalog is derived, while event logs, snapshots, manifests, reports,
usage logs, and checkpoints are canonical.

## 2026-07-13 — Model-facing boundary treatments

### Question

Can neutral re-indexing of facts agents already receive reduce mechanical mistakes
without steering strategy or crowding out social attention?

### Evidence

- Full grounding screen and replications:
  `runs/experiments/agent-boundary-ab-20260713-152124/` and
  `runs/experiments/agent-boundary-replication-20260713-160725/`.
- Lightweight three-condition screen:
  `runs/experiments/lightweight-boundary-abc-20260713-171022/`. Assignment 108's
  first body-only condition was degraded and the clean replacement is
  `assignment-108/body-only-v3-retry/`.
- Longer paired comparison:
  `runs/experiments/indexed-vs-compact-30t-20260713-194735/`. The initial compact run
  had a transient model-capacity failure at tick 22 and is retained but excluded. The
  clean control is `compact-v2-retry/`; the treatment is `indexed-v3/`.

### Findings

- `grounded-v3` substantially reduced invalid actions and observation-obvious mistakes
  across the short paired runs, but it also reduced speech and trade offers. Repeating
  `body`, `here`, and all four adjacent tiles appears to pull model attention toward
  immediate embodiment and away from broader social activity. This is an attention
  allocation tradeoff, not evidence that social behavior is undesirable.
- `body-only-v3` did not help: across three clean five-tick conditions its invalid rate
  was 22.69%, versus 21.11% for `compact-v2`, and action-budget/energy failures rose
  from 31 to 38.
- `indexed-v3` was the lightest useful treatment in the short screen: invalid actions
  were 20.59% versus 21.11% for compact, observation-obvious failures fell from 111 to
  96, and action-budget/energy failures fell from 31 to 25. Speech still fell from 81
  to 54, although offers rose from 7 to 10.
- In the clean 30-tick pair, indexed reduced the aggregate invalid rate from 28.7% to
  25.4% and observation-obvious invalids from 325 to 222. Speech fell from 216 to 178;
  offers rose from 34 to 38, accepted trades from 3 to 4, and gifts fell from 12 to 6.
  Dynamic observation size rose only 2.2%.
- Effects were model-specific in both short and long runs. Indexed descriptively helped
  Sonnet, Terra, and Opus, while Luna, Sol, and Fable had slightly higher invalid rates.
  Small provider cohorts mean this is a hypothesis, not a provider ranking.
- In the 30-tick paired-agent exploratory test, the indexed change in
  observation-obvious invalid rate was -4.7 percentage points with an unadjusted
  p-value of 0.017, but no metric survived Benjamini-Hochberg correction across 18
  tested outcomes. The reduction appeared in all six five-tick blocks (exact sign-test
  p=0.03125; corrected q=0.25). Agent-level inference is conditional because agents
  share one interactive world.

### Decision

Keep `compact-v2` as the universal default. Retain the other boundaries as explicit
experimental treatments. Do not create provider-specific boundaries: that would make
provider comparisons less fair and risks compensating for models rather than studying
them. The narrow evidence is that indexing can reduce observation-obvious mistakes;
there is no clear evidence that it improves survival, commerce, wealth, construction,
or society formation.

### Next question

Test turn timing. Boundary changes improved mechanical validity but did not reliably
improve downstream social/economic behavior. Compare `simultaneous-v1` with
`shuffled-sequential-v1` across independent paired world seeds while holding the
compact boundary, population assignment, world, and reasoning settings fixed.

## 2026-07-09 — Why gifting dominated early commerce

### Evidence and finding

The 60-tick Lakeside GLM-5.2 run is summarized in `reports/lakeside-settlement.md` and
the older run reports. It produced 27 gifts, eight offers, and one accepted trade; 23
gift actions were food/water aid and only four moved productive materials. Agents also
formed one five-member group, created six group-owned structures, and completed two
heavy cooperative builds.

The defensible conclusion is not that one economic ideology won. In a small trusted
group, direct aid and delivery to shared construction were cheaper than formal barter,
while gathering remained sufficient for survival. The result motivated experiments
with real comparative advantage and physical exchange, while preserving the principle
that agents should not be instructed to trade or form institutions.

### Decision

Treat the specialist preset as an explicitly experimental comparative-advantage
condition. Keep physical goods, local knowledge, co-located settlement, and agent-made
institutions; do not add remote item teleportation or automatic markets to the organic
world.
