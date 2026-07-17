# Analysis: Sol, Terra, and Luna at medium reasoning

## Question and design

How do five `gpt-5.6-sol`, five `gpt-5.6-terra`, and five `gpt-5.6-luna`
agents behave in the same organic generalist world when all three cohorts use medium
reasoning?

The run used world seed 11, stratified model assignment seed 117, `compact-v2`
observations, raw decisions, simultaneous turns, four Codex workers, and 50 target
ticks. It completed all 50 ticks with 685 successful model calls and no LLM failures.
The run was left unattended until the process exited; analysis began only after the
artifacts were complete.

Canonical artifacts are in this directory:

- `run.jsonl`: raw event stream
- `run-snapshot.json`: final world snapshot
- `run-manifest.json`: exact command, settings, assignments, and provenance
- `run-usage.jsonl` and `run-plan-usage.json`: model and plan usage
- `run-report.json` and `run-report.md`: generated report
- `run-checkpoint.pkl`: restorable checkpoint

## Headline result

The run was mechanically reliable but socially modest. Eight of fifteen agents
survived. Sol had the clearest adaptive advantage: all five Sol agents survived and
Sol agents built both productive structures. All five Terra agents died, while three
of five Luna agents survived. The world produced five completed trades and ten gifts,
but no groups, contracts, tile claims, or cooperative construction.

| Cohort | Survived | Calls | Proposed | Invalid | Waits | Food + water gathered | Offers / completed from offers | Structures | Credits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Sol | 5/5 | 250 | 858 | 164 (19.1%) | 179 | 94 | 6 / 1 | 2 | 304.280025 |
| Terra | 0/5 | 202 | 672 | 145 (21.6%) | 236 | 40 | 11 / 1 | 0 | 85.090612 |
| Luna | 3/5 | 233 | 628 | 124 (19.7%) | 100 | 75 | 11 / 3 | 0 | 52.724245 |

`Completed from offers` attributes a successful offer to the model that created it;
the accepted-action counts in the generated report instead attribute the accepting
action. Deaths censor later decision and action counts, especially for Terra.

## Why Terra died

The evidence points to weak survival execution rather than provider or parsing
failure:

- Every Terra decision returned successfully. All cohorts received the same static
  game context and the same context format.
- Terra generated 236 waits in only 202 decisions, compared with 179 waits in 250 Sol
  decisions and 100 waits in 233 Luna decisions. Multiple actions can occur in one
  decision, so this is not a percentage of turns; it measures how often plans spent
  action slots resting instead of changing the resource situation.
- Terra gathered only 27 food and 13 water. Sol gathered 46 food and 48 water; Luna
  gathered 48 food and 27 water.
- Terra suffered 99 survival-damage events. Water was empty in 78 and food was empty
  in 40. All five Terra agents eventually died at ticks 33, 35, 41, 42, and 46.
- The most extreme case was agent 13: it moved only nine times, waited 61 times,
  gathered seven total resource units, and died at tick 35.
- Terra did attempt commerce: it created 11 offers and participated in three accepted
  trades. The volume was too small and too unreliable to repair its subsistence
  deficit.

Geography contributed but does not explain the whole split. Mean Manhattan spawn
distance to water terrain was 2.2 tiles for Sol, 3.2 for Terra, and 3.4 for Luna. Sol
therefore had a modest positional advantage over Terra, but Luna began slightly
farther from water than Terra and still retained three survivors. Nearby matched
examples also diverged: Terra agent 7 began one tile from water and died, while Luna
agent 2 began two tiles from water and survived. This remains descriptive because
agents interact inside one shared world.

## Economy and society

- Agents created 28 offers; five completed, for 17.9% offer conversion. All 28 were
  observed by their counterparties, 19 drew an acceptance attempt, 13 reached a
  settlement check, and five settled.
- Completed exchange moved food for water three times, food for coin once, and fiber
  for food once. These were physical, local settlements rather than teleported goods.
- Ten gifts moved 16 units of book value. Six were food or water and four were
  materials. All gifts crossed between ungrouped agents.
- Sol agent 15 built a farm plot and Sol agent 6 built storage. They were individually
  owned and maintained; no cooperative build occurred.
- There were no groups, contracts, claims, or paid access policies. Three free access
  grants occurred.

This is more genuine commerce than the early gifting-dominated worlds, but not a
self-sustaining market system. Trade remained mostly emergency barter and did not
prevent seven deaths.

## Reliability and invalid actions

The model boundary itself was clean: 685 calls, zero failures, complete usage records,
and identical static rules/context format across all three cohorts. The run produced
433 invalid actions out of 2,158 proposed actions (20.1%). Most were resource failures:
341 were unavailable resource or access attempts. Trade coordination/state caused 29,
target or carrying constraints 26, action budget or energy 14, movement/occupancy 12,
and other causes 11.

The simultaneous resolver remains a material confound. The report identifies 404
invalid actions that followed prior same-tick resolutions the acting agent could not
observe, and invalidity rose from 17.8% in early activation positions to 22.4% in late
positions. That does not mean all 404 were caused by stale state; it marks the set that
could have been affected.

## Reasoning and usage

Medium reasoning did not translate into an equal hidden-reasoning budget across model
families. Recorded reasoning tokens per call were approximately 295 for Sol, 162 for
Terra, and 417 for Luna. This run has no low-reasoning control, so it cannot tell us
whether medium reasoning improved any outcome.

The simulation used 9,441,751 prompt tokens, of which 5,708,288 were cached, plus
266,728 output tokens and 203,469 reasoning tokens. Exact run-scoped usage was
442.094882 Codex plan credits: 304.280025 Sol, 85.090612 Terra, and 52.724245 Luna.
Actual API cost was $0 because the run used ChatGPT-plan billing. Account telemetry
showed the available 10,080-minute primary bucket moving from 18% to 22% used. That
four-point delta is account-level and can include other Codex activity; no separate
five-hour bucket was exposed for this run.

Sol consumed 68.8% of run credits. Its rate card is substantially higher than Terra
or Luna, so the cost split should not be mistaken for a token-volume split.

## Interpretation, uncertainty, and next experiment

The credible finding is that this particular Sol cohort managed survival and
investment much better than the Terra and Luna cohorts without any connector-quality
advantage. The all-Terra collapse is important enough to replicate, but one seed is
not a model ranking: model labels, positions, agents, resources, and social feedback
all interact inside the same world, and later action counts are censored by death.

Do not change the world or prompt to rescue Terra on this evidence alone. The next
useful experiment is a paired multi-seed replication with the same population and
assignment strategy. If the goal is specifically to measure reasoning effort, run
matched low-versus-medium conditions at the same world and assignment seeds and use
world-seed pairs as the statistical units. Add a report diagnostic for feasible
survival opportunities declined in favor of waiting; it would separate lack of local
resources from planning failure without nudging agent behavior.
