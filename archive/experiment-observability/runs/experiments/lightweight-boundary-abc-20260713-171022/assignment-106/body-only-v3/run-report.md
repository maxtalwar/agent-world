# Run report: run

- Ticks: 5/5
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 100 calls, $0, 65.2% cache hit
- Per call: 9440.8 input tokens (3285.1 uncached), 332.6 output tokens; agent context chars static/dynamic 6561.0/2502.3
- Simulation plan credits: 25.057312 exact run-scoped credits (input 17.092062 + cached 2.728 + output 5.23725)
- Codex plan [codex]: primary 16% to 16%, delta +0pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 20 calls, 0 gifts, 0 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 20 calls, 0 gifts, 0 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 15 calls, 0 gifts, 1 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts

## Occupations
- generalist: 20/20 living, 20.7% proposed actions invalid, 1 offers/0 accepts, 1 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {'agent-7': 1}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 1 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Trade funnel: 1 offers observed by counterparties / 0 attempted / 0 reached settlement checks / 0 completed | expired without attempt: 0
- Construction contributions: 4 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t2, build_started: t3

## Agents
- agent-1: alive, hp 100, wealth 18, inventory {'food': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-10: alive, hp 100, wealth 18, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-11: alive, hp 100, wealth 17, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 2, 'stone': 1}, groups []
- agent-12: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-13: alive, hp 100, wealth 19, inventory {'food': 1, 'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-14: alive, hp 100, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 100, wealth 18, inventory {'food': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-16: alive, hp 100, wealth 17, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-17: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'wood': 2, 'fiber': 1}, groups []
- agent-18: alive, hp 100, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-19: alive, hp 100, wealth 20, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 5, 'wood': 1}, groups []
- agent-2: alive, hp 100, wealth 16, inventory {'food': 3, 'water': 1, 'coin': 4, 'wood': 1, 'fiber': 1}, groups []
- agent-20: alive, hp 100, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-3: alive, hp 95, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-4: alive, hp 100, wealth 12, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-5: alive, hp 100, wealth 21, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-6: alive, hp 100, wealth 11, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 2}, groups []
- agent-7: alive, hp 100, wealth 13, inventory {'food': 2, 'water': 2, 'coin': 4, 'wood': 1}, groups []
- agent-8: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 100, wealth 14, inventory {'water': 1, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []

## Reliability
- Invalid actions: 67 / 324 proposed (20.7% of proposed actions) | 0.67 per decision
- Invalid categories: {'resource_or_access_unavailable': 44, 'action_budget_or_energy': 12, 'target_or_carry_constraint': 9, 'movement_or_occupancy': 2}
- Observation attribution: {'known_invalid_from_observation': 29, 'potential_same_tick_or_plan_state_change': 17, 'known_constraint_or_plan_sequence': 12, 'not_classified': 9}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
