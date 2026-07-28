# Isolated worktrees for long-running simulations

Every independently executing model-backed simulation must run from its own
detached Git worktree. The worktree is pinned to the launch commit and retained
through completion and analysis.

This prevents a concurrent checkout, merge, source edit, or fingerprint change
in the shared repository from changing or temporarily removing files beneath a
live simulation. It also makes checkpoint resume use the exact code that
created the checkpoint.

Use:

```bash
screen -dmS gpt54mini-s11 scripts/run-isolated-cohort \
  --cohort gpt54mini-v4-seed11 -- \
  python3 -m agent_world.cli run \
    --benchmark-protocol participant-v4 \
    --brain codex --model gpt-5.4-mini --seed 11 \
    --out runs/benchmarks/gpt54mini-v4/seed-11/run.jsonl \
    --snapshot runs/benchmarks/gpt54mini-v4/seed-11/run-snapshot.json \
    --progress
```

The launcher:

1. Requires a clean tracked checkout when using the default `HEAD`.
2. Resolves that revision to an immutable commit.
3. Creates `.worktrees/run-cohorts/COHORT-SHA` as a detached worktree.
4. Links the canonical ignored `.env` when present.
5. Rewrites relative `runs/...` command arguments to the canonical repository,
   keeping all artifacts in the usual location.
6. Executes the run from the isolated source tree.

Use a different `--cohort` ID for every independently executing seed or
experimental cell. Two simultaneous benchmark seeds therefore use two
worktrees. A mixed-model simulation is still one cell because every model
cohort participates in the same world process.

For a checkpoint resume, reuse the cohort ID and explicitly provide the
original launch commit:

```bash
screen -dmS gpt54mini-s11-resume scripts/run-isolated-cohort \
  --cohort gpt54mini-v4-seed11 --commit LAUNCH_SHA -- \
  python3 -m agent_world.cli run \
    --resume-checkpoint runs/benchmarks/gpt54mini-v4/seed-11/run-checkpoint.pkl \
    --ticks 50 --progress
```

Do not remove the worktree while a run or its analysis is active. After the
study is complete and its durable artifacts are committed, remove it explicitly
with `git worktree remove PATH`.
