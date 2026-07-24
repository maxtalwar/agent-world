# Opus 5 mixed-civilization benchmark

## Question

How does Claude Opus 5 perform relative to Opus 4.8 when it replaces the Opus
cohort inside an otherwise identical mixed Agent World civilization?

## Design

The treatment study is:

`runs/experiments/opus-5-vs-4-8-mixed-30a-40t-seeds11-41-20260724-175444`

It reuses the two standard `stateless-v1` cells from:

`runs/experiments/stateless-v1-v3-civilization-30a-40t-seeds11-41-20260723-174150`

as the Opus 4.8 controls. The paired world seeds are 11 and 41. Every cell has
six Sol, six Terra, six Luna, six Opus, and six Sonnet agents and runs for 40
ticks. The only treatment change is:

- control: `6@claude:claude-opus-4-8`
- treatment: `6@claude:claude-opus-5`

All cells use `organic-generalists`, medium reasoning, baseline feedback, raw
decisions, simultaneous resolution, `stateless-v1`, stateless conversations,
stratified assignment seed 117, eight global workers, and four workers per
provider. An automatic tick-5 health gate rejects a cohort with at least two
failures and a failure rate above 20%.

Both existing controls completed tick 40 and passed the health gate. The seed
41 control had one isolated Sonnet decision failure, while its Opus 4.8 cohort
had none. The controls ran at commit `0a05b0f`; the only repository changes
between that commit and treatment launch state `cf99d93` were experiment
documentation. There were no changes under `agent_world/` or `tests/`.

## Interpretation policy

The comparison is a paired-seed replacement experiment, not 12 independent
Opus agents. Opus behavior can change the world seen by every other cohort, so
the analysis must examine both direct Opus outcomes and civilization-wide
spillovers.

Primary direct outcomes are provider reliability and latency, invalid proposals
per submitted action, contention separately, survival and death timing,
production, consumption, construction, ownership, trade, gifts, and
communication. Civilization outcomes include total survival, damage, wealth,
inequality, reserves, resource flows, entrepreneurship, commerce,
communication, cooperation, groups, institutions, and cross-cohort interaction
matrices.

Claims about Opus 5 should require the same direction across both paired seeds.
Failures must be normalized by submitted actions or decisions; economic
activity should be normalized by successful calls or starting population where
appropriate. Unchanged cohorts provide evidence about both systemic spillovers
and ordinary run-to-run variation.

## Completion and data quality

Both Opus 5 cells completed tick 40, passed the startup health gate, recorded
100% usage coverage, and had no model, quota, or provider failures. Both
controls also passed their health gates. The seed 41 control's single isolated
model failure came from Sonnet, not Opus 4.8.

The submitted-action denominator below is the number of actions in recorded
`agent_response` decisions. Contention is kept separate because it does not
represent a planning error.

## Direct Opus result

The direct result is large and directionally replicated. Opus 5 was a much
better raw planner, survived more reliably, and became a much more active
builder and economic coordinator.

| Direct Opus outcome, pooled | Opus 4.8 | Opus 5 |
|---|---:|---:|
| Survivors | 10/12 | 12/12 |
| Submitted actions | 1,567 | 1,653 |
| Invalid proposals | 571 (36.4%) | 210 (12.7%) |
| Contention failures | 8 (0.5%) | 18 (1.1%) |
| Action-point exhaustion errors | 90 | 4 |
| Communications | 428 | 816 |
| Trade offers / accepts | 69 / 6 | 107 / 18 |
| Gifts sent | 0 | 20 |
| Completed assets owned | 1 | 9 |
| Owned asset replacement value | 30 | 146 |
| Construction contribution value | 30 | 111 |
| Prompt tokens per call | 6,944 | 7,313 |
| Output tokens per call | 577 | 1,174 |
| Mean decision latency | 10.02 s | 17.99 s |
| Prompt cache share | 60.3% | 56.8% |

The invalid-proposal result is not a death-timing artifact. Opus 5 improved
from 38.6% to 13.9% in seed 11 and from 34.2% to 11.6% in seed 41. It submitted
slightly more actions per decision while almost eliminating action-point
overflow, showing materially better budget planning rather than simple
caution. Invalid gathering, fishing, consumption, and movement attempts also
fell sharply. Contention roughly doubled, but remained near 1% and reflects the
more active agents colliding with other simultaneous actors rather than faulty
plans.

Opus 5 also changed economic style. Across the two worlds it owned seven farms,
one workshop, and one well; Opus 4.8 owned one structure total. It started or
completed more construction, performed maintenance, created all four observed
access-fee policies, broadcast far more often, and sent twenty gifts after
Opus 4.8 sent none. Opus 5 participated in most completed trades, although the
conversion of its own offers was not consistently better across both seeds.

The performance came with a material usage cost. Opus 5 used 5.3% more prompt
tokens per call, 103% more output tokens, and had 80% higher mean per-call
latency. Parallel execution limited the wall-clock increase to roughly 8%, but
Claude plan-limit consumption is not exposed precisely enough to translate the
token increase into an exact quota cost.

## Civilization result

| Civilization outcome, pooled | Opus 4.8 worlds | Opus 5 worlds |
|---|---:|---:|
| Survivors | 49/60 | 50/60 |
| Invalid proposals / submitted actions | 2,211/7,496 (29.5%) | 1,674/7,595 (22.0%) |
| Contention failures / submitted actions | 50 (0.7%) | 92 (1.2%) |
| Survival-damage events | 630 | 566 |
| Complete structures | 11 | 14 |
| Fixed-asset replacement value | 154 | 266 |
| Stored inventory value | 118 | 52 |
| Trade offers / accepts | 180 / 21 | 250 / 33 |
| Accepted trade value | 113 | 203 |
| Gift events / value | 21 / 42 | 43 / 82 |
| Communications | 1,258 | 1,740 |
| Liquid inventory wealth | 791 | 722 |
| Upkeep paid / missed | 11 / 10 | 2 / 20 |

Both Opus 5 worlds produced more fixed capital, market activity, accepted trade
value, gifts, and communication. Trade latency also fell in both seeds. This
looks like a more entrepreneurial and socially active civilization, with Opus
5 occupying a hub role rather than merely surviving well in isolation.

It was not an unqualified improvement. The additional capital was poorly
maintained: paid upkeep fell while missed cycles doubled. Storage inventories
and liquid wealth also fell, so the economy shifted toward fixed productive
assets without clearly increasing total accumulated wealth. No groups or
contracts formed in either condition. Overall survival improved by only one
agent despite the striking Opus-level gain.

The most important spillover was cohort displacement. Sol survival improved
from 11/12 to 12/12, Terra from 7/12 to 10/12, Luna from 11/12 to 12/12, and
Opus from 10/12 to 12/12. Sonnet moved in the opposite direction, falling from
10/12 to 4/12, with a decline in both seeds. Sonnet's invalid-proposal rate
actually improved in both treatment worlds, so the deaths cannot be explained
as simpler planning failure. More aggressive resource use, movement, commerce,
or social leadership by Opus 5 may have changed the competitive environment,
but two mixed-world replications cannot identify which mechanism caused the
loss.

The world-wide invalid-proposal reduction also was not solely arithmetic from
replacing Opus. Sol, Terra, and Sonnet improved in both paired worlds, while
Luna worsened slightly in both. That pattern is consistent with Opus 5 making
the surrounding world easier to coordinate for some cohorts, although world
divergence prevents a stronger causal claim.

## Conclusion

Opus 5 clearly outperformed Opus 4.8 as an Agent World participant. The
planning-error reduction, survival, construction, gifting, communication, and
economic participation all replicated. It is a strong candidate to replace
Opus 4.8 in the standard model roster when Claude usage is available.

The tradeoff is meaningful: Opus 5 is slower and roughly doubles output-token
load. Its stronger agency also changes the ecology around it. These worlds
became more capital-intensive and socially active, but not much more survivable,
and Sonnet suffered a replicated collapse. The benchmark therefore supports
"better agent" more strongly than "uniformly better civilization."

## Deferred follow-up

A pure Opus 4.8 versus pure Opus 5 comparison would measure model behavior
without mixed-model interactions, but it is not required for this first
benchmark. It remains useful if the mixed study reveals an important difference
that needs cleaner attribution. The present result makes that follow-up more
valuable, especially for separating Opus's direct planning advantage from the
negative Sonnet spillover.
