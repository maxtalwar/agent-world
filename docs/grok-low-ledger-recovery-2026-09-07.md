# Low-effort Grok ledger recovery — 2026-09-07

Scope: `grok-4-6-low-ledger-on-20260905` and
`grok-4-6-low-ledger-off-20260905`, both authorized seeds. Both medium-effort
Grok conditions remain deferred and were not resumed.

On: seed 11 frozen at 48/50 with two accepted cached decisions (agents 2/4);
seed 41 already completed 50/50. Off: seed 11 frozen at 39/50 after a cancelled
provider request; seed 41 frozen at 44/50 with seven cached decisions
(agents 1/10/2/3/4/5/6). No current authentication blocker was found.

A native, read-only ACP `_x.ai/billing` request returned 100% credit usage,
weekly period ending 2026-09-08T10:16:39.873051Z, zero on-demand cap and zero
prepaid balance. The verified continuation deadline is one minute later:
**2026-09-08 03:17:39.873 Pacific / 10:17:39.873 UTC**. No model probes or
recurring agent checks are needed while waiting. Provider availability after
that reset remains subject to its actual response.

The original twelve-hour cumulative wait allowance had already expired. The
user-authorized recovery extends the operational allowance to 36 hours per job,
covering historical wait, the verified future wait, and twelve hours afterward.
Historical reserved wait is retained. The known deadline is stored in each
unfinished checkpoint and cell's `next_auto_resume_at_utc`, and as an
append-only `run_quota_wait` event. Managed supervisors perform the sleep.

Initial resume verification detected a changed default Grok executable before
any inference. The exact original binary remains installed, hash
`9ba87444e1819e8f6104adbbf4676a870c204380aa5c3e1c38a926c4ea677238`.
A job-scoped PATH restores it for these cells and controllers; original-binary
`models` verifies authenticated access to grok-4.6. No source migration is
needed; all cells retain 0b3173cdb60ae036ec702843d8577f20a7b68081.

All original artifact files were archived per unfinished cell beneath each
job's `quota-recovery-20260907` directory before modification. Recovery records
contain hashes, old/new operational wait state, provider deadline and cached
agent IDs. Verify pending-journal and usage hashes after managed resume;
completed world history remains an unchanged event prefix. Do not resample
cached decisions. Terminal/attention follow-up belongs to the existing event
watcher. These remain diagnostic ledger experiments, not leaderboard admission.
