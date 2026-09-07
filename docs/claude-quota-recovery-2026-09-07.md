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
