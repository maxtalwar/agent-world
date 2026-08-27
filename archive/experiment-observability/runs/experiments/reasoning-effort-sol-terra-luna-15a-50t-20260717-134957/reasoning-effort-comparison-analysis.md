# Reasoning-effort comparison: Sol, Terra, and Luna

## Question and design

Does increasing reasoning effort from low to medium to high improve survival,
mechanical validity, commerce, or society formation for a matched population of five
Sol, five Terra, and five Luna agents?

All three valid conditions ran for 50 ticks with world seed 11, stratified assignment
seed 117, the `organic-generalists` preset, `compact-v2` observations, raw decisions,
and simultaneous turns. Agent-model assignments, spawn positions, world rules, and the
static game-context hash were identical. The medium run was the already-completed run;
low and high ran concurrently. Simulator-relevant code and static context did not
change between them.

Included conditions:

- Low: `low-retry-1/`
- Medium: `../sol-terra-luna-medium-15a-50t-20260717-004547/`
- High: `high/`

The original `low/` directory is preserved but excluded. Sol agent 6 received one
transient model-capacity failure at tick 0, giving 99.85% rather than 100% usage
coverage. `low-retry-1/` is the clean replacement. Every included condition completed
50/50 ticks with zero LLM failures and 100% usage coverage.

## Results

| Metric | Low | Medium | High |
| --- | ---: | ---: | ---: |
| Living agents | **12** | 8 | 11 |
| Survival-damage events | **160** | 194 | 162 |
| Invalid actions | 435/2,227 (19.5%) | 433/2,158 (20.1%) | **403/2,270 (17.8%)** |
| Offers / completed trades | 22 / 2 | 28 / 5 | **20 / 6** |
| Trade conversion | 9.1% | 17.9% | **30.0%** |
| Gifts | 9 | 10 | 8 |
| Structures | 2 storage | farm + storage | 1 farm |
| Speech events | 60 | **135** | 67 |
| Groups / contracts | 0 / 0 | 0 / 0 | 0 / 0 |
| Claimed tiles | 0 | 0 | 1 |
| Simulation credits | **351.568658** | 442.094882 | 514.184610 |
| Elapsed time | 35.85 min | 36.81 min | 60.39 min |

## What higher reasoning changed

### Better trade follow-through

Commerce is the strongest monotonic result. Completed-offer conversion rose from 9.1%
at low to 17.9% at medium to 30.0% at high. High created the fewest offers but completed
the most trades. Meeting failures fell from nine at low and ten at medium to four at
high.

The content of trade also changed. Five of high's six completed trades used coin,
compared with one of five at medium and none of two at low. All six high trades crossed
model cohorts. High therefore looked less like indiscriminate offer generation and
more like selective, successfully coordinated exchange. It is still emergency barter,
not a market institution, but it is the clearest evidence so far that extra reasoning
can improve real physical commerce without the harness completing trades for agents.

### Fewer mechanical mistakes

High reduced aggregate invalidity by 1.7 percentage points versus low and 2.3 points
versus medium. The improvement was model-specific:

| Model | Low | Medium | High |
| --- | ---: | ---: | ---: |
| Sol | 17.6% | 19.1% | 17.6% |
| Terra | 22.5% | 21.6% | **19.6%** |
| Luna | 18.7% | 19.7% | **16.0%** |

Observation-known invalids fell to 196 at high, from 252 at low and 247 at medium.
Unavailable-resource/access failures fell to 309 from 355 and 341. Conversely,
target/carry failures rose to 45 at high from 22 and 26, suggesting that more elaborate
plans still overreached physical inventory or capacity constraints.

### No general survival improvement

Survival was not monotonic: low retained 12 agents, high 11, and medium only 8.

| Model | Low | Medium | High |
| --- | ---: | ---: | ---: |
| Sol | 5/5 | 5/5 | 5/5 |
| Terra | 4/5 | 0/5 | 4/5 |
| Luna | 3/5 | 3/5 | 2/5 |

This substantially changes the interpretation of the prior medium run. Terra is not
simply unable to play the world: its all-agent collapse did not repeat at either low
or high reasoning. The medium trajectory appears stochastic or path-dependent rather
than a stable Terra property. Sol's perfect survival was the only model outcome that
repeated across all three conditions.

High also did not produce more capital formation. Low and medium each built two
productive structures; high built one. No condition formed a group, contract,
cooperative asset, fee policy, or dividend system. A high-reasoning Terra agent made
the comparison's only tile claim, but no institution developed around it.

## Cost and actual reasoning used

Reasoning effort worked technically, but the models consumed very different hidden
budgets:

| Model | Low | Medium | High |
| --- | ---: | ---: | ---: |
| Sol reasoning tokens/call | 192.9 | 294.5 | 414.4 |
| Terra reasoning tokens/call | 153.2 | 162.0 | 288.7 |
| Luna reasoning tokens/call | 282.4 | 416.8 | 916.1 |

Total reasoning tokens rose from 148,939 at low to 203,469 at medium and 379,174 at
high. Visible output stayed nearly flat at 64,070, 63,259, and 66,348 tokens. The extra
cost therefore purchased internal reasoning rather than longer visible plans.

High used 46.3% more exact simulation credits than low and 16.3% more than medium. The
three valid conditions totalled 1,307.848150 credits. The excluded low run consumed an
additional 421.234605 credits before its single failure was discovered. Because high,
the excluded low run, and the low retry overlapped, their account-level weekly-meter
deltas cannot be added; the available account bucket moved roughly from 23% to 33%
during the new work. Exact per-run simulation credits remain the reliable attribution.

## Interpretation and decision

One world seed cannot support a significance test. Agents affect one another, so the
15 agents are not independent replicates, and model sampling creates different social
and resource trajectories even with the same deterministic world. These measurements
are paired descriptive evidence, not causal estimates.

For now, keep low reasoning as the efficiency default. It delivered the best survival
and lowest cost. High reasoning is a promising experimental treatment when the outcome
of interest is trade coordination or currency use: it bought a modest validity gain
and much better settlement discipline, but not better survival or broader society
formation.

The next defensible experiment is a paired multi-seed low-versus-high replication.
Use independent world seeds as the statistical units. The primary preregistered
outcomes should be trade conversion, meeting failures per attempted acceptance,
coin-denominated completed trades, invalid-action rate, survival, and productive asset
value. That would tell us whether high reasoning's commerce advantage is real enough
to justify its 46% credit premium.
