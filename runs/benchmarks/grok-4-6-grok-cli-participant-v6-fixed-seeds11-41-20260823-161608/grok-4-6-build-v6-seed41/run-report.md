# Run report: run

- Ticks: 50/50
- Agents: 8 living / 2 dead
- Action points/tick: 4 | seed: 41
- LLM: 492 calls, $0, 39.4% cache hit
- Per call: 16836.6 input tokens (10210.0 uncached), 4007.2 output tokens, 3775.6 reasoning tokens; agent context chars static/dynamic 7435.0/5100.9
- Estimated LLM cost: $23.505992 at API list rates (input 10.046626 + cached 1.630144 + cache write 0.0 + output 11.829222) — token-derived estimate, not a provider charge

## Model benchmarks (agent-world-participant-v6)

Trial status: **diagnostic only**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (grok-4.6) |
> |---|---:|
> | **Effective execution** | 90.5 |
> | **Sustained competence** | 82.9 |
> | **Entrepreneurial agency** | 66.0 |

### Supporting execution diagnostics

| Metric | cohort-1 (grok-4.6) |
|---|---:|
| Invalid proposals | 182 (11.0%) |
| Contention failures | 10 (0.6%) |
| Action-point overruns | 9 |
| Purposeful agent-ticks | 453 (92.1%) |

### Supporting economic diagnostics

| Metric | cohort-1 (grok-4.6) |
|---|---:|
| Living terminal value | 470.5 |
| Starting endowment | 135.0 |
| Net value created | 335.5 |
| Net value / 100 agent-ticks | 67.1 |
| Enterprise supply value | 13.0 |
|   of which net goods supplied | 11.0 |
|   of which net service income | 2.0 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 2.6 |
| Venture initiatives (diagnostic) | 50.0 |
| Economic productivity score | 335.5 |

### Benchmark score trajectory

| Tick | Cohort | Role | Execution | Competence | Entrepreneurship | Living | Endpoint health | Living value |
|---:|---|---|---:|---:|---:|---:|---:|---:|
| 30 | cohort-1 | diagnostic checkpoint | 91.8 | 94.2 | 70.4 | 10 | 89.2 | 390.0 |
| 40 | cohort-1 | diagnostic checkpoint | 92.6 | 89.8 | 59.1 | 10 | 61.2 | 454.8 |
| 50 | cohort-1 | official endpoint | 90.5 | 82.9 | 60.8 | 8 | 40.2 | 470.5 |

Protocol flags: benchmark_code_fingerprint_mismatch.

## Society
- Groups: 0
- Structures complete: {'farm_plot': 9, 'storage': 3, 'shelter': 3} | co-op builds: 2
- Ownership: {'agent-6': 2, 'agent-4': 2, 'agent-2': 3, 'agent-7': 4, 'agent-9': 2, 'agent-5': 2, 'agent-1': 1}

## Economy
- Gifts: 3 {'agent-6->agent-1': 1, 'agent-9->agent-1': 1, 'agent-1->agent-9': 1}
- Gift flow: 4 units / 7 book value | subsistence/material units: 3/1 | group status: {'in_group': 0, 'out_group': 3, 'unknown': 0}
- Trades: 32 offered / 3 accepted / 16 expired | conversion: 9.4% | invalid accepts: 5
- Construction contributions: 282 value | productive assets: 16
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 40 | tile claims: 18 | access grants: 21

## Milestones (first tick)
- claim_tile: t0, grant_access: t3, build: t3, gift: t6, offer_trade: t9, craft: t9, build_started: t11, accept_trade: t16, death: t44

## Agents
- agent-1: alive, hp 65, wealth 14, inventory {'coin': 5, 'fiber': 3, 'water': 3}, groups []
- agent-10: DEAD, hp 0, wealth 8, inventory {'coin': 4, 'fiber': 2}, groups []
- agent-2: alive, hp 41, wealth 12, inventory {'coin': 2, 'fiber': 2, 'food': 3}, groups []
- agent-3: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []
- agent-4: alive, hp 45, wealth 12, inventory {'coin': 2, 'fiber': 1, 'food': 3, 'water': 2}, groups []
- agent-5: alive, hp 27, wealth 8, inventory {'food': 1, 'wood': 2}, groups []
- agent-6: alive, hp 53, wealth 13, inventory {'coin': 1, 'fiber': 1, 'food': 2, 'stone': 1, 'water': 2}, groups []
- agent-7: alive, hp 39, wealth 4, inventory {'coin': 2, 'water': 2}, groups []
- agent-8: alive, hp 62, wealth 17, inventory {'coin': 1, 'fiber': 4, 'food': 1, 'wood': 2}, groups []
- agent-9: alive, hp 70, wealth 15, inventory {'coin': 4, 'fiber': 4, 'water': 3}, groups []

## Reliability
- Invalid proposals: 182 (7.5% of events)
- Contention failures: 10 (0.4% of events)
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
