# Stateless v1 versus v3 replicated civilization experiment

## Design

Experiment root:

`runs/experiments/stateless-v1-v3-civilization-30a-40t-seeds11-41-20260723-174150`

This study compares standard `stateless-v1` with corrected `stateless-v3` in
two matched seed pairs. Each cell ran for 40 ticks with 30 agents: six Sol, six
Terra, six Luna, six Opus, and six Sonnet. All cells used medium reasoning,
baseline action feedback, raw decisions, simultaneous turns, the
`organic-generalists` preset, stratified assignment seed 117, and stateless
provider conversations. The only intended treatment was the connector profile.

All four cells reached tick 40. Every tick-5 health gate passed. Three cells had
zero model-decision failures and 100% usage coverage. Seed 41 v1 had one Sonnet
decision failure and 99.91% usage coverage; there were no quota failures or
checkpoint pauses.

Claude's invocation is unchanged by v1/v3, so Opus and Sonnet provide a useful
measure of background stochastic and shared-world variation. They are not a
perfect behavioral control because they interact with the treated Codex agents.

## Cost and connector behavior

### Paired Codex results

| Seed | Profile | Calls | Prompt/call | Cached share | Uncached/call | Output/call | Credits/call |
|---|---|---:|---:|---:|---:|---:|---:|
| 11 | v1 | 697 | 14,630 | 65.9% | 4,992 | 421 | 0.5885 |
| 11 | v3 | 709 | 13,899 | 62.7% | 5,189 | 442 | 0.6505 |
| 41 | v1 | 699 | 14,585 | 67.1% | 4,795 | 415 | 0.5824 |
| 41 | v3 | 711 | 13,897 | 61.9% | 5,300 | 393 | 0.6277 |
| **Pooled** | **v1** | **1,396** | **14,607** | **66.5%** | **4,893** | **418** | **0.5855** |
| **Pooled** | **v3** | **1,420** | **13,898** | **62.3%** | **5,244** | **417** | **0.6391** |

V3 reduced reported Codex prompt tokens per call by 4.9%, reproducing the
controlled tick-zero result. It nevertheless increased uncached input by 7.2%
and exact simulation credits per call by 9.2%. The cost increase replicated:
10.5% in seed 11 and 7.8% in seed 41. Output, reasoning, and latency were nearly
flat when pooled, so cache erosion is the main measured cause.

| Codex model | Prompt/call change | Cached-share change | Credits/call change |
|---|---:|---:|---:|
| Sol | -4.4% | -7.5 pp | +9.8% |
| Terra | -5.0% | -11.0 pp | +21.2% |
| Luna | -5.5% | +6.9 pp | -14.6% |

The cache effect is model-specific: Luna benefited, while the more expensive Sol
and Terra calls lost enough cache reuse to overwhelm the smaller prompt. Thus
v3 is not currently a cost improvement for this mixed population.

All 60 tick-zero Agent World request hashes matched within the paired cells.
Even the unchanged Claude cohorts showed materially different tick-zero cache
and output telemetry between concurrent runs. Prompt-token reduction is a clean
connector effect; the exact cache and credit magnitude remains partly sensitive
to provider timing, concurrency, and automatic cache behavior.

## Civilization outcomes

### Paired headline results

| Metric | Seed 11 v1 | Seed 11 v3 | Seed 41 v1 | Seed 41 v3 | Replicated direction |
|---|---:|---:|---:|---:|---|
| Survivors | 24 | 26 | 25 | 25 | V3 non-worse |
| Survival-damage events | 293 | 247 | 337 | 322 | Lower in v3 |
| Invalid-action rate | 22.9% | 22.3% | 23.2% | 23.1% | Slightly lower in v3 |
| Contention rate | 0.6% | 1.1% | 0.5% | 0.9% | Higher in v3 |
| Completed structures | 6 | 3 | 5 | 4 | Lower in v3 |
| Structure replacement value | 78 | 88 | 76 | 58 | Mixed |
| Stored inventory value | 81 | 40 | 37 | 69 | Mixed |
| Accepted trades | 14 | 4 | 7 | 2 | Lower in v3 |
| Trade conversion | 14.7% | 4.0% | 8.2% | 3.0% | Lower in v3 |
| Gift events | 8 | 10 | 13 | 17 | Higher in v3 |
| Speech events | 456 | 456 | 497 | 346 | Non-increasing in v3 |
| Total wealth | 389 | 394 | 402 | 353 | Mixed |
| Wealth Gini | 0.326 | 0.238 | 0.262 | 0.306 | Mixed |

Pooled survival was 51/60 in v3 versus 49/60 in v1. V3 also had 9.7% fewer
survival-damage events. This did not represent greater end-state security:
living agents held 11 carried food in the two v3 worlds versus 31 in v1, and
mean food reserves were lower under v3 in both seeds. V3 agents had slightly
higher mean health but thinner food and water buffers.

### From settled capital to mobile extraction

Several coupled differences replicated across both worlds:

- Movement increased from 1,424 to 1,661 events (+16.6%).
- Gathering increased from 886 to 932 (+5.2%).
- Harvesting collapsed from 58 to 12 (-79.3%).
- Maintenance actions fell from 24 to 9.
- Completed structures fell from 11 to 7.
- Access grants fell from 11 to 6.
- Contention failures rose from 50 to 96.

V3 therefore produced a more mobile, extractive civilization. Agents moved and
gathered more, but converted less of that activity into durable productive
capital, harvests, maintenance, or secure reserves. V1 produced a more settled
capital economy with more farms, storage, upkeep, and access relationships.

Planning errors and contention moved in opposite directions. Invalid proposals
fell from 2,211 to 2,174 despite similar decision exposure, including fewer
action-point-overrun and unavailable-water-consumption errors. Contention nearly
doubled, concentrated in food, fiber, and fishing. Total resolver failures were
therefore almost unchanged. V3 may make individual plans slightly more valid
while sending more agents toward the same immediately visible resources.

### Entrepreneurship, ownership, and institutions

V1 completed 11 structures: eight were owned by Sol agents, with the others
owned by Luna, Opus, and Sonnet. V3 completed seven: four Sol-owned, one
Terra-owned, one Opus-owned, and one group-owned. V3 therefore had less capital
but somewhat more diverse ownership.

Both conditions recorded two cooperative builds across the two seeds. V1 seed
11 produced the study's clearest functioning property institution: one
fee-charging structure collected 17 fiber payments and issued three dividend
claims. V3 seed 41 instead created the only formal group, the four-member
cross-model `forest_workshop`, and gave it a storage asset. Neither condition
formed contracts, collateral, or repayment institutions. These institutional
outliers did not replicate and should be treated as examples of possible paths,
not condition-level effects.

Upkeep distinguished the conditions more reliably. V1 agents performed 24
maintenance actions and supplied upkeep value 50; v3 performed nine and
supplied value 18. V3 had fewer missed cycles only because it maintained a
smaller capital stock.

### Trade, gifts, and communication

V1 offered 180 trades and completed 21. V3 offered 166 and completed only six.
Conversion fell from 11.7% to 3.6%, and accepted trades declined in both seeds
and across every model cohort. Most completed trades in both conditions crossed
model cohorts, so the decline represents weaker inter-cohort market
coordination rather than loss of within-model exchange.

Trade offers did not uniformly disappear: v3 seed 11 offered slightly more than
its v1 pair, and Opus offered more under v3 when pooled. The main failure was
conversion. V3 accumulated more still-open or expired offers and far fewer
successful acceptances.

Gift events increased from 21 to 27, although total gift value was nearly flat
(42 in v1 versus 40 in v3). Nearly all gifts crossed cohorts. The economy thus
shifted modestly away from completed exchange and toward direct assistance.

Speech fell from 953 to 802 events. Seed 11 was exactly tied at 456; seed 41 v3
fell by 151, so reduced communication did not replicate as cleanly as the trade,
construction, or movement effects.

## Model outcomes

| Model | V1 survivors | V3 survivors | V1 invalid/decision | V3 invalid/decision | Main directional result |
|---|---:|---:|---:|---:|---|
| Sol | 11/12 | 12/12 | 0.596 | 0.625 | Survival improved; validity slightly worse |
| Terra | 7/12 | 10/12 | 0.929 | 0.718 | Strongest survival and validity improvement |
| Luna | 11/12 | 11/12 | 0.603 | 0.612 | Essentially unchanged |
| Opus | 10/12 | 11/12 | 1.202 | 1.240 | Similar |
| Sonnet | 10/12 | 7/12 | 1.397 | 1.511 | Worse survival under v3 worlds |

Terra is the clearest positive model-level signal: invalid proposals fell in
both seed pairs, and seed 11 avoided all three Terra deaths seen in v1. However,
Terra's Codex cost per call increased 21.2%.

Contention rose for every cohort, including unchanged Opus and Sonnet agents.
This supports a shared-world mechanism: changed Codex behavior altered resource
competition faced by everyone. Sonnet's replicated survival decline also warns
against interpreting v3's two extra pooled survivors as a universal performance
improvement.

## Interpretation

The connector change is not behavior-neutral. It preserves the Agent World
rulebook and observations, but removes model-visible coding-agent instructions.
That can still redistribute attention and change stochastic trajectories. Across
two seeds, v3 consistently favored immediate movement and extraction over
market conversion, capital maintenance, and settled production.

Two replications are suggestive, not definitive. The strongest claims are:

1. V3 reliably reduces total reported Codex prompt tokens by about 5%.
2. Under concurrent full simulations, v3 did not reduce cost; poorer Sol/Terra
   cache reuse increased exact credits per call by about 9%.
3. V3 remained reliable at the provider boundary and did not worsen overall
   survival.
4. The paired civilizations repeatedly became more mobile and contentious, with
   fewer successful trades, harvests, and completed structures.

Before making v3 the default, run a fixed captured-input cache benchmark and at
least two additional civilization seeds. A sequential or counterbalanced launch
would help separate connector-prefix caching from concurrency and cache-warming
order. If the civilization pattern persists, treat prompt-harness reduction as
a substantive behavioral intervention rather than a free infrastructure
optimization.
