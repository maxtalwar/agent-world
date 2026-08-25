# Run report: run

- Ticks: 5/5
- Agents: 40 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 200 calls, $0, 70.7% cache hit
- Per call: 12126.9 input tokens (3549.6 uncached), 487.4 output tokens, 403.2 reasoning tokens; agent context chars static/dynamic 8653.0/2501.3
- Estimated LLM cost: $0.293264 at API list rates (input 0.141984 + cached 0.034309 + cache write 0.0 + output 0.116971) — token-derived estimate, not a provider charge
- Simulation plan credits: 36.65799 exact run-scoped credits (input 17.74795 + cached 4.28864 + output 14.6214)
- Codex plan [codex]: primary 11% to 11%, delta +0pp | credits 2655.3620750000 to 2655.3620750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed | secondary 0% to 0%, window reset/changed

## Model benchmarks (agent-world-participant-v7)

Trial status: **diagnostic only**.

> **Primary benchmark scorecard**
>
> | Benchmark | cohort-1 (gpt-5.6-luna) |
> |---|---:|
> | **Effective execution** | 93.0 |
> | **Sustained competence** | 79.6 |
> | **Entrepreneurial agency** | 0.0 |

### Supporting execution diagnostics

| Metric | cohort-1 (gpt-5.6-luna) |
|---|---:|
| Invalid proposals | 43 (6.8%) |
| Contention failures | 22 (3.5%) |
| Action-point overruns | 1 |
| Purposeful agent-ticks | 186 (93.0%) |

### Supporting economic diagnostics

| Metric | cohort-1 (gpt-5.6-luna) |
|---|---:|
| Living terminal value | 880.0 |
| Starting endowment | 540.0 |
| Net value created | 340.0 |
| Net value / 100 agent-ticks | 170.0 |
| Enterprise supply value | 0.0 |
|   of which net goods supplied | 0.0 |
|   of which net service income | 0.0 |
|   of which own capital output | n/a |
| Enterprise supply / 100 agent-ticks | 0.0 |
| Venture initiatives (diagnostic) | 4.0 |
| Economic productivity score | 850.0 |

Protocol flags: benchmark_code_fingerprint_mismatch, benchmark_protocol_not_declared, protocol_mismatch:agents, protocol_mismatch:cohort_size, protocol_mismatch:final_tick, protocol_mismatch:global_max_workers, protocol_mismatch:provider_max_workers, protocol_mismatch:ticks.

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 2 {'agent-22->agent-17': 1, 'agent-26->agent-36': 1}
- Gift flow: 2 units / 4 book value | subsistence/material units: 2/0 | group status: {'in_group': 0, 'out_group': 2, 'unknown': 0}
- Trades: 4 offered / 0 accepted / 1 expired | conversion: 0.0% | invalid accepts: 2
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t1, gift: t3

## Agents
- agent-1: alive, hp 100, wealth 14, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-10: alive, hp 100, wealth 18, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-11: alive, hp 100, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-12: alive, hp 100, wealth 17, inventory {'food': 5, 'water': 1, 'coin': 4, 'fiber': 1}, groups []
- agent-13: alive, hp 100, wealth 13, inventory {'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-14: alive, hp 100, wealth 19, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 100, wealth 18, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-16: alive, hp 100, wealth 21, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-17: alive, hp 100, wealth 14, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 1}, groups []
- agent-18: alive, hp 100, wealth 22, inventory {'food': 3, 'coin': 4, 'fiber': 6}, groups []
- agent-19: alive, hp 100, wealth 12, inventory {'food': 1, 'water': 4, 'coin': 4, 'fiber': 1}, groups []
- agent-2: alive, hp 100, wealth 18, inventory {'water': 1, 'coin': 4, 'fiber': 2, 'wood': 3}, groups []
- agent-20: alive, hp 100, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-21: alive, hp 100, wealth 18, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-22: alive, hp 100, wealth 15, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 2}, groups []
- agent-23: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-24: alive, hp 100, wealth 21, inventory {'food': 4, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-25: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 3, 'coin': 4, 'fiber': 3}, groups []
- agent-26: alive, hp 100, wealth 17, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-27: alive, hp 100, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-28: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-29: alive, hp 100, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-3: alive, hp 100, wealth 10, inventory {'food': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-30: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 3, 'coin': 4, 'fiber': 3}, groups []
- agent-31: alive, hp 100, wealth 19, inventory {'water': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-32: alive, hp 100, wealth 16, inventory {'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-33: alive, hp 100, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-34: alive, hp 100, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-35: alive, hp 100, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-36: alive, hp 100, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-37: alive, hp 100, wealth 13, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 3}, groups []
- agent-38: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-39: alive, hp 100, wealth 20, inventory {'food': 3, 'coin': 4, 'fiber': 5}, groups []
- agent-4: alive, hp 100, wealth 13, inventory {'food': 1, 'water': 3, 'coin': 4, 'fiber': 2}, groups []
- agent-40: alive, hp 100, wealth 15, inventory {'food': 4, 'water': 1, 'coin': 4, 'fiber': 1}, groups []
- agent-5: alive, hp 100, wealth 13, inventory {'food': 2, 'water': 3, 'coin': 4, 'fiber': 1}, groups []
- agent-6: alive, hp 100, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-7: alive, hp 100, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-8: alive, hp 100, wealth 13, inventory {'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 100, wealth 18, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 4}, groups []

## Reliability
- Invalid proposals: 43 (6.3% of events)
- Contention failures: 22 (3.2% of events)
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
