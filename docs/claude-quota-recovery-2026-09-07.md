# Claude quota-window recovery — 2026-09-07

Affected jobs: `web-claude-haiku-4-5-20251001-cdc35c0408ed` (seeds 11/41,
ticks 23/21), `web-claude-sonnet-5-f8f540cb1847` (seeds 11/41, ticks 45/40).
Original launch source: f10ee284c84075bca77919136652036551bab614.

Each exhausted a lifetime 43,200-second quota allowance despite successful
intervening ticks. The latest provider message explicitly says the session
limit resets at 1:50pm (America/Los_Angeles); parser output is
2026-09-07T20:50:00Z. The authorized recovery deadline is 20:51Z (13:51 PDT),
including the normal minute of slack. No provider inference is needed while
waiting. No fresh study or baseline is launched.

The repair changes only quota bookkeeping: a completed tick renews the
per-episode allowance and resets backoff. Checkpoint state retains total
reserved wait time independently. An exhausted allowance before a known reset
no longer triggers a premature probe. Same-tick resumes retain their budget.

Recovery archives original checkpoint/snapshot/commit metadata and records
hashes for the ledger, usage and pending decisions. The current episode's
reserved time is derived from waits at its frozen tick. Its remaining wait is
reserved to 20:51Z, while lifetime telemetry retains the historical 43,200
seconds. No accepted pending decisions, world state, model, recipe, cohort,
effort, source fingerprint, or original launch identity is replaced.
Per-cell source-recovery records explicitly identify the new execution commit;
final certification requires source-migration review rather than silently
claiming unchanged source. Event monitoring remains local and deterministic.

Validation: session, reset-parser and controller unittest suites cover repeated
quota windows separated by progress, no early probe, frozen-world waiting,
bounded exhaustion, disabled waiting, and accepted-decision checkpoint reuse.

## Recovery incident and final scheduling state

The first recovery attempt preserved the pending-journal hashes but did not
archive journal contents. This was insufficient: journal execution identities
include a digest of every Python source file. The accounting-only source change
therefore invalidated Haiku's eight accepted pending decisions per seed during
CLI usage recovery, before model calls. Their usage was moved, intact, to
`run-usage-partial-tick-23.jsonl` and `run-usage-partial-tick-21.jsonl`.
Post-resume verification detected the mismatch. Haiku cell supervisors and
controller were stopped before the reset; its automatic schedule was removed.

The original checkpoint archives contain world/brain state but not the decision
journal. Exact native transcripts/debug records were unavailable: Claude was
invoked with `--no-session-persistence`. No exact reconstruction is claimed.
Haiku requires an explicit evidence choice before continuation; it must not
silently resample these accepted decisions or claim unchanged certification.
This loss was caused by the recovery operation, not by Claude model behavior.

Sonnet had no accepted pending entries and remains in durable quota sleep until
20:51 UTC, with original usage hashes and event prefixes verified. The source
recovery validator now refuses a nonempty pending journal before mutation.
Future migrations must archive the journal and explicitly validate any identity
migration against unchanged observations, model, world, and accepted decisions.
