# Agent World model benchmarks

Agent World Participant v4 is the current standardized model benchmark suite.
It keeps the deterministic protocol and evidence safeguards from v3 while
correcting two construct-validity failures:

- an all-`wait` policy can no longer receive a perfect execution score;
- internal transfers and structure input cost no longer count as value created.

Participant v1, v2, and v3 reports remain historical artifacts. They are not
silently rescored or mixed into a v4 leaderboard.

Preserved examples include the
[GPT-5.4 v2 report](gpt-5-4-benchmark.md), the
[Spark v1/v2 diagnostic](gpt-5-3-codex-spark-benchmark.md), and the
[Spark v3 provisional report](gpt-5-3-codex-spark-v3-benchmark.md).

## Result tiers

- **Diagnostic:** any run, including mixed populations, stopped runs, degraded
  runs, historical protocols, and nonstandard seeds.
- **Provisional:** one integrity-clean, complete v4 run on predeclared seed 11.
- **Replicated certified:** one integrity-clean, complete v4 run on every
  required seed: 11, 41, 73, 101, and 137.

Five distinct worlds give the leaderboard a visible per-seed distribution
instead of presenting two pooled observations to two decimal places as if
their uncertainty were known. Certification still pools raw numerators and
denominators for the official score, but the aggregate also retains each
replication and reports its values, mean, median, range, sample standard
deviation, and descriptive 95% Student-t interval.

Duplicate copies of a required seed are not certified evidence. Repeated-seed
studies remain useful diagnostics for model sampling variance, but they must
not overweight one world in the standardized pooled result.

## Frozen trial

Every benchmark run uses:

| Setting | Required value |
|---|---|
| Seeds | 11, 41, 73, 101, 137 |
| Population | 10 copies of one model |
| Horizon | 50 ticks |
| Diagnostic checkpoints | ticks 30 and 40 |
| Official endpoint | tick 50 |
| World | `organic-generalists` |
| Objective | neutral |
| Reasoning effort | medium |
| Decisions | raw |
| Action feedback | baseline |
| Resolution | simultaneous |
| Global/provider workers | 4 |
| Connector | `stateless-v3` |
| Provider conversation | stateless |
| Private agent I/O | enabled |

Launch the provisional seed:

```bash
python3 -m agent_world.cli run \
  --benchmark-protocol participant-v4 \
  --brain codex --model gpt-5.6-luna \
  --seed 11 \
  --out runs/benchmarks/luna-v4/seed-11/run.jsonl \
  --snapshot runs/benchmarks/luna-v4/seed-11/run-snapshot.json \
  --progress
```

Run the same command with seeds 41, 73, 101, and 137 for certification, using
a separate output directory for each seed. Aggregate the five reports with:

```bash
python3 -m agent_world.cli benchmark \
  runs/benchmarks/luna-v4/seed-11/run-report.json \
  runs/benchmarks/luna-v4/seed-41/run-report.json \
  runs/benchmarks/luna-v4/seed-73/run-report.json \
  runs/benchmarks/luna-v4/seed-101/run-report.json \
  runs/benchmarks/luna-v4/seed-137/run-report.json \
  --out runs/benchmarks/luna-v4/leaderboard
```

The benchmark flag locks every other setting. A conflicting option fails
before a model call.

## Scores

Higher is better. Effective execution and sustained competence range from 0
to 100. Entrepreneurial agency and its economic-productivity diagnostic start
at zero and have no maximum; 100 is a frozen reference target, not a ceiling.

### 1. Effective execution

This score replaces v3's planning-execution label:

```text
action feasibility =
  valid submitted proposals / submitted proposals excluding contention

purposeful activity =
  decision opportunities with at least one successful meaningful action
  / decision opportunities

effective execution =
  geometric mean(action feasibility, purposeful activity)
```

Same-tick contention is excluded from feasibility. Independently confirmed
model-output contract violations are invalid proposals. Provider, quota,
adapter, harness, and ambiguous-boundary failures invalidate the trial rather
than becoming model mistakes.

Purposeful activity counts at most once per agent-tick. Successful movement,
resource work, consumption, crafting, construction, ownership, exchange,
contracts, gifts, group administration, storage, maintenance, and access
actions count. `wait`, `inspect`, and communication-only ticks do not.

This term prevents action spam from gaining extra activity credit and prevents
an all-`wait` policy from scoring 100. Waiting can still be strategically
correct; a model is not required to act on every tick. The rate simply makes
the amount of exercised agency visible alongside proposal accuracy.

### 2. Sustained competence

```text
geometric mean(
  effective execution,
  survival continuity,
  living-accessible material outcome
)
```

- **Survival exposure** is completed decision opportunities divided by the
  full target horizon.
- **Endpoint population health** includes dead agents as zero and living
  agents by remaining health.
- **Survival continuity** is the geometric mean of exposure and endpoint
  health.
- **Living-accessible material outcome** is living cohort value relative to
  three times starting endowment, capped at 100.

The material term stays bounded so extreme inventories cannot compensate for
collapse or ineffective execution. Uncapped economic output is reported
separately.

### 3. Entrepreneurial agency

Participant v4 uses a conservative definition appropriate to the current
simulation:

```text
geometric mean(venture initiative score, net value creation score)
```

Venture initiatives are successful trade offers, construction starts,
credit-contract offers, and access-fee policies. The initiative component
reaches 100 at five initiatives per 100 possible agent-ticks. That anchor is
close to demonstrated strong-model behavior rather than v3's unreachable
20-per-100 scale.

Net value created is:

```text
max(0, living-accessible terminal value - starting endowment)
```

normalized per 100 possible agent-ticks. Its component reaches 100 at 20 value
per 100 agent-ticks and remains uncapped above that target.

The anchors were sanity-checked against preserved clean GPT-5.4 evidence rather
than guessed in isolation. Its historical v2 initiative rate was 4.25 per 100
agent-ticks, while applying the v4 accounting diagnostic to its two preserved
v3 event ledgers yields net-value rates of 30.4 and 17.0. Those runs are not v4
benchmark results; they only establish that targets of 5 and 20 are in a
demonstrated, interpretable range.

This deliberately measures cohort outcomes rather than pretending to identify
the private profit of each homogeneous agent:

- trading goods among cohort members does not change cohort value;
- access fees and contract repayments within the cohort are transfers;
- completing a structure converts inputs into a same-value asset;
- a structure contributes only when its production or services ultimately
  improve the cohort's living-accessible terminal outcome;
- a pure foraging cohort has no venture initiatives and therefore receives
  zero entrepreneurial agency even if it accumulates materials;
- wash trading has initiatives but no net value creation and therefore also
  receives zero.

The score rewards building, exchange, credit, priced access, and other venture
attempts when they coexist with a real economic outcome. It does not claim to
isolate causal gains from trade. That would require heterogeneous preferences,
external market counterparties, or a validated utility counterfactual that the
current simulation does not provide.

### Economic productivity diagnostic

The uncapped value-creation component is also reported on its own. It shows
whether a cohort created living-accessible material value regardless of
whether it used entrepreneurial institutions. This keeps wealth information
visible without allowing it to overwhelm sustained competence.

## Recipe-consistent benchmark values

V3 used the world's hand-set book values directly, which made some productive
transformations look like wealth destruction. V4 starts with that table and
raises any single-output recipe's result until it is worth at least its inputs.

| Resource | V4 benchmark value |
|---|---:|
| coin | 3 |
| water | 1 |
| food | 2 |
| fiber | 2 |
| wood | 3 |
| stone | 4 |
| ore | 8 |
| ingot | 19 |
| tool | 12 |
| advanced tool | 43 |

Consequently, smelting two ore plus one wood into an ingot preserves at least
19 value, minting one ingot into eight coins preserves at least 24, and
crafting an advanced tool preserves its 43-value input bundle. These are
benchmark accounting values; they do not modify inventories, recipes, trade
rules, or agent-facing prices.

## Integrity and versioning

A run is diagnostic-only when a required setting differs, the run stops early,
the population is mixed, external or harness integrity fails, usage coverage
is incomplete, or its fingerprint differs.

The run records a SHA-256 fingerprint of scoring code plus behavior-defining
provider, world, rule, map, model, interface, runner, and session sources.
Changing a formula, target, world, or harness requires a new suite version.
A narrow telemetry correction may use a scoring revision only when preserved
raw evidence can reproduce it without changing trial behavior.

V4 has no compatibility exception for v3 reports because the old event
aggregates do not contain the new purposeful-activity construct and because
the economic formula changed materially.

## Reporting standard

Human-facing reports put these scores first:

1. effective execution;
2. sustained competence;
3. entrepreneurial agency.

Supporting evidence must include proposal failures with denominators,
contention, action-point overruns, purposeful agent-ticks, survival, endpoint
health, living value, net value created, initiatives, decision/provider
failures, usage, result tier, and seed coverage.

Certified aggregate reports also include every seed's scores and the
descriptive spread. Tick-30 and tick-40 trajectories remain diagnostics; only
tick 50 is the official endpoint.

Communication, prosocial behavior, leadership, deception, and antisocial
behavior remain unscored. Frequency alone is not a validated measure of their
quality or intent.
