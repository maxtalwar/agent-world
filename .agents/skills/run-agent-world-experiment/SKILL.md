---
name: run-agent-world-experiment
description: Launch, resume, monitor, or finalize general Agent World simulations, smoke tests, harness tests, and exploratory model runs. Use when the user asks to run or test something without explicit benchmark, leaderboard, certification, or participant-protocol intent; default to seed 11 only.
---

# Run Agent World Experiment

Use for ordinary simulations, smoke tests and harness experiments. Explicit
benchmark or certification requests belong to run-agent-world-benchmark.

## Define the question

Launch only user-authorized model-backed work. Record the question, exact
model/connector, treatment and sufficient scale in an experiment config.
Default to one world per condition, normally seed 11; match seeds across
conditions. Follow AGENTS.md for extra replications and provider usage limits.

Use the user's world/settings or established comparison baseline. Clarify a
genuinely unresolved world choice when it would change the question; otherwise
use delegated defaults. Do not inherit a full benchmark horizon or restrictions
merely because an experiment uses a benchmark recipe's defaults. Keep altered
conditions and source provenance explicit.

## Operate and hand off

Use python3 -m agent_world run --config CONFIG.json --dry-run, then launch
without --dry-run. Consult docs/run-quickstart.md for configuration and commands.
The managed runner owns isolation, supervision, gates, quota waits and recovery.
Inspect meaningful events or requested status, not ticks. Arrange follow-up
using the user's preferences; remove finished studies and stop when none remain.
Recover the existing study only after resolving an attention blocker.

Consult docs/agent-world-experiment-runs.md for experiment-specific accounting
or evidence questions. Match finalization to the intended analysis: cost
comparisons need token-derived cost; commerce analysis needs the selected
transfer policy's evidence. Keep skipped accounting explicit.

Report the question, actual settings, terminal state, integrity and artifact
location. General experiments remain diagnostic even if they resemble a
benchmark. Use report-agent-world-runs to interpret completed evidence.
Follow AGENTS.md for repository changes.
