# Run report: run

- Ticks: 5/50 — **stopped early: interrupted**
- Agents: 10 living / 0 dead
- Action points/tick: 4 | seed: 41
- LLM: 50 calls, $0, 48.6% cache hit
- Per call: 10850.7 input tokens (5572.0 uncached), 488.8 output tokens, 353.0 reasoning tokens; agent context chars static/dynamic 8653.0/2307.4
- Estimated LLM cost: unavailable — no USD rates for model(s): grok-4.5

## Model benchmarks (agent-world-participant-v7)

Trial status: **diagnostic only**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (grok-4.5) |
> |---|---:|
> | **Effective execution** | 45.7 |
> | **Sustained competence** | 39.0 |
> | **Entrepreneurial agency** | 0.0 |

### Supporting execution diagnostics

| Metric | cohort-1 (grok-4.5) |
|---|---:|
| Invalid proposals | 17 (25.4%) |
| Contention failures | 0 (0.0%) |
| Action-point overruns | 0 |
| Purposeful agent-ticks | 14 (28.0%) |

### Supporting economic diagnostics

| Metric | cohort-1 (grok-4.5) |
|---|---:|
| Living terminal value | 171.0 |
| Starting endowment | 135.0 |
| Net value created | 36.0 |
| Net value / 100 agent-ticks | 7.2 |
| Enterprise supply value | 0.0 |
|   of which net goods supplied | 0.0 |
|   of which net service income | 0.0 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 0.0 |
| Venture initiatives (diagnostic) | 0.0 |
| Economic productivity score | 36.0 |

Protocol flags: protocol_mismatch:final_tick, run_integrity_not_clean, run_not_completed.

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 0 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- none

## Agents
- agent-1: alive, hp 95, wealth 12, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-10: alive, hp 95, wealth 12, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-2: alive, hp 95, wealth 8, inventory {'food': 1, 'water': 2, 'coin': 4}, groups []
- agent-3: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-4: alive, hp 95, wealth 10, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-5: alive, hp 95, wealth 10, inventory {'food': 2, 'water': 2, 'coin': 4}, groups []
- agent-6: alive, hp 95, wealth 12, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-7: alive, hp 95, wealth 8, inventory {'food': 1, 'water': 2, 'coin': 4}, groups []
- agent-8: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 95, wealth 12, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 1}, groups []

## Reliability
- Invalid proposals: 17 (14.2% of events)
- Contention failures: 0 (0.0% of events)
- LLM failure events: 13
- Decision quality: degraded | failure rate 26.0% | flags ['ambiguous_boundary_failures_present']
