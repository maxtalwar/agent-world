# Per-action execution and capacity feedback — 2026-09-05 Pacific

Implemented at the user's request after the first v8 ranking audit. No paid
model runs or score changes to admitted evidence were made.

## Capacity feedback fix

Inventory has a maximum carried weight, normally 10. Water weighs 2 per unit.
An agent carrying nine weight units cannot collect one more water, even when
its tile or well has water available. Gathering first checks the source, then
limits collection by remaining carrying capacity.

The old capacity failure said “No water is available.” The new message states
the resource, current load and limit, and suggests using, dropping or storing
cargo to make room. True resource absence retains a distinct message.
Zero requested quantity is also distinct. The fix applies to extraction from
tiles, adjacent water and wells. It changes feedback, not capacities, resources,
costs or turn ordering. Active studies remain on their pinned source.

## Per-action Execution

The registered participant-v8-action-review recipe uses the existing
outcome-production policy with execution_unit set to action. Published
participant-v8 omits the parameter and retains whole-decision scoring and its
original recipe digest. This review is not the new default leaderboard.

Execution = 100 * successful actions / submitted non-contention actions.

Each action and each message counts once. A three-action plan with two
successes and one failure scores 66.67; valid work remains credited.
Two error events from the same proposal still count as one failed action.
Contention is excluded from both numerator and denominator.
An action skipped because the plan exhausted its AP earns no success credit.
All remaining skipped actions are counted, including those after the engine's
existing stop point. Actual execution order and stop behavior are unchanged.

Valid waits count as actions. An empty action list performs the engine's
existing implicit wait, recorded once. A malformed model response with no
attributable proposals counts as one failed proposal; its fallback wait never
earns credit. Provider and harness failures remain integrity blockers.
The score is feasibility, not usefulness: easy valid actions can improve the
ratio. Capability and Production carry strategic outcomes separately.

The engine attaches versioned lists of outcomes to the private agent_response
record, separately for actions and messages. This avoids guessing successful
actions from missing errors, matching identical action objects ambiguously,
counting one proposal's multiple errors twice, or counting an unexecuted tail
as successes. These records are excluded from agent observations alongside
the existing response transcript. Existing ledgers without the telemetry cannot
claim this scoring recipe; they are not silently reconstructed or relabelled.

## Capability recommendation at the time of this review

**Subsequently adopted:** [participant-v8-revised](v8-revised.md) implements the
equal-weight mean following user approval. This action-only recipe remains
frozen; the paragraphs below record the original recommendation.

Current v8 Capability remains the geometric mean of full-run health and
final-season health. The review recipe deliberately retains that formula so
the approved Execution change is concrete without treating a design discussion
as approval of a new Capability formula.

Recommended simpler candidate: mean health across every original agent and
every completed tick. Dead agents contribute zero; tick-zero starting health
is excluded. All 60 ticks have equal weight. Final-season health, endpoint
survival and extinction timing remain diagnostic evidence.

This measures sustained survival and health, not general intelligence.
It is more transparent and avoids a second implicit weighting of the final
season, but it cannot guarantee agreement with other model benchmarks.
It still rewards a good early period before later collapse, and health cannot
represent economic achievement beyond its eventual survival effects.
Production already measures productive activity; adding it back into Capability
would mix the constructs again.

A model ranking inconsistent with external expectations is a reason to audit
discrimination and construct validity, not proof of a calculation error.
Validation should use fixed behavioral examples and baseline policies:
valid-but-unproductive rest, resource-aware survival, capacity management,
seasonal preparation, and productive infrastructure that actually sustains
agents. Choose the formula before inspecting new model rankings.
No extra survival/inventory weights or model-specific adjustments were added.

## Verification

Tests cover weighted capacity, wells, successful collection after dropping
cargo in the same plan, actual source absence, preserved successes around
a failed action, duplicate failure events, unexecuted action tails, contention,
invalid messages, malformed output, missing telemetry, implicit rest, hidden
telemetry, aggregate per-action scores, recipe validation, and the unchanged
published v8 recipe digest.

Full validation: 645 tests passed with one skipped; review recipe validation
passed, and the published v8 recipe digest is unchanged.
