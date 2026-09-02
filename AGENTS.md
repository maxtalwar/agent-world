# Repository workflow

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
  event-derived status and `agent-world resume RUN_ID` for checkpoint recovery.
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
