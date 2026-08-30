# Why capable agents ignored the town ledger

Date: 2026-08-30

Study: `ledger-affordance-causal-20260830-221534`

Status: complete, diagnostic-only (not benchmark or leaderboard evidence)

## Conclusion

The ledger was mechanically sound and the models were capable of using it. The
dominant failure was decision architecture: an optional institutional action
never entered the agents' planning procedure, and when agents were forced to
evaluate it they usually judged novelty relative to their own memory rather
than relative to the town's public knowledge.

At tick 0 of the reflection treatment, the ledger was empty and every agent had
private specialty and local-map information. Nine of ten Luna agents still said
some version of "no novel nonlocal information." The one agent that correctly
modeled the information asymmetry posted. Merely explaining that distant agents
could not see local facts did not solve this: perspective-only treatments
produced 0/100 notes whether posting cost one action point or zero.

The successful intervention was a conditional public-novelty rule: compare a
concrete specialty, resource, supply, need, or offer fact with recent public
notes; post it when it is useful beyond local range and absent; do not repeat
unchanged facts. Under the original four-action output limit and one-action-point
price, this produced 24 notes from all 10 Luna agents versus 0 in the matched
exact-shape control. A matched Sol cell moved from 1 note by 1 author to 29 notes
by all 10 authors.

## Evidence base

Before intervention, 27 preserved organic-world reports contained 8,684 model
decisions from Luna, Sol, Grok 4.5/4.6, and DeepSeek variants and zero authored
ledger notes. The study added 30 valid isolated cells and 3,400 decisions. Every
cell used seed 11, retained raw I/O and lifecycle manifests, launched from a
clean pinned commit through `scripts/run-isolated-cohort`, and performed the
single tick-5 startup gate. The study used Luna for mechanism discovery, then
Sol and longer Luna cells for validation.

Six initial stage-two cells were stopped and quarantined after a new
message-channel treatment exposed a second in-process validator still using the
old hard-coded response schema. Correct ledger-mode outputs were converted to
failure waits in those cells. The validator was patched, all six cells were
restarted from a new commit and cohort ID, and only the repaired results below
are counted. A 24x24 long-run launch also failed at preflight because the
handcrafted map supports 16x16 or 32x32; it spent no model calls and was
restarted at 32x32.

## Hypotheses and tests

| Hypothesis | Intervention | Result | Conclusion |
|---|---|---:|---|
| Mechanics or prompt exposure was broken | Code audit, retained Sol prompt, unit tests, mandated control | Mandated: 25/100 notes | False. The action worked and models could execute it. |
| The feature was merely too obscure | Concise top-level salience | 0/100 | Insufficient. |
| One AP made local speech dominate | Free ledger | 0/100 | Not the primary cause. |
| Empty-board cold start/social proof | Generic founding note; two realistic peer notes | 0/100; 0/100 | False as a sufficient explanation. |
| Neutral incentives were too weak | Collective objective | 0/100 | Insufficient. |
| Several small frictions jointly blocked it | Salient + free + seeded | 0/100 | False for those factors. |
| Ledger belonged in the messages array | Free and one-AP message-channel modes | 0/100; 0/100 | Wrong output category was not the root cause. |
| Four output slots suppressed a zero-cost fifth action | Exact shape, free, five slots | 1/100 | Minor threshold effect only; not robust. |
| Exact shape, slot, or price was individually decisive | Four/free; four/1 AP; five/1 AP | 0/100 in all three | No. |
| One concrete post would create contagion | Only agent-1 bootstrapped | 1 required post, 0 follow-ons | No. |
| Agents omitted the option from deliberation | Require intent to say LEDGER POST/SKIP, posting optional | 9 notes, 7 authors | Supported. Evaluation alone unlocked some use. |
| Agents saw no private value | Explain discovery, trade, and aid value | 19/100 free; 14/100 original price | Supported as a secondary factor. |
| Agents needed an actionable request | Town requests local reports | 10 notes at tick 0, none later | Supported for one-shot compliance, not durable adoption. |
| Public novelty was mis-modeled | Define novelty against recent public notes | 23/100 free; 24/100 original price | Strongly supported. |
| Perspective explanation alone was sufficient | Explain what distant agents cannot see | 0/100 free; 0/100 original price | False. Knowledge must be coupled to a decision trigger. |

All 100-decision cells above used 10 Luna agents except the matched Sol
validation described below. The mandated and bootstrap cells are positive
controls, not voluntary-adoption evidence.

## Key treatment results

| Cell | Model | Mechanics | Notes | Authors | Pattern |
|---|---|---|---:|---:|---|
| Historical organic corpus | Five model variants | Original | 0 / 8,684 decisions | 0 | No natural adoption |
| Stage-1 baseline | Luna | Original | 0 / 100 | 0 | Replicated failure |
| Mandated capability | Luna | Original | 25 / 100 | 10 | Capability positive control |
| Action-5 salient/free | Luna | Free, 5 slots | 1 / 100 | 1 | Weak combined-friction effect |
| Reflection | Luna | Free, 5 slots | 9 / 100 | 7 | Explicit evaluation changes behavior |
| Private value | Luna | Free, 5 slots | 19 / 100 | 10 | Motivation helps |
| Decision rule | Luna | Free, 5 slots | 23 / 100 | 10 | Broad, updated reports |
| Decision rule, original friction | Luna | 1 AP, 4 slots | 24 / 100 | 10 | Minimal mechanism-preserving fix |
| Private value, original friction | Luna | 1 AP, 4 slots | 14 / 100 | 8 | Partial alternative |
| Sol baseline | Sol | 1 AP, 4 slots | 1 / 100 | 1 | Matched failure |
| Sol decision rule | Sol | 1 AP, 4 slots | 29 / 100 | 10 | Cross-model replication |
| Long decision rule | Luna, 20 agents | 1 AP, 4 slots | 141 / 500 | 20 | Posts on 23/25 ticks |
| Compact production default | Luna | 1 AP, 4 slots | 18 / 100 | 10 | Production wording passed |
| Compact production default | Sol | 1 AP, 4 slots | 18 / 100 | 10 | Production wording passed |

The longer Luna run had 130 unique author/title pairs among 141 notes; only 11
notes repeated an author/title topic. This is frequent use, but not a per-tick
mandate or exact-repeat flood. It reported newly encountered coordinates and
changed conditions through tick 24. All 20 agents survived and all 500
decisions completed without model-output failures.

## What agents did with the working ledger

The successful Luna cells posted specialties, precise food/water/fiber/wood/ore
coordinates, fishing locations, an active farm, depleted sites, unmet needs,
and offers. One original-friction Luna note advertised an active farm at
`[6,8]`; the next reported a miner's food-for-stone need; the final note offered
food for coin.

Sol went further. In the matched baseline it produced one note and no contract
events. With the decision rule it posted 29 notes, proposed six contracts,
accepted four, and settled three. The ledger carried:

- a crafter's food-for-stone and food-for-wood proposals to known specialists;
- active-contract status and later settlement;
- open stone-for-food offers;
- moving/depleted fishing spots;
- a correction retracting a false water coordinate;
- a completed farm seeking water; and
- an artisan's urgent two-coin water contract.

The compact production wording also generalized: Luna and Sol each produced
18 notes from all 10 agents with zero decision failures. Sol proposed 12
contracts and accepted five in that replication, though none settled within
its 10 ticks. This separates the shared affordance failure from downstream
model capability: both models can operate the board after the fix, while Sol
is much more likely to turn public information into enforceable exchange.

## Root cause

The original interface described a feature, not a decision condition. The
ledger appeared at the end of a long action catalogue and again in a mechanics
section. Agents could recite and obey it when commanded, but their default
planner prioritized immediate survival and local interaction. An empty
`town_ledger` did not itself become a reason to act.

Three causal components matter:

1. **Option neglect.** Without an explicit comparison step, the optional
   institutional action was rarely evaluated at all. Reflection alone raised
   use from zero to nine notes.
2. **Self-relative novelty.** When forced to evaluate, most agents treated
   facts familiar to themselves as non-novel even though those facts were
   private and the public ledger was empty.
3. **Weak private motivation.** Explaining that publication enables discovery,
   trade, and aid increased use, but less reliably than an operational public-
   novelty rule.

Action cost, output slots, exact schema grounding, and salience were real
frictions. Removing all three once produced one spontaneous note. None was the
root cause, and the final solution leaves the mechanics unchanged.

## Implemented fix

Organic worlds now use a compact default ledger rule that states:

- the ledger is durable and world-global;
- distant agents cannot see local facts;
- useful specialty/resource/supply/need/offer facts should be compared with
  recent public notes;
- the exact `post_ledger_note` JSON shape; and
- unchanged facts should not be repeated.

The old terse behavior remains available as `town_ledger_prompt_mode=legacy`
for historical reproduction. The one-AP ledger price and four-action output
limit remain unchanged. Duplicate ledger prose was removed from the default
static context, leaving it at 7,678 characters against the existing 7,800
budget. The complete 425-test suite passes.

## Limits and next questions

This is a seed-11 diagnostic campaign, not a benchmark score. The causal
contrast is strong because many mechanisms were matched within one seed, but
future work can test seed variability and other providers. The longer world
shows high but mostly varied board traffic; worlds above 20 agents may benefit
from a compact personal last-post field or better public summaries so the
eight-note window does not encourage paraphrased refreshes.

The decision rule unexpectedly activated Sol's contract system, but did not do
so for Luna. That suggests a useful next experiment: apply the same explicit
trigger design to contracts, groups, agreements, and access rules, then test
which institutions are blocked by option neglect versus actual planning
limits.

## Artifacts

Study manifests and run outputs:
`runs/experiments/ledger-affordance-causal-20260830-221534/`.

Pinned treatment commits begin at `abae2f1`; conditional-schema repair is
`a419f45`; the compact production default is `1bb3dc1` and its validation
manifest is `79f25d8`.
