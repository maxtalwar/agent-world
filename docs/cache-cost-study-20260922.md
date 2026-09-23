# Astra and Sol native cache-cost diagnostic

## Preregistered scope

Question: how much could the shared-prefix native Codex mode reduce run cost
for GPT-6 Astra and GPT-5.6 Sol, including initialization and cache misses?

Four managed diagnostic experiments compare fresh conversations with
`shared-prefix-fork-v1` on CLI 0.156.0. Each condition uses seed 11, ten agents,
one tick, medium effort, and one worker. Astra takes world defaults from
`participant-v8-revised`; Sol takes defaults from its cataloged
`participant-v6` baseline. These are separate within-model comparisons, not
cross-model performance rankings. The intended budget is 20 decision calls
and one template initialization per model (42 calls in total).

The fresh condition runs before the fork condition for each model. The two
models may run concurrently, but decisions within a condition are sequential.
Paired request hashes must match for all ten agent observations. The conditions
do not advance past the first tick, so agent behavior cannot change later
inputs. Template cost is included once. No seeds beyond 11 are launched.

## Planned accounting

- Report observed cache reads, misses, input/output tokens, initialization,
  reliability, and API-list-price-equivalent cost for all actual calls.
- Separate observed total-cost differences from input-only differences: small
  changes in reasoning/output can swamp a ten-call comparison.
- Estimate future run cost from matched per-decision input costs plus the
  historical full-run output budget. Also show a historical-ledger sensitivity
  calculation that preserves each recorded observation/output budget and
  changes only measured fork input overhead and cache behavior.
- Use the exact seed-11 cataloged Astra v8-revised and Sol v6 ledgers; do not
  pool recipes or treat their different horizons as a model-only comparison.
- Include the cost of one initialization in a complete uninterrupted run.
  Resumes, routing load, parallel workers, and cache expiry can reduce savings.
- Treat the result as an approximation from ten startup observations, not a
  measured full-run saving or a subscription-quota conversion.

Transfer accounting is not required: these experiments test prompt caching
and cost, not entrepreneurship or economic outcomes. Standard diagnostic
reports remain available, but first-tick performance is not a leaderboard
claim. Published recipes and historical evidence remain unchanged.

## Price basis

Official API pricing checked on 2026-09-22: Astra $10 input / $1 cached input /
$12.50 cache writes / $50 output per million tokens. GPT-5.6 Sol currently has
promotional prices of $4 / $0.40 / $5 / $20 respectively. The repository's
older Sol card is $5 / $0.50 / $6.25 / $30. Both sides of each comparison will
use the same price card; the Sol promotion is not attributed to caching.

Sources: [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[pricing](https://developers.openai.com/api/docs/pricing).

The benchmark database passed verification before selection: 105 runs,
47,211 decisions, no foreign-key errors. Baselines are
`gpt-6-astra-v8-revised-20260907:seed-11` (600 decisions) and
`gpt-5.6-sol:seed-11` (500 decisions), both medium effort.
