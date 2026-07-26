# Agent World model benchmarks

Agent World Participant v3 is the current standardized model benchmark suite.
It turns deterministic run telemetry into three repeatable scores while keeping
the raw evidence and formulas visible.

The suite distinguishes:

- **Diagnostic scores:** useful measurements from any run, including mixed
  civilizations, stopped runs, degraded runs, and older harnesses.
- **Provisional benchmark results:** one integrity-clean, complete 50-tick run on the
  predeclared seed 11 that exactly follows participant-v3.
- **Replicated certified benchmark results:** pooled results from integrity-clean,
  complete 50-tick runs on both required seeds, 11 and 41.

This prevents an interesting exploratory run from being presented as directly
comparable to a controlled benchmark.

## Recorded attempts

- [GPT-5.4, 2026-07-25](gpt-5-4-benchmark.md): historical provisional
  Participant v2
  benchmark from a clean, complete seed-11 run; planning 86.54, sustained
  competence 78.45, and entrepreneurial agency 22.17.
- [GPT-5.3-Codex-Spark, 2026-07-24](gpt-5-3-codex-spark-benchmark.md):
  diagnostic-only; both runs exhausted the dedicated weekly quota before tick
  40 and each contained one model-decision failure. That attempt also exposed
  Participant v1 competence inflation; its corrected v2 diagnostic is 51.03,
  not 82.23.
- [GPT-5.3-Codex-Spark Participant v3, 2026-07-26](gpt-5-3-codex-spark-v3-benchmark.md):
  provisional seed-11 revision-2 result; planning 66.64, sustained competence
  32.68, and entrepreneurial agency 2.12. Two malformed model outputs are
  scored as model failures rather than mistaken for harness corruption.

Participant v1 is retired. It counted dead agents' inventories as material
success, measured survival only over ticks that happened to run, and lacked an
endpoint-health check. Historical v1 reports remain historical artifacts and
must not be silently mixed with later results.

Participant v2 remains a valid historical 40-tick suite. Participant v3 keeps
the same trial settings and core score construction, extends the official
endpoint to tick 50, and records diagnostic score trajectories at ticks 30, 40,
and 50. Existing v2 results are not converted or invalidated; models need fresh
v3 runs to enter the new leaderboard.

Participant v3 scoring revisions are recorded in every report:

- **Revision 2** made one classification correction: malformed structured
  output produced by the target model is a scored planning failure, not a
  reason to discard the trial. This does not repair the action or remove its
  consequences. The engine still executes the existing fallback wait, and the
  failure occupies one submitted-action slot.
- **Revision 3** removes the 100-point ceiling from entrepreneurial agency.
  Its fixed targets still define 100, but models that outperform them retain
  that information in their component and composite scores. Planning and
  sustained competence remain bounded at 100.

Historical revision-2 reports are not overwritten. Supplying one to the
benchmark aggregation command explicitly applies revision 3 to its preserved
raw counts and labels the source and output scoring revisions in the new
leaderboard artifact.

## Standard and usage-constrained trials

Every benchmark run uses the same pure-model 50-tick trial:

| Setting | Required value |
|---|---|
| Seeds | 11 and 41 |
| Population | 10 copies of one model |
| Horizon | 50 ticks |
| Diagnostic score checkpoints | ticks 30 and 40 |
| Official score endpoint | tick 50 |
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
  --benchmark-protocol participant-v3 \
  --brain codex --model gpt-5.6-luna \
  --seed 11 \
  --out runs/benchmarks/luna-v3/seed-11/run.jsonl \
  --snapshot runs/benchmarks/luna-v3/seed-11/run-snapshot.json \
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
  runs/benchmarks/luna-v3/seed-11/run-report.json \
  runs/benchmarks/luna-v3/seed-41/run-report.json \
  --out runs/benchmarks/luna-v3/leaderboard
```

Aggregation pools the raw numerators and denominators before scoring. It does
not average the two run scores. Passing only the clean seed-11 report emits a
provisional result; passing both required seeds emits a replicated certified
result.

The horizon remains 50 ticks in both tiers. Shortening a constrained model to
30 or 40 ticks is not allowed: historical 50-tick runs show that survival
collapses and civilization milestones often occur after tick 40. If even one
50-tick run is unaffordable, the available evidence remains diagnostic.

Each v3 run records cumulative diagnostic score snapshots at ticks 30 and 40,
plus the designated tick-50 endpoint. These trajectories show whether planning,
survival, and enterprise are improving, stable, or collapsing. They are not
three independent trials and must not be averaged; only the tick-50 score can
be provisional or certified. Each checkpoint is normalized to its elapsed
prefix horizon, so a healthy tick-30 population is not mechanically penalized
for the twenty future ticks that have not happened yet.

## The three scores

Higher is always better. Planning execution and sustained competence range
from 0 to 100. Entrepreneurial agency starts at zero but has no maximum: 100 is
its frozen excellent-performance reference point. Formulas, scale metadata,
and every component are stored in the machine-readable run report.

### 1. Planning execution

This measures how often the model proposes an action that is actually feasible.

```text
100 × (submitted actions - contention - invalid proposals)
    / (submitted actions - contention)
```

Same-tick contention is excluded. If two agents both make a valid attempt at
the final resource, losing resolution priority is not a planning mistake.

Action-point overruns are included among invalid proposals and also reported
separately. Each malformed model response adds one model-output invalid
proposal. Provider, quota, usage-ledger, or harness failures do not become
planning mistakes; they invalidate the benchmark trial through its integrity
checks.

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

The three-times-endowment target is mechanics-based and frozen in v3. It means
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
opportunities. It continues above 100 when a cohort starts ventures at a higher
rate.

**Realized venture value** combines common book-value units from:

- completed productive assets owned;
- accepted trades originated by the cohort;
- access fees collected by cohort-owned assets;
- fulfilled contract repayments received.

The realization component reaches 100 at 40 value per 100 possible
agent-ticks. Over a 50-tick trial, that is 20 realized value per starting agent,
2.5 times the organic world's eight-value starting endowment. It also continues
above 100 rather than discarding exceptional value creation.

The targets are fixed "excellent performance" anchors, not percentiles fitted
to whichever models happen to be in the leaderboard. The geometric mean means
offer spam with no completed exchange cannot earn a high score, while passive
wealth accumulation with no venture initiation also cannot.

For example, a cohort exactly at the initiative target and at twice the
realization target receives component scores of 100 and 200, producing an
entrepreneurial-agency score of 141.42. A cohort at twice both targets scores
200. Thus twice the realized value is always visible, although the composite
also deliberately accounts for whether the cohort initiated ventures.

## Quality and certification

A run is diagnostic-only if any required setting differs, the run stops early,
the population is mixed, an external provider/quota/harness failure occurs, or
usage coverage is incomplete. A malformed response generated by the target
model degrades descriptive quality but does not invalidate benchmark integrity:
it is part of the model's measured performance.

Result status is assigned as follows:

| Status | Requirement | Interpretation |
|---|---|---|
| Provisional | One integrity-clean, complete seed-11 run | Complete usage-constrained benchmark with single-world uncertainty |
| Certified | One integrity-clean, complete run for each seed, 11 and 41 | Replicated benchmark; pool raw counts before scoring |
| Incomplete replication | An integrity-clean seed-41 run without seed 11, or a duplicate required seed | Cannot stand alone; may contribute after the missing seed is added |
| Diagnostic only | Early stop, provider/quota/harness failure, protocol mismatch, mixed population, or incomplete usage | Descriptive evidence, never promoted by relabeling |

Resuming a quota-paused run from its completed-tick checkpoint is allowed, but
the complete audit remains authoritative. A provider or quota failure does not
disappear when a run resumes. A malformed model response also remains in the
audit, but is scored as a model failure rather than disqualifying the run.

For new Codex, Claude, Cursor, and direct OpenAI decisions, malformed model
output is preserved verbatim in the private usage ledger together with the
parser stage/detail and a SHA-256 hash. This diagnostic evidence is not
included in subsequent agent prompts. Historical runs can only retain the
error detail that was originally logged; missing raw responses cannot be
reconstructed.

At launch, the run records a SHA-256 fingerprint of the scoring code and the
behavior-defining provider brains, world, rules, map, model, interface, and
runner sources.
Aggregation rejects a different fingerprint even when the visible settings
match. Any behavior-changing revision therefore needs a new suite version
instead of silently joining the old leaderboard.

The aggregate artifact retains:

- pooled raw counts;
- per-component scores;
- seed and source paths;
- rejected runs and exact exclusion reasons;
- the complete frozen protocol and scoring targets.

Changing a formula, target, world, or harness requires a new suite ID. A narrow
telemetry/classification correction can use an explicit scoring revision and
source-fingerprint compatibility entry only when the event ledger contains all
inputs needed to recompute it and trial behavior was unchanged. The initial
Participant v3 Spark run is the sole revision-1 compatibility case; its event
ledger was not edited, and the migration is disclosed in its study record.

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
or the descriptive civilization analysis. Participant v3 reports also show the
tick-30/40/50 score trajectory, clearly distinguishing diagnostic checkpoints
from the designated final endpoint.

## What v3 does not score

Communication, gifts, trades, construction cooperation, and group creation are
retained as social diagnostics. They are not yet a social-ability score because
frequency alone cannot distinguish useful coordination from chatter.

Antisocial behavior is also not scored yet. Reliable measurement will require a
separately validated semantic annotation procedure with human-audited examples;
keyword counts or an uncalibrated LLM judge would make the benchmark look more
precise than it is.

Future suites can add social coordination, leadership, adaptation, deception,
or antisocial-behavior tasks without changing Participant v3.
