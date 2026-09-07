# Gemini v8.1 provenance review — 2026-09-07

Outcome: review performed; unchanged benchmark certification is **not approved**.
The source migration is explained, but evidence required to independently verify
all schema-finish exemptions is incomplete. Do not repeatedly run this review
unless the missing native evidence is restored or a new evidence policy is
explicitly chosen. This is an evidence decision, not an active simulation fault.

## Verified

Both Gemini 3.6 Flash Medium and 3.7 Flash Medium finished seeds 11 and 41 at
60 ticks. Reports record clean integrity and 100% usage coverage. All four
archived checkpoint hashes and previous recovery-record hashes match their
recorded values. The recipe digest, requested model IDs and medium effort are
preserved. Source began at c94b8afd and resumed with recovery commits f10ee284
and a886e7e0; original source and recovery records remain retained.

The reviewed c94b8afd..a886e7e0 diff changes the Antigravity result parser to
verify native `finish` operations from SQLite/protobuf records, adds quota
recognition, and adds explicit recovery plumbing. It does not change model
invocation arguments, prompts, world mechanics, seeds or reasoning defaults.
The exemption requires native records rather than trusting model-authored text.
This supports an operational correction, but is not proof of every actual call.

## Unresolved evidence

Three trace-bearing Gemini 3.7 seed-11 receipts and five Gemini 3.6 seed-41
receipts refer to native conversation databases that are absent at the recorded
connector trace root. A stored hash cannot replace the original bytes for an
independent audit of which tool operation was exempted. Other raw step digest
reconstructions did not all match when hashing every type-132 step; the parser
hashes only reported step indices, so these differences are not proof of
corruption and require the exact stream-index evidence for resolution.

Requested-only model attribution and unavailable matching API rate cards are
also retained exactly as recorded; this review does not manufacture returned
model identity or prices. No reports, ledgers, recipe fingerprints, scores or
certification guards were rewritten. No result was admitted to the leaderboard.

The adjacent JSON contains per-cell report hashes, checkpoint verification,
trace receipt counts, and missing native session IDs. Restore those databases
and associated stream indices to reopen the review. Fresh runs under one clean
connector revision are another option, but were not launched by this review.
