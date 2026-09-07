# Expanded regeneration pilot — 2026-09-07

User-authorized question: does healing increase discrimination by rewarding models
that keep more agents alive and sustain their needs, rather than simply raising
all health scores? Test mechanics and policy usefulness separately.

New managed experiments: regen2-terra-20260907, regen2-luna-20260907,
regen2-mini-20260907. Each uses seeds 11 and 41, ten agents, sixty ticks,
medium reasoning through Codex, four workers per cell, and the unchanged
regeneration implementation at 9f296668f779fa281e269da98f73c1683e45b467.
Their same-model participant-v8-revised managed benchmarks are off controls.
Sol's completed regen2-sol-20260907 supplies the stronger-model treatment.
Gemini's existing regeneration run remains useful but is NOT a prerequisite
for analyzing these Codex results or recommending a benchmark recipe tonight.

Monitoring: use the existing Run Monitoring thread and event-driven watcher.
Repair recoverable infrastructure faults and resume existing checkpoints under
the user's authorization. Do not poll healthy or quota-waiting worlds with
agents. At each terminal event, assess the completed matched pairs now available;
do not mark all analysis blocked merely because Gemini has not finished.

Decision measures: original-population health over time, final/tail health,
final survivors and death timing; per-agent qualification streaks, actual health
restored, and failures to qualify by food/water/energy/damage. Compare on-minus-off
changes per seed, and Sol-minus-other-model gaps with and without regeneration.
Separate preserving agents from health among survivors; retain dead slots at zero.
Production is a secondary mechanism check. Higher aggregate health alone is not
success. Record stochastic seed disagreement and do not claim improved
cross-provider separation until Gemini completes.

Mechanical checks: no resurrection, caps, post-decay reserve thresholds including
energy, consecutive eligible ticks, damage/shortage reset, and checkpoint parity.
Use a deterministic ten-injured-survivors versus one-healthy-survivor scenario
with identical original population size to verify the intended scoring effect.

These are diagnostic experiments, not benchmark admission. Preserve the existing
recipe, all accepted decisions and source provenance. New benchmark design and
Astra benchmark launch are subsequent work after the regeneration decision.
