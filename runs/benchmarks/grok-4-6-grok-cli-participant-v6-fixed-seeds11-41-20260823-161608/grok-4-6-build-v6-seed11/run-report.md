# Run report: run

- Ticks: 50/50
- Agents: 9 living / 1 dead
- Action points/tick: 4 | seed: 11
- LLM: 500 calls, $4.2137, 31.1% cache hit
- Per call: 16901.8 input tokens (11639.4 uncached), 3943.8 output tokens, 3711.0 reasoning tokens; agent context chars static/dynamic 7435.0/5312.8
- Estimated LLM cost: $24.78637 at API list rates (input 11.63944 + cached 1.315584 + cache write 0.0 + output 11.831346) — token-derived estimate, not a provider charge

## Model benchmarks (agent-world-participant-v6)

Trial status: **eligible replication**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (grok-4.6) |
> |---|---:|
> | **Effective execution** | 92.4 |
> | **Sustained competence** | 81.9 |
> | **Entrepreneurial agency** | 108.7 |

### Supporting execution diagnostics

| Metric | cohort-1 (grok-4.6) |
|---|---:|
| Invalid proposals | 122 (7.4%) |
| Contention failures | 8 (0.5%) |
| Action-point overruns | 5 |
| Purposeful agent-ticks | 461 (92.2%) |

### Supporting economic diagnostics

| Metric | cohort-1 (grok-4.6) |
|---|---:|
| Living terminal value | 406.5 |
| Starting endowment | 135.0 |
| Net value created | 271.5 |
| Net value / 100 agent-ticks | 54.3 |
| Enterprise supply value | 43.5 |
|   of which net goods supplied | 21.0 |
|   of which net service income | 22.5 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 8.7 |
| Venture initiatives (diagnostic) | 58.0 |
| Economic productivity score | 271.5 |

### Benchmark score trajectory

| Tick | Cohort | Role | Execution | Competence | Entrepreneurship | Living | Endpoint health | Living value |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 30 | cohort-1 | diagnostic checkpoint | 93.0 | 94.3 | 108.5 | 10 | 81.6 | 437.5 |
| 40 | cohort-1 | diagnostic checkpoint | 93.0 | 90.5 | 88.1 | 10 | 63.3 | 445.5 |
| 50 | cohort-1 | official endpoint | 92.4 | 81.9 | 71.8 | 9 | 35.3 | 406.5 |

## Society
- Groups: 0
- Structures complete: {'farm_plot': 8, 'storage': 5, 'shelter': 2} | co-op builds: 2
- Ownership: {'agent-2': 3, 'agent-5': 3, 'agent-7': 2, 'agent-4': 3, 'agent-1': 3, 'agent-6': 1, 'agent-8': 1, 'agent-9': 1, 'agent-10': 1, 'agent-3': 1}

## Economy
- Gifts: 11 {'agent-10->agent-5': 1, 'agent-5->agent-10': 1, 'agent-5->agent-8': 1, 'agent-7->agent-1': 1, 'agent-3->agent-8': 2, 'agent-10->agent-6': 2, 'agent-9->agent-6': 2, 'agent-6->agent-1': 1}
- Gift flow: 15 units / 26 book value | subsistence/material units: 8/7 | group status: {'in_group': 0, 'out_group': 11, 'unknown': 0}
- Trades: 39 offered / 4 accepted / 15 expired | conversion: 10.3% | invalid accepts: 5
- Construction contributions: 333 value | productive assets: 19
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 34 | tile claims: 15 | access grants: 24

## Milestones (first tick)
- claim_tile: t0, build: t3, grant_access: t4, gift: t6, offer_trade: t10, craft: t12, accept_trade: t14, build_started: t28, death: t49

## Agents
- agent-1: alive, hp 52, wealth 6, inventory {'coin': 4, 'fiber': 1}, groups []
- agent-10: alive, hp 56, wealth 4, inventory {'coin': 2, 'food': 1}, groups []
- agent-2: alive, hp 48, wealth 16, inventory {'coin': 4, 'fiber': 5, 'water': 2}, groups []
- agent-3: alive, hp 40, wealth 10, inventory {'coin': 2, 'fiber': 2, 'food': 1, 'water': 2}, groups []
- agent-4: alive, hp 55, wealth 13, inventory {'coin': 4, 'food': 4, 'water': 1}, groups []
- agent-5: alive, hp 9, wealth 4, inventory {'coin': 4}, groups []
- agent-6: DEAD, hp 0, wealth 6, inventory {'wood': 2}, groups []
- agent-7: alive, hp 22, wealth 13, inventory {'coin': 2, 'fiber': 4, 'wood': 1}, groups []
- agent-8: alive, hp 11, wealth 8, inventory {'fiber': 2, 'food': 1, 'water': 2}, groups []
- agent-9: alive, hp 60, wealth 3, inventory {'fiber': 1, 'water': 1}, groups []

## Reliability
- Invalid proposals: 122 (5.0% of events)
- Contention failures: 8 (0.3% of events)
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
