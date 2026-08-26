# Run report: run

- Ticks: 50/50
- Agents: 7 living / 3 dead
- Action points/tick: 4 | seed: 11
- LLM: 485 calls, $0, 25.1% cache hit
- Per call: 20152.8 input tokens (15097.2 uncached), 2204.3 output tokens, 0.0 reasoning tokens; agent context chars static/dynamic 7435.0/4250.7

## Model benchmarks (agent-world-participant-v6)

Trial status: **diagnostic only**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (cursor-grok-4.5) |
> |---|---:|
> | **Effective execution** | 86.2 |
> | **Sustained competence** | 74.7 |
> | **Entrepreneurial agency** | 40.3 |

### Supporting execution diagnostics

| Metric | cohort-1 (cursor-grok-4.5) |
|---|---:|
| Invalid proposals | 186 (12.5%) |
| Contention failures | 6 (0.4%) |
| Action-point overruns | 6 |
| Purposeful agent-ticks | 412 (84.9%) |

### Supporting economic diagnostics

| Metric | cohort-1 (cursor-grok-4.5) |
|---|---:|
| Living terminal value | 315.8 |
| Starting endowment | 135.0 |
| Net value created | 180.8 |
| Net value / 100 agent-ticks | 36.1 |
| Enterprise supply value | 9.0 |
|   of which net goods supplied | 7.0 |
|   of which net service income | 2.0 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 1.8 |
| Venture initiatives (diagnostic) | 26.0 |
| Economic productivity score | 180.8 |

### Benchmark score trajectory

| Tick | Cohort | Role | Execution | Competence | Entrepreneurship | Living | Endpoint health | Living value |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 30 | cohort-1 | diagnostic checkpoint | 86.6 | 89.0 | 0.0 | 10 | 85.8 | 356.2 |
| 40 | cohort-1 | diagnostic checkpoint | 85.7 | 85.0 | 63.1 | 10 | 62.5 | 366.8 |
| 50 | cohort-1 | official endpoint | 86.2 | 74.7 | 50.3 | 7 | 39.6 | 315.8 |

Protocol flags: run_integrity_not_clean.

## Society
- Groups: 0
- Structures complete: {'farm_plot': 6, 'storage': 2, 'shelter': 1} | co-op builds: 1
- Ownership: {'agent-9': 2, 'agent-5': 1, 'agent-2': 2, 'agent-4': 1, 'agent-7': 1, 'agent-6': 2, 'agent-10': 1}

## Economy
- Gifts: 5 {'agent-7->agent-6': 1, 'agent-6->agent-7': 2, 'agent-1->agent-6': 1, 'agent-6->agent-2': 1}
- Gift flow: 5 units / 9 book value | subsistence/material units: 4/1 | group status: {'in_group': 0, 'out_group': 5, 'unknown': 0}
- Trades: 16 offered / 1 accepted / 12 expired | conversion: 6.2% | invalid accepts: 4
- Construction contributions: 160 value | productive assets: 10
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 37 | tile claims: 1 | access grants: 7

## Milestones (first tick)
- claim_tile: t1, build_started: t2, build: t4, craft: t5, offer_trade: t14, grant_access: t29, gift: t32, accept_trade: t39, death: t43

## Agents
- agent-1: alive, hp 96, wealth 20, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-10: DEAD, hp 0, wealth 16, inventory {'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-2: alive, hp 63, wealth 16, inventory {'food': 1, 'water': 1, 'coin': 4, 'wood': 1, 'fiber': 3}, groups []
- agent-3: alive, hp 15, wealth 14, inventory {'water': 2, 'coin': 4, 'stone': 1, 'fiber': 2}, groups []
- agent-4: DEAD, hp 0, wealth 9, inventory {'fiber': 3, 'wood': 1}, groups []
- agent-5: alive, hp 6, wealth 18, inventory {'coin': 2, 'fiber': 3, 'wood': 2, 'stone': 1}, groups []
- agent-6: alive, hp 93, wealth 18, inventory {'food': 6, 'water': 2, 'coin': 4}, groups []
- agent-7: alive, hp 73, wealth 24, inventory {'food': 6, 'coin': 4, 'fiber': 4}, groups []
- agent-8: DEAD, hp 0, wealth 20, inventory {'food': 1, 'coin': 4, 'stone': 1, 'fiber': 2, 'wood': 2}, groups []
- agent-9: alive, hp 50, wealth 12, inventory {'coin': 4, 'stone': 2}, groups []

## Reliability
- Invalid proposals: 178 (9.1% of events)
- Contention failures: 6 (0.3% of events)
- LLM failure events: 43
- Decision quality: degraded | failure rate 8.87% | flags ['model_output_failures_present', 'ambiguous_boundary_failures_present']
