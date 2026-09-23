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
promotional prices of $4 / $0.40 / $5 / $20 respectively. Correction after
checking effective overrides: the repository already uses these current Sol
rates through main_harness_pricing.py. The older literal card in usage.py is
overridden. The $5 / $0.50 / $6.25 / $30 card is retained only as a labeled
legacy-price sensitivity. Both sides use the same price card; no pricing
change is attributed to caching.

Sources: [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra),
[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[pricing](https://developers.openai.com/api/docs/pricing).

The benchmark database passed verification before selection: 105 runs,
47,211 decisions, no foreign-key errors. Baselines are
`gpt-6-astra-v8-revised-20260907:seed-11` (600 decisions) and
`gpt-5.6-sol:seed-11` (500 decisions), both medium effort.

## Completed results

All four controllers completed at tick 1. Source: f17d04769494c85c5b1183791f8d94701100bb72.
All 20 paired observation hashes match, including the respective historical
first-tick observations. Static rulebook hashes also match historical evidence.
Each fork condition has ten distinct child sessions, one static template, and
per-fork delta accounting. There were 40 decisions plus two initializations,
no failed decisions, no missing usage, and no provider failures.

| Measurement | Astra fresh | Astra fork | Sol fresh | Sol fork |
| --- | ---: | ---: | ---: | ---: |
| Decision input tokens | 149,581 | 150,251 | 135,501 | 136,171 |
| Cached input tokens | 0 | 143,360 | 19,712 | 104,064 |
| Calls with any cache reads | 0/10 | 10/10 | 2/10 | 9/10 |
| Decision output tokens | 2,062 | 2,091 | 4,089 | 3,399 |
| Decision input cost | $1.495810 | $0.212270 | $0.471041 | $0.170054 |
| Total observed cost, including template | $1.598910 | $0.463110 | $0.552821 | $0.290838 |

Astra forks read 14,336 cached tokens every time. Sol forks read 12,928 on
five calls, only 9,856 on four, and zero on one. No call reported cache writes.
The fork adds 67 input tokens per decision; initialization costs $0.146290 for
Astra (14,504 input, 25 output) and $0.052804 for Sol (13,076 input, 25 output).
Total diagnostic spending was $2.905678 API equivalent, not an API charge.

The decision-input reductions are 85.8% and 63.9%. Including initialization
and observed output, these short tests saved 71.0% and 47.4%. Output differences
are not attributed to caching. Astra had no invalid actions; Sol's invalid
action rates were 3.8% fresh and 8.9% fork (action-level denominators differ).
All decisions parsed successfully. This small test cannot establish behavioral
equivalence, quality improvement, or lack of regression.

## Approximate full-run savings

The preferred forward estimate uses each condition's measured mean decision
input cost, then adds historical mean prompt growth as uncached input and
holds historical output tokens fixed. Historical first-tick prompts match:
Astra input grows by 959.228 tokens per decision on average, Sol by 727.918.
One template initialization is included. This assumes the CLI overhead stays
constant and the observed cache distribution persists as observations grow.

| Matched current-CLI projection | Fresh | Fork | Estimated saving |
| --- | ---: | ---: | ---: |
| Astra, 600 decisions | $101.76 | $24.89 | $76.87 / 75.5% |
| Sol, 500 decisions | $29.28 | $14.29 | $15.00 / 51.2% |

**Those large percentages are not reductions from the existing leaderboard
costs.** Historic Astra already cached 10,240 tokens on 591/600 calls. Historic
Sol cached 14,080 on 371/500, 9,984 on 48, 15,104 on one, and missed on 80.
Different CLI versions/routing therefore materially change the baseline.

| Historical cost versus projected current fork | Historical | Projected fork | Difference |
| --- | ---: | ---: | ---: |
| Astra seed 11 | $43.80 | $24.89 | $18.91 / 43.2% lower |
| Sol seed 11 | $14.69 | $14.29 | $0.41 / 2.8% lower |

This second comparison includes CLI overhead changes, not just cache affinity.
For an alternative sensitivity that freezes the *old* total input budgets,
adds only the measured 67-token fork overhead, and substitutes today's cache
distribution, Astra projects to $21.40 (51.1% lower), but Sol to $16.73
(13.9% higher). With full-prefix hits on every call that alternative yields
$21.40/$12.20; with every call missing it yields $98.81/$35.47. These are
scenarios, not confidence bounds.

**Conclusion:** the native shared-prefix mode substantially improves this
matched current-CLI test. Astra has a promising run-saving signal. Sol does
not yet have persuasive savings relative to its historically well-cached
benchmark, even though it improves today's fresh-call baseline.

Ten sequential first-tick decisions do not establish sustained cache behavior
under normal parallel workers, expiry, restarts, or provider routing changes.
The fresh-before-fork order was not randomized. Astra's 10/10 hits are not a
guarantee. Native usage reports the requested exact models but no independently
resolved response model. The extra initialization exchange is a new treatment,
not a transparent change to published benchmark conditions. No historical
evidence, leaderboard, or published recipe was changed. Subscription quota
savings are not inferred from API-equivalent dollars.

## Reproduction

Run `python3 scripts/analyze_cache_cost_study.py --output docs/cache-cost-study-20260922.json`.
The generated [measurements](cache-cost-study-20260922.json) include source
file SHA-256 hashes, reliability, fixed price cards, cache distributions,
template cost, historical budgets, and all projection variants. The analyzer
refuses incomplete controllers, unmatched prompts/source, duplicate decisions,
non-delta fork usage, or unexpected model/effort/CLI. Run configs are the four
`configs/run-configs/cache-{astra,sol56}-{fresh,fork}-20260922.json` files.
