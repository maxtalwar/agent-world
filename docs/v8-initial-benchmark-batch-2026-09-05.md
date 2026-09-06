# Initial Participant v8 benchmark batch — 2026-09-05

User-authorized models: GPT-5.6 Luna, GPT-5.6 Terra, and Muse Spark 1.2.
Every world uses the registered participant-v8 recipe: 10 agents, 60 ticks,
medium effort, seeds 11 and 41, fresh conversation, no message board, and
self-declared transfer intent.

Simulation launch commit: 75bd330bfc4027a993ba007aa16ac2effe00fccb.
The configs explicitly pin that commit. The job controller may be launched
from the later documentation/config commit; all six simulation cohorts use
the same frozen source and recipe.

| Model | Connector | Run ID | Workers per world |
|---|---|---|---:|
| gpt-5.6-luna | codex / codex_cli | gpt-5-6-luna-v8-20260905 | 4 |
| gpt-5.6-terra | codex / codex_cli | gpt-5-6-terra-v8-20260905 | 4 |
| muse-spark-1.2 | muse / muse_cli | muse-spark-1-2-v8-20260905 | 2 |

For each run ID R, the two cohort IDs are R-seed-11 and R-seed-41.
Configuration files are in configs/run-configs/v8-initial-20260905/.
Managed job manifests are runs/jobs/R/job.json; evidence is
runs/managed/R/seed-11/ and runs/managed/R/seed-41/.

## Preflight

- Codex CLI 0.147.0 is signed in with ChatGPT. Its authenticated model catalog
  advertises the exact Luna and Terra IDs with medium effort.
- Muse Code 1.0.3 (1.0.3-R2198.1) passes native preflight with saved account
  credentials. The same connector/account recently completed Spark 1.2 v7.
  Local preflight cannot prove live entitlement or remaining quota; the first
  benchmark seed's gate checks actual behavior without a duplicate paid probe.
- Native subscription/account routes are used. Token-derived API-list cost is
  reported separately from subscription charges.
- Config validation confirms all six worlds target 60 ticks at the same source.
- Each job starts seed 11 first; its controller releases seed 41 only after a
  clean tick-5 startup gate. The three jobs can run concurrently.
- Quota refusals freeze checkpoints under the normal bounded wait policy.
  No Grok or Muse Spark 1.1 checks are resumed by this batch.

## Completion contract

Controllers own checkpoint recovery and per-seed finalization. Their durable
manifests retain progress, quality flags, measured usage, model provenance,
cost accounting, deterministic transfer accounting, and analysis_readiness.
Requested-only identity remains acceptable when native CLIs do not independently
echo the serving model. Conflicting returned identities require review.

No result is admitted to the source catalog or leaderboard until completed
evidence passes the reporting workflow. This manifest is a launch plan, not
a performance claim.

## Completion handoff — 2026-09-06 02:47 UTC

Terra is analysis-ready on both required seeds, each with a terminal
run_completed event at tick 60. Seeds 11 and 41 contain 476 and 486 decisions,
respectively, with 100% usage coverage, clean integrity, no provider failures,
and complete self-declared transfer accounting. Requested gpt-5.6-terra identity
is recorded as requested_only, consistent with the accepted native CLI policy.
Both reports are protocol-compliant and share source fingerprint
77b2c0ac0928173d1a91c77094825a9d5b30ce059efefd7bb95740b2fc7018fa.
The manifest and evidence paths above contain the analysis-ready handoff.

The completion audit exposed a finalizer metadata bug: it inspected the
subscription charge rather than the report's token-derived API estimate.
The corrected audit records API-list estimates of $7.264506 and $7.617036,
using the report's dated 2026-09-05 rate card, separately from $0 reported
subscription charges. Simulation source, raw evidence, and scores are unchanged.
Finalization and v8 integration tests pass (20 tests).

Luna and Muse remain under their original controllers. Their pinned
orchestrators predate this metadata correction: after automatic completion,
check the accounting label against attempted_token_cost and recover the
finalization audit using the corrected source checkout if necessary.
Do not restart their simulations or modify their pinned cohorts.
