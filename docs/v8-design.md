# Participant v8 design record

Finalized 2026-09-05. The registered
[participant-v8 recipe](../agent_world/recipes/participant-v8.json) and reusable
`outcome-production` scoring policy are implemented through launch, resume,
reporting, aggregation, finalization, and database projection.

The canonical specification is [model-benchmarks.md](model-benchmarks.md).

## Decisions

- Ten agents, 60 completed ticks, twelve-tick seasons, benchmark seeds 11 and 41.
- Medium effort, with provider settings and ceilings recorded; no silent fallback.
- No message board; retain explicit commerce-intent labels.
- Capability measures sustained original-population health independently of
  execution or economic outcomes. No inventory bonus.
- Execution measures complete-decision feasibility, with no activity bonus.
- The economic column is **Production**, replacing the proposed Enterprise
  label because it measures productive contribution rather than business sense.
- Equal useful production receives equal credit whether self-consumed, sold,
  bartered, or gifted. Transfers themselves add no production credit.
- Construction alone earns no bonus. Productive infrastructure earns its
  contribution through collected output; farm tending and harvest are not
  counted twice.
- Survival consumption does not erase production credit or create a threshold
  at positive net wealth. Production inputs are netted to avoid double-counting.
- The main table contains Model, Capability, Execution, Production, Cost/run,
  and Mean time/decision. Detailed results retain components and seed spread.

## Horizon

Sixty ticks covers spring, summer, autumn, winter, and a full second spring.
Capability's final twelve outcomes are completed ticks 49–60. This emphasizes
recovery after winter. The cutoff still cannot capture every future benefit
of retained assets; the score does not pretend to estimate that future value.

## Evidence and readiness

The old thirteen-world capability/execution review retains its original
50-tick horizons and recipe identities. It is diagnostic evidence, not a
v8 leaderboard. New production tests cover the user-specified counterexamples,
and local end-to-end tests exercise the 60-tick horizon, resume, aggregation,
finalization, and catalog projection without provider calls.

Use [the benchmark config](../configs/run-configs/v8-benchmark.example.json)
for authorized leaderboard runs, or [the experiment config](../configs/run-configs/v8-world.example.json)
for a single-seed study. No model-backed v8 runs were launched during implementation.
