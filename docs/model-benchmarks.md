# Agent World model benchmarks

Agent World Participant v2 is the current standardized model benchmark suite.
It turns deterministic run telemetry into three repeatable scores while keeping
the raw evidence and formulas visible.

The suite distinguishes:

- **Diagnostic scores:** useful measurements from any run, including mixed
  civilizations, stopped runs, degraded runs, and older harnesses.
- **Provisional benchmark results:** one clean, complete 40-tick run on the
  predeclared seed 11 that exactly follows participant-v2.
- **Replicated certified benchmark results:** pooled results from clean,
  complete 40-tick runs on both required seeds, 11 and 41.

This prevents an interesting exploratory run from being presented as directly
comparable to a controlled benchmark.

## Recorded attempts

- [GPT-5.4, 2026-07-25](gpt-5-4-benchmark.md): provisional Participant v2
  benchmark from a clean, complete seed-11 run; planning 86.54, sustained
  competence 78.45, and entrepreneurial agency 22.17.
- [GPT-5.3-Codex-Spark, 2026-07-24](gpt-5-3-codex-spark-benchmark.md):
  diagnostic-only; both runs exhausted the dedicated weekly quota before tick
  40 and each contained one model-decision failure. That attempt also exposed
  Participant v1 competence inflation; its corrected v2 diagnostic is 51.03,
  not 82.23.

Participant v1 is retired. It counted dead agents' inventories as material
success, measured survival only over ticks that happened to run, and lacked an
endpoint-health check. Historical v1 reports remain historical artifacts and
must not be silently mixed with v2 results.

## Standard and usage-constrained trials

Every benchmark run uses the same pure-model 40-tick trial:

| Setting | Required value |
|---|---|
| Seeds | 11 and 41 |
| Population | 10 copies of one model |
| Horizon | 40 ticks |
| World | `organic-generalists` |
| Objective | neutral |
| Reasoning effort | medium |
| Decisions | raw |
| Action feedback | baseline |
| Turn resolution | simultaneous |
| Global/provider workers | 4 |
| Private agent I/O log | enabled |
| Connector | `stateless-v3` |
| Provider conversation | stateless |

Pure-model trials isolate a model's behavior better than mixed populations.
Mixed runs remain valuable ecology experiments, but one model can change the
resource pressure and opportunities faced by every other cohort.

Launch the predeclared seed-11 trial:

```bash
python3 -m agent_world.cli run \
  --benchmark-protocol participant-v2 \
  --brain codex --model gpt-5.6-luna \
  --seed 11 \
  --out runs/benchmarks/luna-v2/seed-11/run.jsonl \
  --snapshot runs/benchmarks/luna-v2/seed-11/run-snapshot.json \
  --progress
```

For a usage-constrained model, one clean seed-11 run is sufficient for a
**provisional benchmark**. Seed 11 is fixed in advance so researchers cannot
choose the more favorable world after seeing outcomes. A seed-41-only result is
an incomplete replication, not a provisional benchmark.

For the full **replicated certified benchmark**, repeat with `--seed 41` and a
different output directory. The seed-41 result can be added later to promote an
existing provisional result without rerunning seed 11. The benchmark flag sets
and locks every other setting. A conflicting option fails before any model
call.

Each run report automatically contains `benchmarks`. Pool the two reports with:

```bash
python3 -m agent_world.cli benchmark \
  runs/benchmarks/luna-v2/seed-11/run-report.json \
  runs/benchmarks/luna-v2/seed-41/run-report.json \
  --out runs/benchmarks/luna-v2/leaderboard
```

Aggregation pools the raw numerators and denominators before scoring. It does
not average the two run scores. Passing only the clean seed-11 report emits a
provisional result; passing both required seeds emits a replicated certified
result.

The horizon remains 40 ticks in both tiers. Shortening a constrained model to
30 ticks is not allowed: late survival collapses and delayed consequences can
make a weak long-horizon planner look artificially successful. If even one
40-tick run is unaffordable, the available evidence remains diagnostic.

## The three scores

All scores range from 0 to 100. Higher is better. Formulas and every component
are stored in the machine-readable run report.

### 1. Planning execution

This measures how often the model proposes an action that is actually feasible.

```text
100 × (submitted actions - contention - invalid proposals)
    / (submitted actions - contention)
```

Same-tick contention is excluded. If two agents both make a valid attempt at
the final resource, losing resolution priority is not a planning mistake.

Action-point overruns are included among invalid proposals and also reported
separately. Provider failures do not become planning mistakes; they invalidate
the benchmark trial through its quality checks.

This score deliberately does not reward boldness. A cautious model can plan
accurately without being entrepreneurial, which is exactly the distinction the
suite is intended to reveal.

### 2. Sustained competence

This asks whether valid planning translates into sustained success:

```text
geometric mean(
  planning execution,
  survival continuity,
  living-accessible material outcome
)
```

- **Survival exposure** is successful decision opportunities divided by the
  complete target horizon, including ticks lost when a run stops early.
- **Endpoint population health** is the cohort's remaining health divided by
  its initial maximum health. Dead agents contribute zero, and barely surviving
  agents receive only their remaining health fraction.
- **Survival continuity** is the geometric mean of survival exposure and
  endpoint population health. This preserves the timing information from
  exposure while preventing a late collapse from looking healthy.
- **Living-accessible material outcome** is economic value still attributable
  to living cohort members relative to three times the cohort's starting
  endowment. Dead agents' inventories and directly owned estates do not count.
  The score caps at 100.
- **Living terminal economic value** includes carried inventory, owned
  completed productive assets, stored inventory, treasuries, upkeep reserves,
  owned ground items, open trade escrow, and still-owned credit
  advance/collateral escrow. Group-owned value is divided among members, and
  only living members' shares count.

The three-times-endowment target is mechanics-based and frozen in v2. It means
an excellent cohort must do more than preserve its starting supplies.

A geometric mean is used rather than hand-tuned weights. A model cannot erase a
collapse by leaving wealth on dead agents, or hide poor planning behind passive
survival.

### 3. Entrepreneurial agency

This separates empty ambition from realized enterprise:

```text
geometric mean(initiative score, realization score)
```

**Venture initiatives** are successful:

- trade offers;
- construction starts;
- credit-contract offers;
- access-fee policies.

The initiative component reaches 100 at 20 initiatives per 100 possible
agent-ticks, equivalent to one successful venture start every five living
opportunities.

**Realized venture value** combines common book-value units from:

- completed productive assets owned;
- accepted trades originated by the cohort;
- access fees collected by cohort-owned assets;
- fulfilled contract repayments received.

The realization component reaches 100 at 40 value per 100 possible
agent-ticks. Over a 40-tick trial, that is 16 realized value per starting agent,
twice the organic world's eight-value starting endowment.

The targets are fixed "excellent performance" anchors, not percentiles fitted
to whichever models happen to be in the leaderboard. The geometric mean means
offer spam with no completed exchange cannot earn a high score, while passive
wealth accumulation with no venture initiation also cannot.

## Quality and certification

A run is diagnostic-only if any required setting differs, the run stops early,
the population is mixed, the model-decision ledger has failures, or usage
coverage is incomplete.

Result status is assigned as follows:

| Status | Requirement | Interpretation |
|---|---|---|
| Provisional | One clean, complete seed-11 run | Complete usage-constrained benchmark with single-world uncertainty |
| Certified | One clean, complete run for each seed, 11 and 41 | Replicated benchmark; pool raw counts before scoring |
| Incomplete replication | A clean seed-41 run without seed 11, or a duplicate required seed | Cannot stand alone; may contribute after the missing seed is added |
| Diagnostic only | Early stop, decision/provider failure, protocol mismatch, mixed population, or incomplete usage | Descriptive evidence, never promoted by relabeling |

Resuming a quota-paused run from its completed-tick checkpoint is allowed, but
the complete audit remains authoritative. A prior model-decision failure does
not disappear when a run resumes. Such a completed run remains diagnostic.

At launch, the run records a SHA-256 fingerprint of the scoring code and the
behavior-defining world, rules, map, model, interface, and runner sources.
Aggregation rejects a different fingerprint even when the visible settings
match. Any behavior-changing revision therefore needs a new suite version
instead of silently joining the old leaderboard.

The aggregate artifact retains:

- pooled raw counts;
- per-component scores;
- seed and source paths;
- rejected runs and exact exclusion reasons;
- the complete frozen protocol and scoring targets.

Changing a formula, target, world, or harness requires a new suite ID. Existing
Participant v1 or v2 results must never be silently rescored under a changed
definition.

## Reporting standard

Human-facing analyses put the three primary benchmark scores first in a
visually distinct scorecard:

1. planning execution;
2. sustained competence;
3. entrepreneurial agency.

A supporting table follows in the style of the direct Opus comparison. It must
include invalid proposals as both a count and a percentage of submitted
actions, contention separately, action-point overruns, survival, economic and
entrepreneurial outcomes, decision/provider failures, and usage where
available. The result tier and seed coverage appear immediately above the
scorecard. A high-level score must never replace the failure-rate denominator
or the descriptive civilization analysis.

## What v2 does not score

Communication, gifts, trades, construction cooperation, and group creation are
retained as social diagnostics. They are not yet a social-ability score because
frequency alone cannot distinguish useful coordination from chatter.

Antisocial behavior is also not scored yet. Reliable measurement will require a
separately validated semantic annotation procedure with human-audited examples;
keyword counts or an uncalibrated LLM judge would make the benchmark look more
precise than it is.

Future suites can add social coordination, leadership, adaptation, deception,
or antisocial-behavior tasks without changing Participant v2.
