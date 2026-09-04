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

## Recovery, accounting, and transports

- Checkpoint schema 2 records exact ledger-prefix bytes and SHA-256 plus artifact generation. Loading checks prefix integrity and prefers a relocated sibling ledger. Rebase compares content, not line count. Legacy schema 1 remains readable.
- Pending journals validate source, adapter class, model/effort, boundary and decision-schema identity; size is bounded on read and write. CLI usage reconciliation uses the same journal validator.
- Usage gets run, record, and logical-decision identities. Coverage joins distinct tick/agent pairs. Partial ledgers contribute separately to attempted spend. Unexpected resolved-model sets block finalization.
- Shared subprocess transport bounds output, drains both pipes, applies one call deadline, and kills/reaps owned process groups. Codex app-server reads partial frames with a deadline and drains stderr. HTTP body reads and socket shutdown enforce deadlines across trickle responses. Devin ACP has one setup/turn deadline and bounded output/queues.
- Quota reservations, exponential backoff and absolute resume deadlines survive checkpoints. Stop hooks run between 30-second wait slices. Controller quota leases expire.
- Managed session names include a digest of full identity. Runtime numeric validation rejects booleans and nonfinite quota values.
- Report publication is atomic and offline regeneration preserves saved plan usage.

Validation: 507 tests pass (one existing skip), including real loopback drip HTTP, partial stdio frames, noisy stderr, output caps, descendant-held pipes, equal-length ledger corruption, relocation, and duplicate-plus-missing usage. No model calls were made. System DNS resolution is still delegated to the platform resolver; the socket deadline starts after connection setup.
