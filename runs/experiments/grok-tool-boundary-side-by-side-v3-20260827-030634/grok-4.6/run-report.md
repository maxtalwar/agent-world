# Run report: run

- Ticks: 5/5
- Agents: 10 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 50 calls, $0, 3.4% cache hit
- Per call: 11912.7 input tokens (11513.3 uncached), 2684.2 output tokens, 2501.4 reasoning tokens; agent context chars static/dynamic 8653.0/2554.6
- Estimated LLM cost: $1.966578 at API list rates (input 1.151334 + cached 0.009984 + cache write 0.0 + output 0.80526) — token-derived estimate, not a provider charge

## Model benchmarks (agent-world-participant-v7)

Trial status: **diagnostic only**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (grok-4.6) |
> |---|---:|
> | **Effective execution** | 93.8 |
> | **Sustained competence** | 78.9 |
> | **Entrepreneurial agency** | 0.0 |

### Supporting execution diagnostics

| Metric | cohort-1 (grok-4.6) |
|---|---:|
| Invalid proposals | 10 (6.3%) |
| Contention failures | 1 (0.6%) |
| Action-point overruns | 0 |
| Purposeful agent-ticks | 47 (94.0%) |

### Supporting economic diagnostics

| Metric | cohort-1 (grok-4.6) |
|---|---:|
| Living terminal value | 212.0 |
| Starting endowment | 135.0 |
| Net value created | 77.0 |
| Net value / 100 agent-ticks | 154.0 |
| Enterprise supply value | 0.0 |
|   of which net goods supplied | 0.0 |
|   of which net service income | 0.0 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 0.0 |
| Venture initiatives (diagnostic) | 2.0 |
| Economic productivity score | 770.0 |

Protocol flags: benchmark_code_fingerprint_mismatch, benchmark_protocol_not_declared, protocol_mismatch:final_tick, protocol_mismatch:global_max_workers, protocol_mismatch:provider_max_workers, protocol_mismatch:ticks.

## Society
- Groups: 0
- Structures complete: {'farm_plot': 1} | co-op builds: 0
- Ownership: {'agent-6': 1}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 1 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Construction contributions: 10 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 9 | access grants: 1

## Milestones (first tick)
- claim_tile: t0, offer_trade: t3, build: t4, grant_access: t4

## Agents
- agent-1: alive, hp 100, wealth 18, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 4, 'wood': 1}, groups []
- agent-10: alive, hp 100, wealth 12, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-2: alive, hp 100, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 4, 'wood': 2, 'fiber': 2}, groups []
- agent-3: alive, hp 100, wealth 11, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 1}, groups []
- agent-4: alive, hp 100, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-5: alive, hp 100, wealth 18, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-6: alive, hp 100, wealth 7, inventory {'food': 1, 'water': 1, 'coin': 4}, groups []
- agent-7: alive, hp 100, wealth 19, inventory {'food': 1, 'coin': 4, 'fiber': 2, 'wood': 3}, groups []
- agent-8: alive, hp 100, wealth 9, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 1}, groups []
- agent-9: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 2, 'wood': 1}, groups []

## Reliability
- Invalid proposals: 10 (4.6% of events)
- Contention failures: 1 (0.5% of events)
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
