# Agent World general experiment runs

This procedure covers model-backed Agent World simulations whose purpose is to
test a model, harness change, world mechanic, connector, prompt, or operational
assumption without producing standardized benchmark evidence.

A request is a benchmark only when the user explicitly asks for a benchmark,
leaderboard result, certification, provisional benchmark, or named participant
protocol. Those requests follow
[benchmark-run-protocol.md](benchmark-run-protocol.md). Do not infer benchmark
intent from “run,” “test,” “try,” “smoke test,” or “experiment.”

## Preset selection

Before launching a new experiment, ask once which world preset to use when the
user has not already supplied a preset or equivalent world configuration. The
question should offer the default and the currently available built-ins from
`python3 -m agent_world.cli run --help`. Do not interrupt a checkpoint resume to ask again,
and do not ask when the user already said to use defaults.

The general experiment default is **`organic-generalists`**:

- classic world variant;
- organic economy;
- dispersed geography;
- neutral objective; and
- generalist agents.

This is a broad economic sandbox without the frontier benchmark's seasons,
storms, winter exposure, roads, and irrigation. Use it when the user says
“default,” expresses no preference after being asked, or delegates the choice.

The built-in alternatives currently are:

- `baseline`: classic world, baseline economy, shared oasis, neutral objective,
  generalists;
- `experimental-organic-specialists`: classic world, organic economy,
  dispersed geography, neutral objective, specialists; and
- `frontier-generalists`: organic/dispersed/neutral generalists in the frontier
  world with seasons, storms, exposure, roads, and irrigation.

The user may also choose explicit economy, geography, objective, or
specialization overrides instead of relying on a named preset. Inspect current
CLI help before presenting choices because the registry can evolve.

## Default scope

A general experiment defaults to **seed 11 only**. Seed 41 is not an ordinary
replication default; it belongs to benchmark certification or to an explicitly
requested multi-seed experiment.

Other settings come from the experimental question:

- use the fewest agents and ticks that can actually test the claim;
- choose the relevant world, reasoning setting, connector, and feedback mode;
- record every setting rather than describing the run as “standard”; and
- use distinct seeds or replications only when the user asks or the experiment
  genuinely tests variability.

Matching benchmark settings by coincidence does not turn a general run into
benchmark evidence. Benchmark intent, suite, seeds, and locked settings must be
predeclared before model calls.

## Manifest and provenance

Create a manifest before launch containing:

- `run_kind: experiment` and the concrete question being tested;
- seed, agents, ticks, world preset and variant, reasoning, connector,
  feedback, resolution, and worker settings;
- requested model, callable model ID, provider/brain, expected returned model
  identity, and billing mode;
- a clean pinned launch commit, output paths, and unique cohort IDs; and
- the completion condition and evidence that will answer the question.

Do not reuse or overwrite a benchmark cell, prior experiment, report,
classification artifact, or checkpoint.

## Isolation and monitoring

Every independently executing model-backed cell still runs through
`scripts/run-isolated-cohort` in a detached worktree pinned to its clean launch
commit. Preserve the worktree through completion and any requested analysis.
See [isolated-run-worktrees.md](isolated-run-worktrees.md) for mechanics and
[observability.md](observability.md) for logs and checkpoints.

For a run reaching tick 5, let the harness perform its automatic startup gate
and inspect that result once. Do not babysit every tick. For a shorter smoke
test, verify once that the intended provider/model boundary was exercised and
that the requested terminal condition was reached.

After startup, monitor only meaningful events: process exit, startup failure,
quota wait, checkpoint pause, completion, or a user status request.

A provider quota is a waiting state. Freeze at a completed tick and resume the
same checkpoint through the same cohort and launch commit. Never restart to
evade a limit, continue calling a refusing provider, or convert failed calls
into fabricated agent actions.

## Completion and accounting

Verify the intended endpoint, expected calls or decisions, integrity, usage
coverage, resolved model identity, and required artifacts. Unlike benchmark
admission, an experiment may intentionally exercise a failure; preserve and
label that outcome instead of forcing `clean` integrity.

Always preserve token usage. Derive public API-list cost when cost or
cross-model efficiency is part of the experimental question, and keep any
provider/CLI subscription figure separate.

Transfer handling depends on what will be claimed:

- Participant v7 uses deterministic agent-declared `gift`, `payment`, and
  `barter` kinds and never needs an LLM gift classifier.
- A Participant v6 run that will receive entrepreneurship, commerce, or
  economy-performance analysis must run the frozen post-run classifier after
  completion, with the same coverage, hash, and evidence-quote checks as a v6
  benchmark.
- A smoke test unrelated to economic outcomes may skip v6 classification, but
  its manifest and handoff must say `transfer_accounting: not_required` and
  explain why. It cannot later support those economic claims until finalized.

## Evidence boundary

General experiments are `diagnostic_only`. They do not enter
`data/run-sources.json`, the generated benchmark database, or the leaderboard,
and seed 11 alone does not make them provisional benchmark evidence.

The handoff states the experiment question, exact settings, seed, cohort,
launch commit, endpoint, integrity, usage, cost and transfer-accounting status,
artifacts, and the narrow conclusion the evidence supports. If the user later
requests diagnostic economic analysis, complete any relevant accounting first;
if the user wants benchmark placement, launch a predeclared benchmark study
through the benchmark workflow.
