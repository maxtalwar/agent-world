# Revised v8 — equal-weight Capability

Approved after the first v8 ranking audit. The registered recipe for the next
leaderboard rebuild is participant-v8-revised. This does not edit the published
participant-v8 recipe or relabel its admitted results. The action-only review
recipe also remains unchanged.

## Scoring

Capability = sum of health after each completed tick across all original agents
/ (original agents * completed ticks).

Health is on a 0–100 scale. All 60 completed ticks have equal weight; starting
health at tick zero is excluded. Dead agents contribute zero through tick 60.
Final-season and endpoint health remain diagnostics, without extra score weight.
The score is independent of Execution and Production. Pool additive counts
across the two required seeds before rounding.

The implementation uses the existing outcome-production policy with
capability_aggregation=full_horizon_mean and execution_unit=action.
Published recipes retain the default full_tail_geometric aggregation.
Per-action Execution and Production are otherwise unchanged from the action
review. Medium effort, no message board, ten agents, and seeds 11/41 remain.

This is a narrow correction, not evidence that health comprehensively measures
model capability. Strong expected model hierarchies are useful validation
priors. A persistent inversion warrants investigation of task discrimination,
construct validity, sampling, and harness behavior; formulas should not be
tuned to force a preferred ranking.

## Separating scoring from the feedback treatment

No completed patched-feedback comparison was available when this revision was
made. The existing Luna and Terra v8 studies are analysis-ready, with clean
integrity and full usage coverage, but both are pinned to launch commit
75bd330bfc4027a993ba007aa16ac2effe00fccb. The capacity feedback fix first appears
in f63bd0c. Thus their recorded behavior is entirely pre-fix.

The stored health counts can be rescored diagnostically under the equal-weight
formula without calling a model. This measures a formula change only. Replaying
old actions through the patched engine cannot measure how a model would change
its future decisions after receiving different feedback.

For a low-cost first comparison, reuse unpatched v8 Luna seed 11 and compare a
new patched Luna world with identical model, medium effort, world, 60-tick
horizon, seed, prompt configuration, and harness settings. Score both health
trajectories with the same equal-weight formula. Verify source differences and
agent-visible prompt parity before launch. The new action telemetry is private;
scoring runs after behavior and should not be a treatment.

Inspect capacity failures, successful collection after a failure, subsequent
inventory disposal/storage, health trajectory, and deaths. A single paired
world is exploratory because provider responses vary even with the same world
seed. A stronger causal follow-up would run old and patched feedback
contemporaneously with only that feedback difference. Additional replication
or Terra can follow if warranted; no new model runs were launched
as part of this revision.

V6 versus patched v8 remains contextual evidence, not an isolated feedback
experiment: horizon, commerce declaration prompts, and source versions differ.
The unpatched v8 studies are the closer available baseline. New revised
leaderboard runs can also serve as the patched observations; do not buy a
duplicate run solely for this comparison.

## Validation

The full suite ran 650 tests successfully with one skipped. New regressions
check equal early/late credit, deaths and tick-zero exclusion, replication
invariance, recipe validation, and complete two-seed scoring/aggregation through
the benchmark pipeline. Published v8 and the action-only review retain their
original recipe digests. The new recipe validates through the CLI.
