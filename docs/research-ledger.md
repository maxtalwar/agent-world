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

## 2026-07-16 — Simultaneous versus shuffled sequential turns

### Question and design

Does resolving each shuffled agent activation before the next agent observes and
decides improve mechanical validity or emergent social/economic behavior?

The generalist screening stage used three paired world seeds (11, 23, 41), 20 agents,
20 ticks, stratified assignment seeds 211–213, `compact-v2`, raw decisions, and low
reasoning. Each world contained four Luna, four Sonnet, three Terra, three Opus, three
Sol, and three Fable agents. The intended run artifacts and complete analysis are at
`runs/experiments/turn-mode-stage1-20a-20t-3seeds-20260716-110620/`:

- Seed 11:
  `seed-11/simultaneous-v1/` and `seed-11/shuffled-sequential-v1/`.
- Seed 23:
  `seed-23/simultaneous-v1/` and `seed-23/shuffled-sequential-v1/`.
- Seed 41:
  `seed-41/simultaneous-v1/` and
  `seed-41/shuffled-sequential-v1-retry-1/`.
- Excluded but preserved:
  `seed-41/shuffled-sequential-v1/`. Its command omitted the three Sol agents and
  routed Fable through the wrong provider, so the 17-agent run was stopped after 12
  decisions and replaced in the retry directory.
- Durable results:
  `turn-mode-stage1-analysis.json` and `turn-mode-stage1-analysis.md`.

All six intended runs completed with 400 decisions, 100% usage-record coverage, zero
decision failures, and matching assignment maps within pairs. World seed was the
experimental unit. Exact two-sided paired sign-flip tests used the three seed deltas;
with n=3, the smallest attainable nonzero p-value is 0.25. No outcome survived
Benjamini-Hochberg correction; the lowest q-value was 0.60.

### Findings and uncertainty

- Sequential observations worked as designed: an average of 201 decisions per run saw
  earlier same-tick events and 98 followed same-tick speech. Invalid actions attributed
  to unobserved prior resolutions fell from 318.3 per run to zero.
- This did not improve validity. Sequential invalid rates were higher in every pair:
  +0.3, +1.2, and +2.1 percentage points, for means of 27.3% sequential versus 26.1%
  simultaneous (exact p=0.25). Observation-known invalid counts also rose in all three
  seeds, and early/middle/late activation positions showed no consistent gradient.
- Economic output did not improve. Offers fell from 24.3 to 18.3 per run and speech
  from 124.3 to 97.3. Sequential runs completed one additional trade overall, but
  accepted trade value was identical at 7.33 per run. Simultaneous runs completed two
  structures; sequential runs completed none.
- Sequential runs did consistently reduce survival damage by 12 events, increase mean
  final health by 3.37, and reduce wealth Gini by 0.038. These are credible hypotheses
  about reduced contention or more conservative behavior, not confirmatory results.
- Model-level validity effects were heterogeneous and descriptive: Sol improved by 8.5
  percentage points, Luna by 1.43, and Opus by 1.1; Terra worsened by 2.6, Sonnet by
  4.63, and Fable by 10.87. Agents share interactive worlds, so these cohorts are not
  independent model-ranking samples.
- Runtime rose from 11.1 to 69.0 minutes per run, about 6.2 times slower. Prompt size
  was effectively unchanged. Exact Codex simulation credits fell from 347.1146 across
  the simultaneous runs to 307.9839 across sequential runs.

### Decision

The generalist screen did not meet the bar for the 30-tick specialist stage, so that
conditional stage was not launched. Keep `simultaneous-v1` as the default. Retain
`shuffled-sequential-v1` as an explicit treatment for targeted contention, survival,
or inequality research rather than treating it as a general infrastructure upgrade.

### Next question

Can a lighter multi-phase turn preserve independent planning and initiative, resolve
the plans together, and then offer a narrow reaction or settlement phase for
conflicts, communication, and physical trades?

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
