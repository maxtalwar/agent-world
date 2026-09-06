# Antigravity schema boundary recovery — 2026-09-06

The user authorized connector engineering and managed recovery of existing jobs
`web-gemini-3-6-flash-medium-8c4e0fb57817` and
`web-gemini-3-7-flash-medium-1ae63d77303d`. No new study was launched.

## Diagnosis and correction

Four cells paused after one automatic retry, at completed ticks 11/10 and
27/28 respectively. The adapter treated generic stream `tool` updates as
external activity. The four latest failed native SQLite sessions contained only
native type-132 `finish` calls and no subtrajectories:

- 3.6 seed 11: d463793f-3d2b-461b-b3cd-499646f0d4ce (steps 2, 6)
- 3.6 seed 41: a82bc5af-0e26-42f0-92ef-29656fbf9e9d (step 4)
- 3.7 seed 11: 53a10fbe-94dc-43b3-b32b-474decd98621 (step 4)
- 3.7 seed 41: 0cfc4f58-fe7c-4820-880b-a84e8b12eec0 (steps 4, 6)

The old adapter did not retain raw stdout. Native step payloads are the retained
failure evidence; a single bounded CLI 1.1.27 structured-output probe corroborated
the schema finish mechanism. Earlier failed sessions had no retained databases
and remain unverified. No discarded decision was retroactively admitted.

Fix commit: `f10ee284c84075bca77919136652036551bab614`, branch
`fix/antigravity-schema-boundary`. The parser exempts a generic tool update only
when its exact session and step index resolve to a native finish record. Missing,
foreign, malformed, external-tool and subtrajectory records still fail closed.
Accepted audited records retain a native payload digest. The prompt and CLI
invocation are unchanged.

## Recorded migration and recovery

Original source `c94b8afd1c3d1080b99e508c53e060295e513946`, recipe
`participant-v8-revised`, seeds 11/41, models and medium effort are preserved.
Each job now records the execution commit separately from launch source, retains
historical worktrees and archives its original job manifest and checkpoints.
Per-cell `source-recovery/seed-N.json` includes original and recovery commits,
recipe fingerprint, checkpoint/archive SHA-256 and hashes of pre-recovery
artifacts. Existing event ledgers, accepted completed decisions and partial
usage evidence were retained. The managed interface resumes the same cohorts.

Commands, from the isolated fix checkout (RUN_ID is each job above):

```sh
python3 scripts/recover-antigravity-schema.py RUN_ID --root /home/maxtalwar/agent-world/.local/leaderboard-sources/c94b8afd1c3d1080b99e508c53e060295e513946 --commit f10ee284c84075bca77919136652036551bab614
python3 -m agent_world resume RUN_ID
```

The local source clone first fetched the fix branch from its existing local
origin. Its checkout and the shared leaderboard-dashboard checkout were not
switched or edited. Durable supervisors and new pinned worktrees were created
by the managed runner. No quota was bypassed; Muse's wait was untouched.

## Validation and result

64 tests passed across native headless connectors, managed runs, finalization,
and source recovery. Migration tests reject wrong source, recipe, provider,
checkpoint, certification flag and corrupted archive hash. Parser tests reject
external tools, delegation, missing and malformed native evidence. Direct audit
of the real two-step failed finish session returned zero external tool calls.
`git diff --check` passed.

Post-resume evidence verified completed ticks 12/11 for Gemini 3.6 and 28/29
for Gemini 3.7, beyond all four paused checkpoints. All original checkpoint
archives still matched their hashes. Consolidated monitoring retains ownership.

These are explicitly migrated runs. Finalization must require source-migration
provenance review; this repair does not certify or admit mixed-source evidence.
