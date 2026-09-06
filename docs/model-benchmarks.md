# Agent World model benchmarks

Revised Participant v8 is the current suite for new benchmark requests. Always select
`protocol: participant-v8-revised` explicitly in managed configs. Historical APIs that
omit a protocol retain their v7 default for compatibility; they do not select
the current leaderboard. V6 and v7 remain independently selectable.

The immutable recipe is
[participant-v8-revised.json](../agent_world/recipes/participant-v8-revised.json).
The [benchmark run protocol](benchmark-run-protocol.md) governs execution,
quota waits, provenance, and finalization. The recipe and its source commit
travel with every run and checkpoint.

## Frozen trial

| Setting | Participant v8 |
|---|---|
| Population | Ten generalists of one model |
| World | Frontier, organic economy, dispersed, neutral objective; 16×16 |
| Horizon | 60 completed ticks |
| Seasons | 12 ticks each: spring, summer, autumn, winter, spring |
| Required seeds | 11 and 41 |
| Optional extended seeds | 73, 101, 137; reported separately |
| Provisional evidence | Seed 11 only |
| Reasoning | Named medium; no silent fallback |
| Conversation | Fresh conversation, connector-v3, raw decisions |
| Observation history | full-v1 |
| Action limit | Four items in the Codex action contract |
| Claude thinking ceiling | 2,048 tokens, retained from the medium v6 envelope |
| Message board | Disabled; no seeded messages |
| Transfer intent | Explicit gift/payment/barter; deterministic accounting |
| Diagnostic checkpoints | 12, 24, 36, 48 |
| Official endpoint | 60 |

Worker concurrency is operational. Identical effort labels do not guarantee
identical computation; record exact provider/model/connector settings and
measured reasoning. A connector that cannot request medium can run a general
experiment with its supported setting, but cannot silently claim standard v8.
The current native-Max-only ZCode boundary remains such an exception.

## Scorecard

| Column | Definition |
|---|---|
| Capability | Mean health across the original population and all 60 completed ticks, equally weighted |
| Execution | Percentage of submitted non-contention actions/messages that succeed; unexecuted proposals earn no credit |
| Production | Gross productive value added, at frozen accounting values, per 100 original-population agent-ticks |
| Cost/run | Mean token-derived API-list equivalent per world, including recorded retries; distinct from subscription charges |
| Mean time/decision | Sum of recorded call/attempt durations per resolved decision, then pooled by decision count; excludes between-call quota waits |

Capability and execution range from 0 to 100. Production is unbounded and has
physical-accounting units; it is not a percentage or a calibrated measure of
commercial skill. Rank by capability, with the other axes shown separately.

Dead agents remain in the original-population denominators for capability and
production. Production is independent of health, execution, trade volume, and
positive terminal wealth growth. No composite combines the three scores.

[Revised Capability and Execution](v8-revised.md) define the current rules;
[per-action evidence](v8-action-review.md) documents execution telemetry. [Production scoring](v8-production.md) defines event accounting,
counterexamples, limitations, and validation. Missing evidence yields unavailable
scores and blocks certification; provider refusals are not fabricated behavior.

## Launch and certification

Copy [v8-benchmark.example.json](../configs/run-configs/v8-benchmark.example.json),
set a unique run ID and exact model/connector, and use the managed interface:

```bash
agent-world run --config YOUR_CONFIG.json --dry-run
agent-world run --config YOUR_CONFIG.json
```

The config requests both required seeds. General experiments can instead use
[v8-world.example.json](../configs/run-configs/v8-world.example.json), which
defaults to seed 11 and does not claim benchmark certification.

Certify only completed, clean, attributable evidence with full usage coverage.
Pool raw numerators and denominators across the required seeds before scoring;
report per-seed values and spread separately. Both seeds must share recipe
identity and source provenance. Model identity follows the existing accepted
requested-only/native-alias policies; unavailable independent echo is not a
new certification blocker.

## Historical suites

The [v6 leaderboard](model-leaderboard-v6.md),
[v7 leaderboard](model-leaderboard-v7.md), and
[historical v6/v7 definitions](model-benchmarks-v7.md) remain available.
Their formulas and evidence are unchanged. Historical 50-tick runs and offline
counterfactual scores are not v8 benchmark results.

Original participant-v8 and participant-v8-action-review remain selectable,
immutable historical recipes. Their results are not pooled with revised v8.
