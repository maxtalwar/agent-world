# Run report: run

- Ticks: 5/5 — **stopped early: interrupted**
- Agents: 10 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 50 calls, $0, 12.1% cache hit
- Per call: 9348.7 input tokens (8219.7 uncached), 849.0 output tokens, 706.9 reasoning tokens; agent context chars static/dynamic 8653.0/2323.8
- Estimated LLM cost: unavailable — no USD rates for model(s): grok-4.5

## Model benchmarks (agent-world-participant-v7)

Trial status: **diagnostic only**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (grok-4.5) |
> |---|---:|
> | **Effective execution** | 47.6 |
> | **Sustained competence** | 58.2 |
> | **Entrepreneurial agency** | 0.0 |

### Supporting execution diagnostics

| Metric | cohort-1 (grok-4.5) |
|---|---:|
| Invalid proposals | 26 (33.3%) |
| Contention failures | 0 (0.0%) |
| Action-point overruns | 0 |
| Purposeful agent-ticks | 17 (34.0%) |

### Supporting economic diagnostics

| Metric | cohort-1 (grok-4.5) |
|---|---:|
| Living terminal value | 172.0 |
| Starting endowment | 135.0 |
| Net value created | 37.0 |
| Net value / 100 agent-ticks | 74.0 |
| Enterprise supply value | 0.0 |
|   of which net goods supplied | 0.0 |
|   of which net service income | 0.0 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 0.0 |
| Venture initiatives (diagnostic) | 0.0 |
| Economic productivity score | 370.0 |

Protocol flags: benchmark_code_fingerprint_mismatch, benchmark_protocol_not_declared, protocol_mismatch:final_tick, protocol_mismatch:global_max_workers, protocol_mismatch:provider_max_workers, protocol_mismatch:ticks, run_integrity_not_clean, run_not_completed.

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
- agent-1: alive, hp 95, wealth 12, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-10: alive, hp 95, wealth 8, inventory {'food': 1, 'water': 2, 'coin': 4}, groups []
- agent-2: alive, hp 95, wealth 10, inventory {'food': 2, 'water': 2, 'coin': 4}, groups []
- agent-3: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-4: alive, hp 95, wealth 12, inventory {'food': 3, 'water': 2, 'coin': 4}, groups []
- agent-5: alive, hp 95, wealth 10, inventory {'food': 2, 'water': 2, 'coin': 4}, groups []
- agent-6: alive, hp 95, wealth 12, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-7: alive, hp 95, wealth 9, inventory {'food': 1, 'water': 3, 'coin': 4}, groups []
- agent-8: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 95, wealth 12, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 2}, groups []

## Reliability
- Invalid proposals: 25 (19.2% of events)
- Contention failures: 0 (0.0% of events)
- LLM failure events: 20
- Decision quality: degraded | failure rate 40.0% | flags ['model_output_failures_present', 'ambiguous_boundary_failures_present']
