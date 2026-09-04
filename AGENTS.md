# Repository workflow

## Laboratory-first architecture

Agent World is a laboratory for exploring the societies and capabilities of
LLM agents across different worlds, populations, harnesses, and configurations.
The laboratory supports experiments. Benchmarks define particular experiments
and decide which results qualify for a leaderboard. Benchmark eligibility
must never determine which experiments the laboratory permits.

Keep benchmark protocols as explicit, versioned recipes and certification
policies, separate from simulation mechanics and connector capabilities.
Support multiple recipes in one checkout; do not replace a global protocol
constant to run an older study. Preserve recipe identity and source provenance
on resume, and never relabel historical evidence or pool different recipes.
General experiments may override recipe defaults without claiming benchmark
certification. Enforce only actual world/connector constraints on those runs.

Define new benchmark designs in `agent_world/recipes/ID.json`; registration
and packaging are automatic. Validate with `agent-world recipes --validate
PATH` and inspect with `agent-world recipes ID`. Use a new ID for changes
to a published recipe. Reuse implemented scoring/transfer policies instead
of branching launch, report, or finalization code on benchmark version names.
See `docs/experiment-recipes.md` for the data model and authoring workflow.

## Agent workflow routing

The repository-tracked skills in `.agents/skills` are the canonical operating
manuals:

- Use `$setup-agent-world` for first-time setup, machine migration, harness
  readiness, or worker-capacity configuration.
- Use `$run-agent-world-benchmark` only for explicit benchmarks, leaderboard
  results, certification, provisional benchmarks, or named participant
  protocols.
- Use `$run-agent-world-experiment` for ordinary simulations, smoke tests,
  harness tests, and exploratory runs.
- Use `$report-agent-world-runs` only to score, interpret, and report on
  completed benchmark or ordinary-run evidence.
- Do not load a run-reporting skill for setup, launch, monitoring, generic
  engineering, or questions that merely sound analytical.

Agents that do not automatically discover repository skills should read the
matching `SKILL.md` directly and follow it as the task manual. The executable
CLI remains the source of truth for behavior.

- Before selecting a model for a benchmark or making a cross-model performance
  claim, query `data/model-benchmarks.sqlite`, generated from
  `data/run-sources.json`; its schema and example queries
  are documented in `docs/model-metrics-database.md`. Use
  `docs/model-leaderboard.md` as the canonical compact human-readable
  projection. Update the source catalog, generated database, and projection in
  the same commit as any new or corrected durable benchmark result.
- After making any workspace change, run the relevant validation, commit the change, and push the branch before handing work back to the user.
- When a run, experiment, debug session, or benchmark surfaces something
  genuinely interesting — a model quirk, a capability inversion, an emergent
  behavior, a harness effect that masqueraded as model behavior — append a
  dated, evidence-backed entry to `docs/insights.md` before finishing the
  task. That file is the project's institutional memory; its header defines
  the bar and the format. Routine scores do not qualify; surprises do.
- Keep commits scoped and use clear, human-readable commit messages.
- Never commit secrets, local credentials, or populated environment files.
- Launch normal model-backed runs through the declarative managed interface:
  `agent-world run --config CONFIG.json`. See `docs/run-quickstart.md` for the
  complete config reference and examples. Use `agent-world status RUN_ID` for
  event-derived status. Every launch includes a detached job controller that
  releases the startup gate, records ten-tick progress milestones, safely
  resumes interrupted/provider-paused checkpoints, reaps non-quota stalls, and
  finalizes benchmark evidence. `agent-world resume RUN_ID` and `agent-world
  finalize RUN_ID` remain explicit recovery tools after an attention state;
  they are not normal babysitting steps.
- Do not poll healthy runs tick by tick. The job controller checks locally every
  30 seconds and writes `controller-heartbeat.json` plus an append-only
  `controller-events.jsonl`. Report status only on user request or a
  terminal/attention event.
- Never launch a long-running run directly inside an `exec_command`, PTY, or
  other temporary foreground command session. The managed interface must place
  every independently executing cell under a durable detached supervisor and
  record its session and log before returning.
- `scripts/run-isolated-cohort` provides source isolation only; it does not
  supervise a process. Direct use is reserved for managed-run internals and
  deliberate recovery. The manager creates one detached worktree per cell,
  pins it to the clean launch commit, and preserves its cohort across resumes.
  Worktrees are an implementation detail for operators, not a manual launch
  step.
- A rate limit means a run is early, not broken. Benchmark runs wait up to
  `BENCHMARK_QUOTA_WAIT_HOURS` for the cap to reset and retry the same tick with
  the world frozen at a completed tick; `--quota-wait-hours` sets this for
  ad-hoc runs. Never work around a limit by restarting a run, and never let a
  run continue against a provider that is refusing calls - a failed decision
  becomes a `wait` action, which is fabricated agent behavior.
