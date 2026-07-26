# GPT-5.4 provisional Participant v2 benchmark

## Result and quality

GPT-5.4 completed the predeclared seed-11 Participant v2 trial: ten homogeneous
agents, 40 ticks, medium reasoning, baseline feedback, raw simultaneous
decisions, and the stateless-v3 connector. The run completed all 400 decision
opportunities with no model, provider, quota, or usage-ledger failure. It
therefore qualifies as a **provisional benchmark**. A clean seed-41 replication
would promote it to replicated certification.

Run root:
`runs/benchmarks/gpt-5-4-participant-v2-provisional-seed11-20260725-041235`

> **Primary benchmark scorecard**
>
> | Benchmark | GPT-5.4 seed 11 |
> |---|---:|
> | **Planning execution** | **86.54** |
> | **Sustained competence** | **78.45** |
> | **Entrepreneurial agency** | **22.17** |

## Supporting objective results

| Outcome | GPT-5.4 seed 11 |
|---|---:|
| Completed horizon | 40/40 |
| Decisions | 400/400 |
| Submitted actions | 1,391 |
| Invalid proposals / submitted actions | 186/1,391 (13.4%) |
| Contention failures / submitted actions | 9/1,391 (0.6%) |
| Action-point overruns | 4 (0.3%) |
| Survivors | 9/10 |
| Endpoint population health | 59.9% |
| Survival exposure | 100% |
| Living-accessible terminal value | 173 |
| Material outcome versus 240 target | 72.08% |
| Venture initiatives | 17 |
| Realized venture value | 37 |
| Structures complete / in progress | 3 / 1 |
| Trade offers / accepted | 14 / 2 |
| Communications | 67 |
| Gifts / groups / cooperative builds | 0 / 0 / 0 |
| Wealth Gini | 0.2085 |

Planning was the clearest strength. After excluding nine same-tick contention
losses, 86.54% of proposed actions were executable. Only four proposals
exhausted the action-point budget. Invalid proposals were instead concentrated
in resource-state and proximity errors: 83 explicitly involved unavailable
water or consuming water not held, 16 attempted out-of-range whispers, and 10
attempted fishing without fishable food. Water therefore remained the main
world-modeling weakness despite the strong aggregate planning score.

## Civilization shape

The population developed into a dispersed private-homestead economy. Agents
claimed nine tiles beginning at tick 5. A farm plot was started at tick 14 and
two farms were complete by tick 16; a third was completed at tick 33. An
individually owned storage project began at tick 18 but still lacked all four
wood inputs at the end. The capital stock was therefore three private farms
worth 30 realized value and one stranded construction project.

Farm activity was real but concentrated. Agents added 23 food to farm plots and
harvested 10 food from improved land. One farm received repeated maintenance
and remained active, one had missed upkeep and ended inactive, and the newest
farm had little time to produce. There were four maintenance actions, split
between two paid and two missed upkeep cycles. GPT-5.4 understood construction
and maintenance, but it did not create a shared production system.

The broader extraction economy produced 109 wild or fished food, 79 water, 66
fiber, 12 wood, 3 ore, and 3 stone before counting farm additions. Final
living-accessible value reached 173, 2.16 times the starting endowment, but
remained below Participant v2's three-times-endowment excellence target.
Terminal liquid wealth was moderately unequal rather than extremely
concentrated (Gini 0.2085).

## Survival

Survival damage began at tick 14 and persisted, but the population avoided a
general collapse. The sole death occurred at tick 39 from hunger: the agent had
water and energy but no food. The nine survivors averaged 66.6 health. Their
mean food, water, and energy reserves were 8.8, 12.2, and 26.9 respectively;
only one survivor had zero food and none had zero water.

The endpoint was healthy enough to support a competence score of 78.45, but it
was not secure. Two survivors finished at 8 and 35 health, and 83 survival
damage events show that much of the population repeatedly operated near a
subsistence boundary. Participant v2 correctly reflects this through 59.9%
endpoint population health rather than treating nine survivors as perfect
survival.

## Commerce and social organization

Commerce emerged late and mainly as a response to water scarcity. The first
offer appeared at tick 21 and the first acceptance at tick 32. Fourteen offers
produced two successful exchanges, a 14.3% conversion rate:

- two coin for one water;
- one wood for one water.

Acceptance latency was one and two ticks. Six offers expired, four were
rejected, and two remained open. The accepted exchanges were small, but they
demonstrate actual price-bearing resource reallocation rather than merely
trade chatter.

Communication also focused heavily on finding, requesting, and transporting
water. The agents produced 67 say, broadcast, or whisper events. Nevertheless,
there were no gifts, groups, contracts, access-fee policies, public assets, or
cooperative builds. Every structure had a single private owner, and no farm was
publicly accessible. The resulting society was market-adjacent but not
institutional: autonomous homesteads occasionally exchanged emergency goods.

## Entrepreneurship interpretation

GPT-5.4 earned 22.17 entrepreneurial agency from 17 recorded initiatives and
37 realized value. Realized value combined 30 from completed productive assets
and 7 from accepted trades. This is meaningful positive enterprise, unlike a
model that merely posts unsuccessful offers, but it remains far below the
benchmark's excellent initiative and realization rates.

There is one small conservative scoring edge case. Agent 7 constructed a farm
in a single successful `build` event, so it counted toward realized asset value
but not the initiative counter, which currently recognizes `build_started`
events. Counting that direct build as a construction start would raise the
initiative count from 17 to 18 and entrepreneurial agency from 22.17 to about
22.81. The official frozen Participant v2 value remains 22.17 unless the suite
definition is revised.

## Usage

| Usage | GPT-5.4 |
|---|---:|
| Calls | 400 |
| Prompt tokens | 4,765,929 |
| Output tokens | 354,249 |
| Reasoning tokens | 308,022 |
| Prompt tokens/call | 11,914.8 |
| Output tokens/call | 885.6 |
| Cached input share | 58.4% |
| Mean / median call latency | 23.85 s / 17.27 s |
| P95 / maximum call latency | 34.91 s / 323.18 s |
| Wall time | about 2 h 17 min |

The account-level general Codex allowance moved from 95% to 99% during the run,
a four-percentage-point observed delta that can include concurrent account
activity. Exact simulation credits are unavailable because GPT-5.4 is not yet
in the local rate card. The 400 simulation calls themselves have complete token
coverage.

## Takeaway

GPT-5.4's provisional profile is **accurate, survival-capable, and moderately
entrepreneurial**. It created durable food production and a functioning, if
small, emergency water market while making very few AP-budget mistakes. Its
weaknesses were repeated water-state errors, uneven individual health, limited
trade conversion, and almost no collective organization. Seed 41 is necessary
before claiming that the survival, farm-building, and commerce pattern
replicates.
