---
name: run-agent-world-benchmark
description: Launch, resume, monitor, finalize, or report status on standardized Agent World benchmark trials. Use when the user explicitly asks for a benchmark, leaderboard result, certification, provisional benchmark, or named participant protocol; not for general simulations, smoke tests, or experiments.
---

# Run Agent World Benchmark

Run benchmark cells reproducibly and leave an analysis-ready evidence handoff. Do not turn the run thread into the model-performance analysis.

## Read the protocol first

Before taking run action, read `docs/benchmark-run-protocol.md` completely. It is the canonical operational procedure. Also read the current suite definition in `docs/model-benchmarks.md`; never infer the active protocol from an old command or directory name.

Follow `AGENTS.md` for repository-wide isolation, quota, validation, commit, push, and insight-journal rules.

## Interpret the request

- Only start or resume model-backed work when the user asks.
- Require explicit benchmark intent. The words “run,” “test,” “try,” “smoke test,” or “experiment” alone do not authorize benchmark defaults; use `$run-agent-world-experiment` for those requests.
- “Run the benchmark on MODEL” means the current standardized suite and its required seeds. At present that is Participant v7 on seeds 11 and 41. If the user asks for one seed, mark the study provisional.
- If the user names Participant v6, v7, or another suite, use that suite's documented rules and required seed set. Protocol versions share this workflow; do not invent a separate procedure or silently substitute the current suite.
- Do not ask the user to choose a world preset for a standardized benchmark. The named `--benchmark-protocol` owns and locks the preset and every behavior-defining setting. If the user requests a different preset or setting, classify the run as an experiment or controlled diagnostic rather than standard benchmark evidence.
- Resolve and record the exact brain, provider, callable model ID, returned model identity, reasoning effort, billing mode, and connector before launch. Do not substitute a similarly named model.
- Treat protocol changes, nonstandard seeds, mixed populations, alternate reasoning settings, or connector experiments as controlled or diagnostic variants, never as standard leaderboard evidence.

## Execute the state machine

1. **Preflight:** inspect the current protocol, provider/model availability, clean launch commit, study manifest, unique cohort IDs, output paths, and required environment without exposing secrets.
2. **Launch:** run every independently executing seed through `scripts/run-isolated-cohort`, pinned to the same clean launch commit. Use one detached worktree and cohort ID per seed.
3. **Health gate:** let the harness run unattended through tick 5. Check the recorded startup gate once; do not manually poll every tick or duplicate the harness check.
4. **Monitor by event:** after the gate passes, inspect only meaningful transitions: startup failure, quota wait, checkpoint pause, process exit, completion, or a user status request. Remain responsible for every cell launched by the task until it reaches a terminal or explicit waiting state; arrange the task's next check around process completion rather than abandoning a background run after the tick-5 gate.
5. **Resume safely:** a quota limit is a waiting state. Keep the world frozen at a completed tick, wait up to the configured allowance, and resume the same checkpoint through the same cohort and launch commit. Never restart to evade a limit and never turn failed provider calls into agent `wait` actions.
6. **Completion check-in:** when a run process exits or completion is first observed, proactively return to that cell before reporting it done. Verify the terminal tick and event, expected decision count, full usage coverage, clean integrity, exact model provenance, report protocol/fingerprint, and required artifacts. Finalize a completed seed immediately even if another seed is still waiting. Process exit or tick 50 alone is not a completed benchmark handoff.
7. **Finalize accounting:** derive public API-list cost independently from recorded token usage and a dated provider rate card. Preserve provider- or CLI-reported subscription cost only as a separately labelled field.
8. **Finalize transfers during that check-in:** for Participant v7, verify deterministic agent-declared `gift`, `payment`, and `barter` accounting and do not invoke an LLM classifier. For Participant v6 ledgers, apply the frozen post-run gift-classification procedure exactly once when gifts exist; validate complete coverage, hashes, and evidence quotes, then regenerate the report from the frozen artifact. Never overwrite a valid frozen artifact. Record `none_no_gifts` when no gifts exist. Do not leave classification for the analysis task to discover or perform.
9. **Handoff:** only after cost and transfer finalization, write the study manifest's `analysis_readiness` block using the contract in `docs/benchmark-run-protocol.md`. A completed simulation is not analysis-ready—and must not be reported simply as “done”—until this gate passes.

## Preserve evidence boundaries

- Keep worktrees and checkpoints until analysis is complete.
- Do not silently repair provenance, integrity, transfer accounting, or cost evidence merely to make a run leaderboard-eligible. Mark the exact blocker and retain the evidence.
- Do not admit a result to the catalog or leaderboard from the run workflow. Durable admission and completed-run interpretation belong to `$report-agent-world-runs` after the readiness gate.
- Report status with artifacts and state: completed seeds, waiting seeds, last completed tick, stop reason, quota deadline, launch commit, integrity, transfer-finalization mode, cost status, and readiness status.

## Finish repository work

Validate any changed code or metadata, append `docs/insights.md` only for a genuine evidence-backed surprise, then make a scoped commit and push it. Never commit secrets or populated environment files.
