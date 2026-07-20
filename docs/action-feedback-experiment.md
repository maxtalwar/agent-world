# Action Feedback Experiment

This study tests how failed-action feedback changes model behavior without changing action resolution or repairing agent plans.

## Failure attribution

The engine records two researcher-visible failure types:

- `invalid_action` with `data.failure_type=invalid_proposal`: the proposed action was impossible for reasons not proven to result from another agent's earlier action in the same tick.
- `contention_failure` with `data.failure_type=contention_failure`: the engine can prove that another agent successfully changed the shared state earlier in the same tick. The event also records a structured `contention_cause`.

Classification is deliberately conservative. Current proven contention categories include resource depletion, destination occupancy, competing trade resolution, item-pile pickup, tile claims, and same-tile construction starts. Ambiguous failures remain invalid proposals. Neither classification changes the submitted action, AP consequences, resolution order, or outcome.

## Phase 1: baseline feedback versus none

Experiment root:

`runs/experiments/action-feedback-baseline-v-none-30a-50t-seeds11-41-20260718-203958`

The study uses two paired seeds. Each seed runs once with the existing baseline feedback and once with no failed-action feedback:

| Pair | World seed | Feedback treatment |
|---|---:|---|
| 1A | 11 | `baseline` |
| 1B | 11 | `none` |
| 2A | 41 | `baseline` |
| 2B | 41 | `none` |

All other controls are fixed:

- preset: `organic-generalists`
- population: 4 Sol, 4 Fable, 5 Terra, 5 Opus, 6 Luna, 6 Sonnet
- reasoning effort: `medium`
- ticks: 50
- assignment: stratified, seed 117
- decision mode: raw
- turn resolution: simultaneous decisions with rotating deterministic resolution priority
- concurrency: 8 global workers, 4 Codex workers, 4 Claude workers

`baseline` preserves the existing prompt instruction and up to five recent failed-action records. `none` removes the instruction, the `recent_action_feedback` payload, and the agent's private failure events from `recent_events`. Research logs and reports retain all failures in both treatments.

The paired analysis should compare survival, action-failure composition, repeated-error behavior, communication, trade offers and acceptances, gifts, movement/exploration, construction, institutions, specialization, and per-model cohort differences. Provider or quota failures invalidate an affected run rather than being interpreted as treatment effects.

## Phase 2: minimal feedback

Experiment root:

`runs/experiments/action-feedback-minimal-30a-50t-seeds11-41-20260719-003342`

The paired seed-11/seed-41 follow-up uses `action_feedback_mode=minimal` with all
Phase 1 controls unchanged. An agent receives at most five compact records from
the immediately preceding tick, each containing only the tick and failed action
type. It receives no failure reason, attempted arguments, format correction, or
private failure event. This isolates a terse outcome signal from the explanatory
baseline history without changing world resolution or repairing a plan.

## Results

Both minimal-feedback cells completed 50 ticks. Seed 11 had one Codex response
format failure and seed 41 had one Claude structured-output failure; neither had
a quota failure. The Phase 1 cells are clean only through tick 28: the old
Claude adapter failed to classify a session-limit response beginning at tick
29-32, so later Phase 1 behavior must not be compared with Phase 2.

Across the shared clean window (ticks 0-28), both seeds produced the same
ordering:

| Feedback | Failed proposed actions | Re-attempted failed action type next tick | Repeated same failure next tick | Survivors at tick 29 |
|---|---:|---:|---:|---:|
| none | 40.8% | 83.1% | 59.4% | 27/30 |
| minimal | 32.6% | 65.9% | 36.5% | 29/30 |
| baseline | 25.3% | 66.5% | 24.7% | 29/30 |

Minimal feedback therefore captured roughly half of baseline's overall failure
reduction and nearly all of its effect on whether an agent immediately tried the
same failed action type again. The remaining baseline advantage came from
causal correction: terse feedback changed what agents tried, while explanations
more often prevented the replacement plan from failing for the same reason.
Minimal feedback averaged about 44 characters per observation versus about 494
for baseline feedback.

The effect varied materially by model. Clean-window failure rates for
none/minimal/baseline were Sol 35.8/14.5/11.9%, Fable 23.1/15.8/14.9%, Terra
33.8/32.3/23.3%, Opus 58.1/42.1/35.9%, Luna 26.9/20.6/18.0%, and Sonnet
57.9/57.3/39.3%. Minimal feedback was nearly sufficient for Sol, Fable, and
Luna, while Terra, Opus, and especially Sonnet benefited from the explanatory
baseline.

Feedback also prevented agents from getting behaviorally stuck. Over the clean
window, average successful movement events were 412 with none, 558 with
minimal, and 595 with baseline. Both feedback treatments had two fewer deaths
per seed than no feedback by tick 29. Civilization-level effects were less
stable: baseline generated more trade offers but not more accepted trades, no
feedback generated more successful gifts, and construction did not have a
consistent treatment ordering across seeds.

The two complete minimal civilizations remained informal but economically
active. Seed 11 ended with 22 survivors, five completed structures, nine
accepted trades, eleven gifts, and a fee-charging farm that received fifteen
payments. Seed 41 ended with 21 survivors, eight completed structures, fourteen
accepted trades, thirteen gifts, and a three-agent cooperative storage build.
Neither formed a formal group. Across both seeds all Sol and Fable agents
survived; deaths were concentrated in Luna (7/12) and Sonnet (8/12). Fable was
the strongest builder/trader cohort, while Sonnet combined heavy communication
with a 60.8% full-run failed-action rate and produced no completed build,
accepted trade, or gift.

The supported conclusion is that feedback content is an experimental mechanism,
not merely interface polish. A tiny outcome signal substantially improves
planning and early survival at about one-tenth the feedback payload, but causal
explanations add real value for some models. Two seeds are directional
replication, not enough to establish small civilization-level effects.

## Phase 3: causal contention feedback

Experiment root:

`runs/experiments/action-feedback-causal-30a-50t-seeds11-41-20260719-145321`

The causal treatment keeps baseline explanations for invalid proposals and adds
a neutral, cause-specific explanation only for proven same-tick contention. It
states that another agent obtained the remaining resource, occupied the
destination, took the item, resolved the trade, claimed the tile, or started
construction before resolution. It does not identify that agent or change the
submitted action, AP cost, priority, or outcome.

The paired causal runs reuse seeds 11 and 41 and all Phase 1 controls.

### Phase 3 outcome: excluded

Both causal cells reached tick 50, but neither is valid for treatment
comparison. A shared provider/network incident produced 47 failed decisions in
seed 11 and 46 in seed 41 during ticks 0-2. The engine advanced those ticks as
fallback waits, permanently changing survival reserves and subsequent world
history. Seed 11 also recorded 21 unclassified Fable usage-credit failures at
ticks 44-49; the quota detector recognized `credits exhausted` but not the
actual phrase `out of usage credits`. Additional isolated timeouts and closed
responses occurred in both cells. Preserve the artifacts, but do not include
their survival, economy, or failure rates in feedback-treatment conclusions.

The causal payload itself was exercised: seed 11 had 55 proven contention
failures and seed 41 had 43, producing 310 and 241 model-facing causal-feedback
records as recent history persisted. Exploratorily, agents re-attempted the
same contended action type on the next tick about 75% of the time, versus 65%
under baseline. This could mean explicit attribution makes an action seem
temporarily unlucky rather than invalid, but the contaminated starting state
prevents a causal claim. A replacement run requires broader quota-string
recognition and pre-resolution handling for batch-level transport failures.

## Phase 4: matched no-Fable baseline versus causal

Experiment root:

`runs/experiments/action-feedback-baseline-v-causal-no-fable-28a-50t-seeds11-41-20260719-205858`

This new internally controlled block uses baseline and causal feedback on seeds
11 and 41. Every cell has the user-specified 28-agent roster: 4 Sol, 5 Terra,
5 Luna, 5 Opus, 5 Sonnet, and 4 Haiku. All other Phase 1 controls remain fixed.
Because both population size and composition differ, analyze only within-block
paired contrasts; do not combine its aggregate civilization metrics with the
earlier 30-agent studies.

### Phase 4 results

All four cells completed 50/50 ticks with no quota or rate-limit failures. The
runs had six isolated model-output failures in 5,059 decisions (0.12%); none was
a batch provider incident, so the four cells remain usable. Assignment maps
match within each seed. Causal explanations appeared in 85/1,203 observations
(7.1%) for seed 11 and 122/1,257 (9.7%) for seed 41.

The direct behavioral result is narrow. Causal feedback reduced literal
repetition of the exact contended action in both seeds: 15/29 to 11/24 in seed
11 and 25/41 to 7/17 in seed 41, or 57.1% to 43.9% pooled. Agents were about as
likely to try the same action *type* again (74.3% baseline, 73.2% causal), so
the added explanation changed parameters or targets more often than it changed
the broad strategy. Proven contention counts also fell in both seeds, from 29
to 25 and from 41 to 17, although contention is an endogenous world outcome,
not a pure planning-quality measure.

Planning-error improvement was not robust. Among submitted actions, the paired
invalid-proposal rates were 33.0% baseline versus 30.8% causal for seed 11 and
31.0% versus 30.9% for seed 41. The report's resolver-wide total failure rates
similarly changed from 25.2% to 23.8% and from 23.7% to 24.2%. Causal feedback
therefore produced one meaningful improvement and one essentially flat or
slightly worse pair, not evidence of a general error-rate reduction. Repetition
of the exact invalid proposal on the next tick rose from 38.8% to 42.5% pooled;
that spillover is consistent across the two pairs but could reflect diverged
world histories rather than attention competition.

| Seed | Mode | Submitted actions | Invalid proposals | Contention | Exact contention retry | Survivors | Offers / accepts | Gifts | Complete structures |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 11 | baseline | 4,070 | 1,341 (33.0%) | 29 | 15/29 | 20 | 89 / 5 | 11 | 3 farms |
| 11 | causal | 3,763 | 1,158 (30.8%) | 25 | 11/24 | 14 | 54 / 3 | 15 | 4 farms, 1 storage |
| 41 | baseline | 3,961 | 1,227 (31.0%) | 41 | 25/41 | 15 | 73 / 4 | 18 | 3 farms |
| 41 | causal | 3,898 | 1,206 (30.9%) | 17 | 7/17 | 18 | 72 / 3 | 16 | 2 farms, 1 storage |

The civilization effects split private capital formation from market
coordination. Across the two baseline worlds, agents built six farms with 60
book value. The causal worlds built six farms plus two storages with 92 book
value and stored 46 value in those storages. They made seven access grants
versus one, and paid seven upkeep cycles while missing eight, versus two paid
and fifteen missed under baseline. This was individual rather than cooperative
entrepreneurship: causal had no co-op build, group, contract, access-fee policy,
fee payment, or dividend. Seven of its eight structures were owned by Sol
agents; baseline ownership was spread across Sol, Luna, Opus, and Sonnet.

The extra capital did not create a stronger market. Causal worlds made 126
offers and completed six trades, versus 162 and nine under baseline. Invalid
acceptances fell from 98 to 70 only because acceptance attempts fell from 107
to 76; success per attempt was essentially unchanged (8.4% versus 7.9%). By
contrast, informal aid became slightly larger: gifts rose from 29 events / 31
units / 44 value to 31 events / 38 units / 56 value. Food spoilage rose from
106 to 128 events despite the new storage capital, suggesting that production,
storage, and distribution never became an integrated economy.

Communication also fell in both matched pairs, from 472 to 393 messages in
seed 11 and 472 to 399 in seed 41. Adjusting for the number of decisions, that
is about 0.363 to 0.322 messages per decision. Trade offers also fell in both
pairs. Because causal explanations appeared in only 7-10% of observations and
their total feedback payload was not larger on average, this is not simply a
token-count result. It is consistent with the semantic feedback redirecting
some attention from social coordination toward local plan correction and
private asset management, but two seeds cannot distinguish that mechanism from
path-dependent divergence.

Survival did not have a stable treatment direction. Seed 11 causal suffered a
large collapse from ticks 26-39 and ended 14 versus 20; seed 41 causal lost more
agents early but only two in the last ten ticks, ending 18 versus 15. Across
both seeds, Sol improved from 7/8 to 8/8 survivors, Opus stayed 9/10, Sonnet
stayed 4/10, Terra fell 5/10 to 4/10, Luna fell 8/10 to 7/10, and Haiku fell
from 2/8 to 0/8. Haiku's replicated loss is worth retesting, but its per-action
error change was inconsistent across seeds, so the current data do not identify
why it occurred.

Per submitted action, Sol's invalid-proposal rate improved in both seeds and
pooled from 15.7% to 14.2%. Terra worsened in both (23.8% to 27.2%) and Luna
worsened in both (20.8% to 23.5%). Opus, Sonnet, and Haiku had mixed seed-level
directions; their pooled rates are confounded by different death timing. The
intervention may therefore interact with model style rather than supplying a
uniform planning benefit.

The supported conclusion is that causal contention feedback helps agents avoid
copying the identical action after an unlucky simultaneous resolution, but it
does not yet justify claiming lower planning-error rates or a healthier
civilization. The most interesting directional signal is a shift toward
Sol-led private capital, storage, access grants, and upkeep alongside less
communication and trade. More matched seeds are needed before adopting causal
feedback as the default; the next replication should pre-register exact retry,
invalid-proposal rate, messages per decision, trade attempts, asset ownership,
and Haiku survival as its primary outcomes.
