# Infrastructure upgrade implementation

Tracking the findings in [the September 4 audit](infrastructure-audit-2026-09-04.md). This is an implementation ledger, not a claim that all findings are complete.

## Completed foundation

- Trusted connector outcomes are separate from model intent. Authentication, quota, provider and harness failures cannot advance a tick. Genuine model-output failures remain scoreable. New events carry outcome metadata; historical ledgers retain their legacy classification.
- Sequential and concurrent brain exceptions both fail before world resolution.
- World ticks restore state, events and RNG on resolution exceptions without copying the full event history. Invalid agreement party lists are rejected as actions.
- ZCode accepts canonical boundary names and historical aliases consistently.
- Codex captures its schema at construction and writes immutable, atomically published schema files addressed by content.
- Usage persistence errors raise explicitly; memory acknowledges records only after successful durable writes. Rollback preserves partial usage before replacing the active ledger.
- Provider throttle waits occur outside the shared runtime lock.
- Atomic JSON/text artifacts fsync the containing directory on POSIX.

Validation: 501 unit tests passed (one existing skip). Eight added regression cases exercise real error paths and the invariants above. The existing interface compatibility fixture still matches after removing the additive outcome telemetry field.

## Remaining audit work

Durable checkpoint integrity and pending-journal identity; logical usage coverage and provenance; transport deadlines and process cleanup; managed lifecycle and quota recovery; shared configuration capabilities; observation and observer performance; packaging, retention, and broader integration coverage remain in progress. Each will receive its own validation record below.
