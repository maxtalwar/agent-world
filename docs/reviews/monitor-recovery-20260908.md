# Monitoring recovery — 2026-09-08

Gemini 3.8 seed 11 originally stopped at tick 5 on a transient Antigravity
`authentication_required` response. An event worker checked the account and
attempted to resume, but did not verify advancement. The old progress timestamp
made the controller count the paused hours as an execution stall and reap the
new process immediately. The same attention signature had already been seen,
so subsequent recovery was never dispatched. An assigned supervisor ID was
also incorrectly rendered as an actively working agent.

Recovery preserved the pinned source and eight cached decisions, reset the
attempt's progress clock, supplied the normal CLI PATH, and resumed through
the managed interface. The monitoring task verified advancement from tick 5
to tick 6 and unchanged completed seed 41 artifacts. Detailed hashes and the
archive are in the job's `recovery-20260908-path/recovery.json`.

## Continuing behavior

- Each resume attempt has a distinct attention signature. An unchanged failure
  still dispatches only once. Healthy progress and known quota waits do not
  invoke an agent. Existing completion signatures survive this upgrade.
- External-dependency acknowledgements cover the recorded incident, not all
  future states of the study. Progress or another resume invalidates the old
  acknowledgement; heartbeat timestamps alone do not.
- The UI claims active repair/review only while an event worker has a recent
  heartbeat. Assignment alone is not evidence of work. Detailed resolution
  text stays under Technical details.
- Completion workers perform routine provenance review and admission. An
  infrastructure-only review is linked to exact report and recovery hashes,
  without impersonating an owner exception. Changed conditions or resampled
  decisions require a separate disclosed classification decision.
- Every managed launch resets the stall timer before starting the detached
  process. Recovery must verify advancement or a real quota wait before success.

Validation: 89 Python regressions plus activity UI assertions; both Sonnet
prefixes verified and its finalization dry run is ready with no blockers.
