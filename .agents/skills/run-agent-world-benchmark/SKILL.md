---
name: run-agent-world-benchmark
description: Launch, resume, monitor, finalize, or report status on Agent World model benchmark runs. Use for requests to run a model through the standardized benchmark, continue a paused seed, handle quota waits, verify completion, or prepare run evidence for later analysis; not for interpreting completed model performance.
---

# Run Agent World Benchmark

Run benchmark cells reproducibly and leave an analysis-ready evidence handoff. Do not turn the run thread into the model-performance analysis.

## Read the protocol first

Before taking run action, read `docs/benchmark-run-protocol.md` completely. It is the canonical operational procedure. Also read the current suite definition in `docs/model-benchmarks.md`; never infer the active protocol from an old command or directory name.

Follow `AGENTS.md` for repository-wide isolation, quota, validation, commit, push, and insight-journal rules.

## Interpret the request

- Only start or resume model-backed work when the user asks.
- “Run the benchmark on MODEL” means the current standardized suite and its required seeds. At present that is Participant v7 on seeds 11 and 41. If the user asks for one seed, mark the study provisional.
- Resolve and record the exact brain, provider, callable model ID, returned model identity, reasoning effort, billing mode, and connector before launch. Do not substitute a similarly named model.
- Treat protocol changes, nonstandard seeds, mixed populations, alternate reasoning settings, or connector experiments as controlled or diagnostic variants, never as standard leaderboard evidence.

## Execute the state machine

1. **Preflight:** inspect the current protocol, provider/model availability, clean launch commit, study manifest, unique cohort IDs, output paths, and required environment without exposing secrets.
2. **Launch:** run every independently executing seed through `scripts/run-isolated-cohort`, pinned to the same clean launch commit. Use one detached worktree and cohort ID per seed.
3. **Health gate:** let the harness run unattended through tick 5. Check the recorded startup gate once; do not manually poll every tick or duplicate the harness check.
4. **Monitor by event:** after the gate passes, inspect only meaningful transitions: startup failure, quota wait, checkpoint pause, process exit, completion, or a user status request.
5. **Resume safely:** a quota limit is a waiting state. Keep the world frozen at a completed tick, wait up to the configured allowance, and resume the same checkpoint through the same cohort and launch commit. Never restart to evade a limit and never turn failed provider calls into agent `wait` actions.
6. **Complete each cell:** verify the terminal tick and event, expected decision count, full usage coverage, clean integrity, exact model provenance, report protocol/fingerprint, and required artifacts. Finalize a completed seed immediately even if another seed is still waiting.
7. **Finalize accounting:** derive public API-list cost independently from recorded token usage and a dated provider rate card. Preserve provider- or CLI-reported subscription cost only as a separately labelled field.
8. **Finalize transfers:** for Participant v7, verify deterministic agent-declared `gift`, `payment`, and `barter` accounting and do not invoke an LLM classifier. For Participant v6 ledgers, apply the frozen post-run gift-classification procedure exactly once when gifts exist; validate complete coverage, hashes, and evidence quotes. Never overwrite a valid frozen artifact. Record `none_no_gifts` when no gifts exist.
9. **Handoff:** write the study manifest's `analysis_readiness` block using the contract in `docs/benchmark-run-protocol.md`. A completed simulation is not analysis-ready until this gate passes.

## Preserve evidence boundaries

- Keep worktrees and checkpoints until analysis is complete.
- Do not silently repair provenance, integrity, transfer accounting, or cost evidence merely to make a run leaderboard-eligible. Mark the exact blocker and retain the evidence.
- Do not admit a result to the catalog or leaderboard from the run workflow. Durable admission and cross-model interpretation belong to `$analyze-agent-world-benchmarks` after the readiness gate.
- Report status with artifacts and state: completed seeds, waiting seeds, last completed tick, stop reason, quota deadline, launch commit, integrity, transfer-finalization mode, cost status, and readiness status.

## Finish repository work

Validate any changed code or metadata, append `docs/insights.md` only for a genuine evidence-backed surprise, then make a scoped commit and push it. Never commit secrets or populated environment files.
