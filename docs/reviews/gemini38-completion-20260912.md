# Gemini 3.8 Flash Medium completion and admission review — 2026-09-12

Both seeds reached tick 60 with clean ledger integrity, complete self-declared transfer accounting, and 100% usage coverage. Requested model identity is recorded; returned identity and API-list pricing are unavailable.

| Seed | Evidence class | Capability | Execution | Production |
|---|---|---:|---:|---:|
| 11 | Changed-harness diagnostic | 85.15 | 97.10 | 145.83 |
| 41 | Clean benchmark replication | 89.22 | 96.69 | 157.83 |

The canonical-root recovery uses the original launch-source finalizer. Both execution worktrees are clean and their exact source diffs from the launch commit are empty. The temporary current-source fingerprint mismatch disappears when reporting with the pinned source; no acceptance waiver is necessary for source code.

Seed 11 retains the approved CLI 1.1.27-to-1.2.1 migration and the separately recorded unexpected self-update at tick 28. The pre-approval event prefix still matches all 1,980,035 bytes and its recorded SHA-256. Accepted events and checkpoints were not edited during this review. The prior recovery record documents the checkpoint metadata migrations; this review does not expand that approval.

The owner subsequently requested leaderboard admission of the completed pair.
Both seeds are now included, with seed 11's approved CLI-version change retained
as a controlled-variant classification and disclosed in the result details.
This does not claim the harness was unchanged throughout the run. No source
fingerprint waiver is needed: pinned-source reports have no quality flags.

The permanent fix separates the canonical evidence/catalog root from the source
used for reporting and aggregation. Both operations now use the original pinned
simulation source rather than the recovery tooling checkout. Failed derived
reports were archived before regeneration. Event, snapshot, checkpoint, usage,
and manifest hashes remained unchanged. No model calls or rerun were needed.

Exact artifact hashes, source checks, scores, and reliability evidence: [review JSON](gemini38-completion-20260912.json). Prior authorization scope: [recovery record](gemini38-environment-recovery-20260912.json).

Validation after admission: all 49 focused finalization, controller, acceptance,
recipe-execution and leaderboard tests passed. Database integrity and foreign-key
checks pass (45 model results, 101 runs, 44,958 usage records); the compact
leaderboard projection includes Gemini. Both final reports remain hash-identical
to the pinned-source review, and all retained event, usage, manifest, and
checkpoint hashes match. Managed readiness is ready and controller state is
completed, with superseded finalization errors cleared.
