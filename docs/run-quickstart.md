# Managed run quickstart

Use the managed interface for every normal long-running model-backed run. It
validates one declarative JSON config, pins the clean source commit, creates one
isolated cohort per seed, starts each cell under a detached `tmux` supervisor,
and records enough state to inspect or resume it later. You do not enter a
worktree or keep the launch terminal open.

## Fire off a run

Start from an example, give it a unique `run_id`, and set the exact model
boundary:

```bash
cp configs/run-configs/experiment.example.json /tmp/my-run.json
$EDITOR /tmp/my-run.json
agent-world run --config /tmp/my-run.json --dry-run
agent-world run --config /tmp/my-run.json
```

The real launch returns only after every immediately eligible cell and any
startup-gate supervisor are alive. It is then safe to close the terminal. The manager writes
`runs/jobs/RUN_ID/job.json`, one log per cell, and simulation artifacts beneath
`runs/managed/RUN_ID/` unless `output_dir` overrides that location.

For a replicated benchmark, seed 11 starts first. A separate detached gate
supervisor reads the harness's recorded startup-health event and releases the
remaining seed cells only after seed 11 passes. If it fails, later seeds remain
`blocked_startup_gate`; no operator has to watch tick 5.

Check meaningful state without following every tick:

```bash
agent-world status RUN_ID
```

If a supervisor was interrupted or a quota wait expired after a completed
tick, resume the existing cells rather than restarting them:

```bash
agent-world resume RUN_ID
```

Resume reuses the original checkpoint, cohort, and pinned launch commit.
Already completed or currently active cells are skipped.

Finalize completed benchmark evidence before calling it done:

```bash
agent-world finalize RUN_ID --dry-run
agent-world finalize RUN_ID
```

Non-dry finalization runs under its own detached supervisor, so the launch
command returns immediately and `agent-world status RUN_ID` reports its state.
Finalization regenerates and audits each completed report, verifies completion,
integrity, usage coverage, model provenance, cost status, and protocol-specific
transfer accounting, then writes `analysis_readiness` into the managed job
manifest. A completed simulation can still finalize as `diagnostic_only`,
`needs_provenance_review`, or another blocked state.

Participant v7 transfer accounting is deterministic from each agent's declared
`gift`, `payment`, or `barter` kind. Participant v6 is different: if a completed
ledger contains gifts and no frozen classification exists, `finalize` invokes
the one-shot `gpt-5.6-sol` judge using the repository's frozen prompt and output
schema, validates every identity and evidence quote, freezes
`gift-classifications.json`, and regenerates the report. It records an attempt
before the model call and refuses to re-judge after an interrupted or invalid
attempt; `--no-classify-v6-gifts` performs only the audit and reports the
missing artifact as a blocker. Existing frozen artifacts are validated and
never overwritten. A v6 ledger with no gifts records `none_no_gifts` without a
judge call.

## Config reference

Every config has these top-level fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | Must be `1`. Unknown fields are rejected rather than silently ignored. |
| `run_id` | Unique filesystem-safe identifier. It names the job, supervisors, cohorts, and default output directory. |
| `kind` | `benchmark` or `experiment`. This is an evidence boundary, not just a label. |
| `question` | Required for experiments; the concrete claim or harness behavior being tested. |
| `protocol` | Benchmark only. Omit to use the current supported participant protocol. A named protocol locks benchmark-defining settings. Historical protocols require `source.commit` pointing to a revision that implements them. |
| `model` | Provider boundary, callable model ID, reasoning effort, or an experimental mixed population. |
| `seeds` | Cells to launch. Defaults to `[11, 41]` for a benchmark and `[11]` for an experiment. |
| `world` | Preset and optional world treatments. Omit locked benchmark settings; the protocol owns them. |
| `runtime` | Horizon, population size, concurrency, quota allowance, and progress logging. |
| `harness` | Connector, conversation, validation, assignment, and startup-gate settings. |
| `output_dir` | Optional artifact root. Defaults to `runs/managed/RUN_ID`. |
| `source.commit` | Optional explicit clean Git revision. Otherwise the manager pins `HEAD` and refuses dirty tracked source. |

### `model`

For a uniform cohort, set `brain`, `id`, and optionally `reasoning_effort`:

```json
"model": {
  "brain": "zcode",
  "id": "glm-5.3",
  "reasoning_effort": "max"
}
```

`brain` selects the actual connector (`openrouter`, `codex`, `claude`,
`cursor`, `devin`, `grok`, or `zcode`); `id` is the callable model identifier
for that connector. The boundary is part of provenance: the same model name
through OpenRouter and a first-party CLI is a different run configuration.

Experiments may instead use `population`, an array of existing
`COUNT@BRAIN:MODEL` specifications. Mixed populations are rejected for a
standard benchmark.

### `world`

`preset` is one of:

- `frontier-generalists` (default): frontier world, organic economy, dispersed
  geography, neutral objective, generalists;
- `baseline`: classic world, baseline economy, shared oasis, generalists;
- `organic-generalists`: classic organic/dispersed world with generalists; or
- `experimental-organic-specialists`: classic organic/dispersed world with
  specialists.

Advanced experiment fields are `width`, `height`, `objective_mode`,
`economy_mode`, `geography_mode`, `specialization_mode`,
`action_feedback_mode`, `communication_action_cost`,
`town_ledger_action_cost`, `town_ledger_prompt_mode`,
`town_ledger_seed_mode`, `town_ledger_output_mode`, and
`codex_action_max_items`. A benchmark config should normally omit `world`
entirely because its protocol rejects incompatible overrides.

### `runtime`

- `ticks` is the total target tick, including after resume.
- `agents` is population size.
- `max_workers` is the global same-tick decision pool. It is not the number of
  run cells.
- `provider_max_workers` optionally sets connector ceilings by `openrouter`,
  `codex`, `claude`, `cursor`, `devin`, `grok`, or `zcode`. Every ceiling is
  still clamped by `max_workers`.
- `quota_wait_hours` controls how long the harness freezes and retries the same
  tick after a provider limit. A benchmark supplies its protocol default.
- `sequential_decisions: true` disables concurrent decisions and therefore
  changes the treatment; standardized benchmarks reject it.
- `progress` controls per-tick log lines. Managed launches enable it by default
  so the detached log remains useful.

### `harness`

- `connector_profile` selects the provider invocation envelope.
- `conversation_mode` selects fresh or persistent per-agent conversations.
- `session_max_turns` bounds retained successful decisions for persistent
  sessions.
- `decision_mode` is `raw` or `validated`.
- `assignment_strategy` and `assignment_seed` control mixed-population
  placement.
- `startup_health_check_tick` and
  `startup_health_max_failure_rate` configure the automatic health gate.
- `no_agent_io_log: true` removes private prompt/observation evidence and is
  unsuitable for standardized benchmark provenance.

Protocol-locked benchmark settings should be omitted, not copied into every
config. The low-level CLI validates the resolved command again before any model
call.

## Benchmark versus experiment

A `benchmark` config predeclares standardized intent and invokes the named
participant protocol for every seed. Matching the same world and horizon in an
`experiment` does not make it benchmark evidence. Conversely, launching a
benchmark config creates a benchmark candidate, not automatic leaderboard
admission: completion, usage coverage, integrity, returned model identity,
accounting, and finalization still have to pass the benchmark protocol.

## What the manager hides

Each seed is an independently executing cell. Internally the manager calls
`scripts/run-isolated-cohort` so a cell cannot change source underneath another
cell, then runs that command in detached `tmux`. The isolation script alone is
not a supervisor; invoking it directly from a temporary command session can
still kill a healthy run when that session ends. Direct invocation is reserved
for managed internals and deliberate recovery.
