# Repository workflow

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
- Never launch a long-running model-backed simulation directly from the shared
  checkout. Launch every independently executing run cell with
  `scripts/run-isolated-cohort` so it runs from its own detached worktree,
  pinned to the clean launch commit. Use a distinct cohort ID for every seed or
  simultaneous cell. Keep that worktree until the run is complete and analyzed,
  and resume checkpoints through the same cohort ID and commit. A mixed-model
  simulation is one run cell and therefore uses one worktree.
- A rate limit means a run is early, not broken. Benchmark runs wait up to
  `BENCHMARK_QUOTA_WAIT_HOURS` for the cap to reset and retry the same tick with
  the world frozen at a completed tick; `--quota-wait-hours` sets this for
  ad-hoc runs. Never work around a limit by restarting a run, and never let a
  run continue against a provider that is refusing calls - a failed decision
  becomes a `wait` action, which is fabricated agent behavior.
