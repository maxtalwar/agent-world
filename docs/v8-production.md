# V8 production scoring

Production measures gross productive value added, not commercial acumen.
The implemented policy is `outcome-production`; the v8 recipe freezes its
configuration and source provenance. It exposes no composite of capability,
execution, and production.

## Formula

Let N be the original population and T the measured horizon (60 for v8).
Let O be the fixed accounting value of goods actually extracted into inventory
plus crafted outputs. Let I be the accounting value of consumed crafting inputs.

Production = 100 × max(0, O − I) / (N × T).

The unit is fixed accounting value added per 100 original-population agent-ticks.
It is linear and unbounded; there is no fitted reference target, logarithm,
cap, positive-terminal-wealth prerequisite, or survival-consumption deduction.
The nonnegative floor handles an overall value-destroying transformation
ledger; it is not a subsistence threshold.

Values reuse the recipe-consistent accounting table already implemented in
the benchmark system. They are analysis weights, not agent-visible prices.
`agent-world recipes participant-v8` exposes the frozen recipe; generated
benchmark reports include the exact accounting table and component counts.

## Event accounting

- `gather`, `chop`, `mine`, `harvest`, and `fish`: credit actual recorded quantity
  entering the producer's inventory at the resource's fixed value.
- `craft`: add outputs and subtract the recipe's actual material inputs.
  The source recipe must match the recorded output. This prevents a resource
  being counted once as an input and again at full value after conversion.
- Farm tending and passive regrowth: no separate credit. These populate the
  tile resource pool; extraction/harvest earns credit once it is collected.
- Completed farms, wells, workshops, tools, irrigation, roads, and storage:
  no construction/ownership bonus. Increased subsequent output benefits the
  score naturally. The acting producer gets output attribution; uniform-model
  benchmark cohorts pool all agents.
- Trade, gifts, fees, contracts, theft, pickup, drop, storage movements, and
  money transfers: no new production value. Repeated transfers cannot inflate
  this score. The existing commerce accounting remains a separate diagnostic.
- Eating, drinking, health restoration, or terminal inventory changes: no
  subtraction from past production. Useful self-consumption and a sale have
  equal production credit.

Initial endowments are not output. Dead agents remain in N, so deaths cannot
improve production by shrinking the denominator. Pooled seed scores use summed
raw O, I, and N×T rather than averaged rounded scores. Events beyond the measured
horizon and output by agents outside the cohort are excluded.

## Intended behavior and limits

A successful self-sufficient farmer and an equally productive commercial farmer
score equally. A farmer who gifts output keeps production credit; the gift adds
no bonus. If generosity undermines later production, the lost output affects
production; if it causes starvation, capability records that separately.

Output of 47, 49, 51, or 53 accounting units gets smooth increments even when
survival consumption is 50. An idle building adds nothing. Tending a farm and
then harvesting it credits the harvest once. Crafting or minting cannot claim
the full output value without paying for the inputs in the accounting.

This is gross production, not profit, utility, market valuation, or net wealth.
It does not directly deduct capital depreciation, unused-stock losses, or
survival consumption. Fixed weights can favor resource mixes and do not model
changing scarcity. Collected but unused goods still count as production;
capability provides the separate outcome axis. Maintaining a resource pool
without collecting output before the cutoff receives no production credit.

## Verification

`tests/test_production_scoring.py` covers destination invariance, unused
construction, farm/harvest double-counting, the subsistence counterexample,
crafting and minting, fixed denominators, pooling, invalid evidence, and
retry-aware latency. `tests/test_v8_pipeline.py` covers report/aggregation
integration, unavailable evidence, legitimate no-ops, live checkpoints,
managed configuration, a real local scripted-world resume, finalization,
and database/leaderboard projection.

No model-backed run or new leaderboard result was created to choose this
formula. Historical scores were not retuned or relabelled.
