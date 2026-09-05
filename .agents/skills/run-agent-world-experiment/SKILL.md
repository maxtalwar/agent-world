---
name: run-agent-world-experiment
description: Launch, resume, monitor, or finalize general Agent World simulations, smoke tests, harness tests, and exploratory model runs. Use when the user asks to run or test something without explicit benchmark, leaderboard, certification, or participant-protocol intent; default to seed 11 only.
---

# Run Agent World Experiment

Run non-benchmark Agent World work at the smallest scope that answers the user's question. General runs are diagnostic evidence, not provisional benchmarks.

## Read the experiment protocol

Before taking run action, read `docs/agent-world-experiment-runs.md` completely. Follow `AGENTS.md` for isolation, quota handling, validation, commits, pushes, and the insight journal.

Read `docs/run-quickstart.md` for managed launch, status, resume, and config syntax.

## Route and scope the request

- Only launch or resume model-backed work when the user asks.
- Default to one world per condition, normally seed 11, matching that seed across conditions. Non-Codex models require an explicit request for extra seeds; "matched seeds" alone does not authorize replication. Codex models may use seeds 11 and 41 when useful, except expensive Astra experiments default to one. Follow the usage policy in AGENTS.md; explicit user scope overrides defaults.
- Before launching a new experiment, if the user has not specified a preset or equivalent world configuration, ask once which preset to use. Present `frontier-generalists` as the default and summarize the current alternatives from CLI help. Do not ask again when resuming an existing manifest or when the user already said to use defaults.
- The experiment default is `frontier-generalists`: frontier world, organic economy, dispersed geography, neutral objective, and generalist agents. Use it when the user chooses the default or delegates the choice.
- Choose agents, ticks, world, reasoning, and other settings from the experiment's purpose. Do not inherit the benchmark's full horizon or locked trial unless the user requests those settings.
- Record `run_kind: experiment`, the question being tested, all settings, exact model/provider provenance, and why the chosen scale is sufficient.
- If the user explicitly asks for a benchmark, leaderboard result, certification, provisional benchmark, or named participant protocol, use `$run-agent-world-benchmark` instead.

## Execute safely

1. Preflight the exact model boundary, clean launch commit, noncolliding paths, study manifest, and required non-secret configuration.
2. Write an experiment config and launch it with `agent-world run --config CONFIG.json`. The manager creates the distinct pinned cohorts and durable detached supervisors. Never run the model-backed process directly inside a temporary command/PTTY session; worktrees are not a manual operator step.
3. For runs reaching tick 5, inspect the automatic startup health gate once after tick 5. For shorter smoke tests, verify the intended provider/model interaction and terminal state once.
4. Monitor by event rather than polling every tick: startup failure, quota wait, checkpoint pause, process exit, completion, or a user status request.
5. Treat quota refusal as a frozen waiting state. Use `agent-world resume RUN_ID` when resumption is needed; it reuses the same checkpoint, cohort, and launch commit. Never restart to evade the limit or fabricate agent behavior.
6. At completion, verify the intended endpoint, integrity, usage coverage, model identity, and expected artifacts. Preserve exact deviations because they are often the point of an experiment.

## Finalize proportionally

- Always preserve the usage ledger and separate model, provider, harness, and quota failures.
- Derive public API-list cost when cost or cross-model efficiency is part of the question; keep subscription/CLI cost separately labelled.
- Participant v7 transfer declarations remain deterministic and need no LLM classifier.
- For a Participant v6 experiment, run the frozen gift classifier after completion when the user will receive entrepreneurship, commerce, or economy-performance analysis. A smoke test that does not analyze those outcomes may retain unclassified transfers, but its manifest must say so.
- Mark the result `diagnostic_only`. Do not add it to the benchmark catalog or present it as provisional merely because it used seed 11 or happened to match some benchmark settings.

## Handoff

Report the experiment question, seed, settings, cohort, launch commit, last completed tick, integrity, usage, cost/classification status, artifacts, and exact conclusion supported. If a later performance report needs accounting that was intentionally skipped, finish it through this skill before using `$report-agent-world-runs`.

Validate changed code or metadata, record only genuinely surprising evidence in `docs/insights.md`, then make a scoped commit and push it. Never commit secrets or populated environment files.
