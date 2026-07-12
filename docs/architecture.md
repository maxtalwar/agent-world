# Infrastructure architecture

Agent World separates deterministic world behavior from model orchestration. The engine remains the source of truth; provider brains can only propose decisions that the engine validates.

## Run ownership

Every CLI, factorial-experiment, and observatory run uses the same infrastructure path:

```text
PopulationSpec -> BrainRuntime -> SimulationSession -> SimulationRunner -> WorldEngine
                                      |
                                      +-> IncrementalRunWriter
                                      +-> usage and plan telemetry
                                      +-> terminal run report
```

- `BrainSpec` resolves the selected brain, model, reasoning effort, and concurrency once.
- `PopulationSpec` expands ordered model cohorts into stable agent assignments. Uniform runs are represented as one-cohort populations, keeping the lifecycle path identical.
- `BrainRuntime` owns mutable usage, quota, and throttling state for exactly one run. It is shared by that run's agent brains and never stored on a provider class or routed through process environment variables.
- Provider-scoped runtime views share the run ledger while isolating Claude, Codex, and API quota/throttle state from one another in mixed populations.
- Mixed runs freeze stratified model assignments before tick zero and persist the exact mapping in lifecycle events, manifests, and checkpoints. Provider semaphores enforce independent concurrency ceilings inside the global decision pool.
- `SimulationSession` owns lifecycle events, the target-tick loop, quota and external-stop handling, progress hooks, checkpoint flushes, plan snapshots, and terminal reports.
- `SimulationRunner` remains the thin observe-decide-resolve bridge for one tick.
- `WorldEngine` owns all deterministic state transitions and validation.

CLI, experiment, and observatory callers retain their presentation-specific responsibilities. Experiments update provenance manifests through session callbacks; the observatory updates live status and pause/stop controls through callbacks. They do not implement separate simulation loops.

The observatory server/controller and its frontend are separate artifacts: Python behavior lives in `observer.py`, while the packaged HTML/CSS/JavaScript application lives in `agent_world/static/observer.html`.

## Persistence

Events are appended once to JSONL. The visible snapshot and crash checkpoint are atomically replaced. Checkpoints exclude historical events and reference the durable event ledger, so checkpoint writes do not grow with run history. Resume restores both engine state and RNG state.

The JSON snapshot is an observational export, not a canonical restore format. It should not be used to reconstruct a world because it may omit internal or private state. Trusted local checkpoints are the canonical resume artifact.

## Telemetry

Each `BrainRuntime` optionally owns one usage JSONL path. Concurrent agents serialize complete records to that path. Reports distinguish API dollars, exact simulation-only Codex credits, and coarse account-level plan snapshots.

## Tests and CI

The runtime has no required third-party dependencies. GitHub Actions installs the package and runs `python -m unittest discover -s tests -q` on Python 3.10 and 3.12 for pushes and pull requests.
