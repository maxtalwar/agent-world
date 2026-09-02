# Agent World benchmark run protocol

This is the canonical operating procedure for launching, resuming, monitoring,
and finalizing model-backed Agent World benchmark runs. Suite definitions and
scoring remain authoritative in [model-benchmarks.md](model-benchmarks.md).
Worktree mechanics remain documented in
[isolated-run-worktrees.md](isolated-run-worktrees.md), and logs and checkpoints
in [observability.md](observability.md).

The run workflow produces evidence. The analysis workflow interprets and
admits that evidence. A simulation reaching its last tick is not by itself an
analysis-ready benchmark result.

## Scope boundary

Use this protocol only when the user explicitly asks for a benchmark,
leaderboard result, certification, provisional benchmark, or named participant
protocol. A general request to run, test, try, smoke-test, or experiment follows
[agent-world-experiment-runs.md](agent-world-experiment-runs.md) and defaults to
seed 11 only. It must not silently acquire seed 41 or benchmark status.

Participant v6, v7, and future suite versions are protocol selections inside
this one benchmark workflow. Keeping one workflow prevents isolation, quota,
accounting, and evidence rules from drifting across per-version skills.

## Default interpretation

When a user says “run the benchmark on MODEL” without narrowing the request:

- use the current standardized participant protocol declared in
  `docs/model-benchmarks.md`;
- run the protocol's required certification seeds (currently 11 and 41);
- use a uniform population of the requested model and every locked trial
  setting, including the suite's reasoning policy;
- treat a requested single seed as provisional evidence; and
- treat any altered seed, population, connector, reasoning setting, or locked
  world setting as a controlled or diagnostic variant.

Do not ask the user to select a world or preset for a standardized benchmark.
The named `--benchmark-protocol` must lock the suite's preset and every
behavior-defining setting. The current Participant v7 suite uses
`frontier-generalists`; the full locked configuration is the Frozen trial table
in `docs/model-benchmarks.md`. A requested override changes the run into an
experiment or controlled diagnostic and cannot remain standard evidence.

Worker concurrency is not behavior-defining. The engine collects every
agent's decision from the same frozen tick state and resolves the tick only
after collection finishes, so `max_workers` and provider worker ceilings
control throughput only. Benchmark configs may tune them to provider capacity;
runs record the actual values as operational telemetry, and finalization never
requires them to match across models or replications. Provider, quota, timeout,
or harness failures remain integrity conditions regardless of worker count.

Do not copy a command from an older run until its protocol and flags have been
checked against the current CLI and suite documentation.

## Lifecycle

Every study and cell moves through explicit states:

```text
preflight -> launched -> startup_gate -> running -> completed -> finalized -> analysis_ready
                              |             |
                              v             v
                         diagnostic      waiting_quota -> resumed
```

`invalid`, `diagnostic_only`, and `needs_provenance_review` are terminal
evidence states, not errors to conceal. `waiting_quota` is nonterminal.

### 1. Preflight

Before any model call:

1. Read the current suite definition and inspect the current CLI help.
2. Resolve the exact brain, provider boundary, callable model ID, expected
   returned model identity, reasoning effort, connector, billing mode, and
   required seeds. Model aliases are not evidence of resolved identity.
3. Confirm the provider/model is callable with the intended credentials and
   boundary. Never print secrets.
4. Pin a clean launch commit. All required seeds in the study use that same
   commit.
5. Create the study manifest before launch. Record the requested tier, locked
   trial, target identity, launch commit, output paths, and one unique cohort ID
   per seed.
6. Confirm paths do not collide with an existing cell. Never overwrite a prior
   run, frozen classification, report, or checkpoint.

### 2. Managed launch

Launch the predeclared config with `agent-world run --config CONFIG.json`.
The manager gives every independently executing seed its own cohort, detached
worktree pinned to the shared clean launch commit, durable supervisor, and log.
These mechanics are recorded in `runs/jobs/RUN_ID/job.json`; they are not
manual operator steps.

Never place the actual model-backed run in an `exec_command`, PTY, or temporary
foreground shell. See [run-quickstart.md](run-quickstart.md).

### 3. Tick-5 health gate

The harness owns the startup gate. Its standardized default runs after tick 5
and fails an unhealthy cell when no model call was attempted, or when at least
two calls failed and the failure rate exceeds 20 percent. The exact recorded
gate configuration is authoritative if a protocol intentionally changes it.

The run agent checks the gate result once after tick 5. It does not babysit the
process after every tick, replicate the health calculation from incomplete log
tails, or interfere with a healthy process.

### 4. Event-driven monitoring

After a healthy startup gate, inspect a cell only when one of these occurs:

- the process exits;
- the harness records startup failure, checkpoint pause, or quota wait;
- the target tick completes; or
- the user asks for status.

Status reports should state the last completed tick, process state, stop
reason, quota deadline when applicable, and the next automatic transition.
Silence between events is normal.

### 5. Quotas and resumption

A rate or usage limit means the run is early, not broken. The harness must stop
calling the refusing provider, freeze the world at a completed tick, and wait
up to `BENCHMARK_QUOTA_WAIT_HOURS` (or the explicit `--quota-wait-hours` value).

Resume only with `agent-world resume RUN_ID`, which uses the existing
checkpoint, cohort, and pinned launch commit. Never restart the study to bypass a limit. Never accept a
provider failure as a fabricated agent action. If the wait allowance expires,
preserve the checkpoint and mark the cell `waiting_quota` or `diagnostic_only`
with the exact reason.

### 6. Cell completion gate

Use `agent-world finalize RUN_ID` for managed studies. It performs the
protocol-aware report, transfer-accounting, and readiness audit described
below. `--dry-run` reports blockers without model calls or artifact writes.

Before calling a cell complete, verify all of the following against artifacts:

- the official target tick and terminal event were reached;
- the expected number of decisions exists;
- usage-record coverage is 100 percent;
- benchmark integrity is `clean` and failure counters agree with the ledger;
- requested, callable, and returned model identities are reconciled;
- brain, provider, connector, reasoning effort, launch commit, protocol, suite,
  scoring revision, and report fingerprint are recorded; and
- output, snapshot, report, usage ledger, manifest, and any required
  classification artifact are present and internally consistent.

Do not wait for the other required seed before finalizing a completed cell.
This makes provisional evidence durable and prevents a later quota pause from
leaving the finished seed half-processed.

### 7. Cost finalization

Cost has two separate meanings and must never be conflated:

- `api_list_cost_usd` is derived from recorded input, cached-input, output, and
  reasoning usage using a public, dated provider rate card; record the source
  URL or repository rate-card revision and the calculation inputs.
- provider- or CLI-reported subscription cost is preserved as
  `provider_reported_subscription_cost_usd` (or an equivalently explicit
  label). It is useful operational telemetry, not the comparable benchmark
  cost.

If no defensible public rate card maps to the recorded model and token classes,
mark API-list cost unavailable with a reason. Do not silently substitute the
subscription figure.

### 8. Transfer finalization

Transfer accounting follows the protocol that generated the ledger.

For Participant v7, agents declare every transfer as `gift`, `payment`, or
`barter`. Verify that the report deterministically reflects those declarations.
Record mode `self_declared_v7`. Do not invoke an LLM classifier and do not
reinterpret a model's declaration after the fact.

For Participant v6, agents lacked that declaration channel. After the cell
completes:

1. If the ledger contains no gifts, record mode `none_no_gifts`.
2. Otherwise run the frozen `gpt-5.6-sol` procedure in
   `scripts/gift-classifier-prompt.md` exactly once against every gift and
   validate the result with
   `scripts/gift-classifications-output.schema.json`.
3. Verify complete gift coverage, unique identifiers, prompt and artifact
   hashes, the exact judge identity, and every evidence quote against the
   ledger.
4. Regenerate the report deterministically from the frozen artifact using the
   cell's pinned launch commit.

Never overwrite a valid frozen classification. A re-judgment is a new scoring
revision, not routine cleanup. Missing or invalid classification leaves a v6
cell incomplete for standardized entrepreneurship analysis.

The managed finalizer records a one-shot attempt before invoking the frozen
judge. If that attempt is interrupted or produces invalid evidence, it
preserves the attempt and raw output and refuses to call the judge again.
Resolve that evidence explicitly; do not silently retry.

### 9. Analysis-readiness handoff

Add an `analysis_readiness` object to the study manifest after finalization.
Use this shape; paths are repository-relative and arrays may contain one or
more cells:

```json
{
  "analysis_readiness": {
    "schema_version": 1,
    "status": "ready",
    "checked_at_utc": "2026-08-24T00:00:00Z",
    "launch_commit": "<40-character commit>",
    "protocol": "participant-v7",
    "completed_seeds": [11, 41],
    "waiting_seeds": [],
    "integrity": "clean",
    "usage_coverage_pct": 100.0,
    "model_provenance": "verified",
    "cost_accounting": "api_list_derived",
    "transfer_accounting": {
      "mode": "self_declared_v7",
      "complete": true,
      "artifacts": []
    },
    "reports": ["runs/.../seed-11/run-report.json"],
    "blockers": []
  }
}
```

Allowed statuses are:

- `ready`: every required seed passed finalization and can enter analysis for
  certification.
- `provisional_ready`: the requested or available standard seed passed
  finalization, but required replication is incomplete.
- `waiting_quota`: a resumable cell is frozen on a provider limit.
- `diagnostic_only`: evidence is interpretable but cannot enter the standard
  pool because the protocol, settings, completion, or integrity differs.
- `invalid`: the evidence cannot support a model-performance conclusion.
- `needs_provenance_review`: completion evidence exists, but identity,
  fingerprint, accounting, or another admission fact remains unresolved.

Every non-ready status must name its blockers. For a multi-seed study,
`provisional_ready` may coexist with a separate waiting cell only when the
completed seed independently passes every finalization check; record both
`completed_seeds` and `waiting_seeds`.

Already cataloged historical studies may predate this field. Their catalog and
database admission records remain the durable substitute. New, unadmitted
studies must not rely on that exception.

## Handoff and admission boundary

The run agent hands off artifacts, not a leaderboard narrative. Its final
status includes:

- study ID and manifest path;
- cell/cohort IDs and launch commit;
- completed and waiting seeds with last completed ticks;
- reports, ledgers, snapshots, checkpoints, and classification artifacts;
- integrity, usage, model-provenance, transfer-accounting, and cost status; and
- the `analysis_readiness.status` plus exact blockers.

The run workflow does not add a new result to `data/run-sources.json` or claim
a leaderboard position. Once evidence is `ready` or `provisional_ready`, the
analysis workflow validates it, interprets performance, and performs durable
catalog/database/leaderboard admission as one scoped change.

## Repository hygiene

Preserve run worktrees and checkpoints through analysis. Commit only durable,
non-secret artifacts that follow the repository's evidence conventions. When
the run exposes a genuine model quirk, capability inversion, or harness effect,
append a dated evidence-backed entry to `docs/insights.md`. Validate changed
code and metadata, then commit and push the scoped repository change.
