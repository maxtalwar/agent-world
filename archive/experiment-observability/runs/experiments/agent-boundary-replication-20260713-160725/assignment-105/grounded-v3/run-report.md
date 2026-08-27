# Run report: run

- Ticks: 5/5
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 100 calls, $0, 67.5% cache hit
- Per call: 9638.2 input tokens (3129.2 uncached), 295.8 output tokens; agent context chars static/dynamic 6598.0/3312.6
- Simulation plan credits: 22.117875 exact run-scoped credits (input 14.94245 + cached 3.0256 + output 4.149825)
- Codex plan [codex]: primary 14% to 14%, window reset/changed | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 20 calls, 1 gifts, 2 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 20 calls, 0 gifts, 0 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts

## Occupations
- generalist: 20/20 living, 16.5% proposed actions invalid, 2 offers/0 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 1 {'agent-8->agent-3': 1}
- Gift flow: 1 units / 1 book value | subsistence/material units: 1/0 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 2 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Trade funnel: 1 offers observed by counterparties / 0 attempted / 0 reached settlement checks / 0 completed | expired without attempt: 0
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- gift: t0, offer_trade: t3, craft: t4

## Agents
- agent-1: alive, hp 100, wealth 21, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 1, 'tool': 1}, groups []
- agent-10: alive, hp 100, wealth 24, inventory {'food': 2, 'coin': 4, 'fiber': 8}, groups []
- agent-11: alive, hp 100, wealth 21, inventory {'food': 5, 'water': 1, 'coin': 4, 'fiber': 3}, groups []
- agent-12: alive, hp 100, wealth 13, inventory {'water': 1, 'coin': 4, 'fiber': 1, 'wood': 2}, groups []
- agent-13: alive, hp 100, wealth 13, inventory {'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-14: alive, hp 100, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 100, wealth 13, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 2}, groups []
- agent-16: alive, hp 95, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-17: alive, hp 100, wealth 11, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 1}, groups []
- agent-18: alive, hp 100, wealth 21, inventory {'water': 1, 'coin': 4, 'ore': 2}, groups []
- agent-19: alive, hp 100, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-2: alive, hp 100, wealth 11, inventory {'food': 2, 'water': 3, 'coin': 4}, groups []
- agent-20: alive, hp 100, wealth 11, inventory {'water': 1, 'coin': 4, 'fiber': 3}, groups []
- agent-3: alive, hp 100, wealth 13, inventory {'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-4: alive, hp 100, wealth 16, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-5: alive, hp 100, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-6: alive, hp 100, wealth 21, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-7: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 1, 'wood': 2}, groups []
- agent-8: alive, hp 100, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 100, wealth 12, inventory {'water': 4, 'coin': 4, 'fiber': 2}, groups []

## Reliability
- Invalid actions: 52 / 315 proposed (16.5% of proposed actions) | 0.52 per decision
- Invalid categories: {'resource_or_access_unavailable': 45, 'target_or_carry_constraint': 3, 'action_budget_or_energy': 2, 'other': 1, 'movement_or_occupancy': 1}
- Observation attribution: {'potential_same_tick_or_plan_state_change': 24, 'known_invalid_from_observation': 22, 'not_classified': 4, 'known_constraint_or_plan_sequence': 2}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
