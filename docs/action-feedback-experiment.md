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

The paired seed-11/seed-41 follow-up uses `action_feedback_mode=minimal` with all
Phase 1 controls unchanged. An agent receives at most five compact records from
the immediately preceding tick, each containing only the tick and failed action
type. It receives no failure reason, attempted arguments, format correction, or
private failure event. This isolates a terse outcome signal from the explanatory
baseline history without changing world resolution or repairing a plan.

## Planned follow-up treatment

After Phase 1, two additional matched treatments can isolate feedback content:

- causal feedback: concise explanations for proven contention failures

The causal runs remain deferred to avoid provider-plan quota pressure. They should reuse the same paired seeds, roster, assignments, world configuration, reasoning effort, and concurrency.
