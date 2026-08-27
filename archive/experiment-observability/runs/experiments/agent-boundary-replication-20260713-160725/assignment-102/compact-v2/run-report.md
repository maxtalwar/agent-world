# Run report: run

- Ticks: 5/5
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 100 calls, $0, 54.3% cache hit
- Per call: 9361.5 input tokens (4280.8 uncached), 320.1 output tokens; agent context chars static/dynamic 6493.0/2505.7
- Simulation plan credits: 33.22479 exact run-scoped credits (input 26.66235 + cached 1.82784 + output 4.7346)
- Codex plan [codex]: primary 12% to 12%, delta +0pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 20 calls, 0 gifts, 1 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 20 calls, 0 gifts, 3 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts

## Occupations
- generalist: 20/20 living, 22.8% proposed actions invalid, 4 offers/0 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 4 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Trade funnel: 2 offers observed by counterparties / 0 attempted / 0 reached settlement checks / 0 completed | expired without attempt: 0
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t3

## Agents
- agent-1: alive, hp 100, wealth 16, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 1, 'wood': 1}, groups []
- agent-10: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-11: alive, hp 100, wealth 20, inventory {'food': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-12: alive, hp 100, wealth 14, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 1, 'wood': 1}, groups []
- agent-13: alive, hp 95, wealth 14, inventory {'food': 1, 'water': 2, 'coin': 2, 'ore': 1}, groups []
- agent-14: alive, hp 100, wealth 17, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-15: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-16: alive, hp 100, wealth 16, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-17: alive, hp 100, wealth 18, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-18: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-19: alive, hp 100, wealth 19, inventory {'food': 2, 'coin': 4, 'wood': 1, 'fiber': 4}, groups []
- agent-2: alive, hp 100, wealth 9, inventory {'food': 1, 'water': 3, 'coin': 4}, groups []
- agent-20: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-3: alive, hp 100, wealth 20, inventory {'coin': 4, 'stone': 2, 'ore': 1}, groups []
- agent-4: alive, hp 100, wealth 18, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-5: alive, hp 100, wealth 13, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 3}, groups []
- agent-6: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-7: alive, hp 100, wealth 18, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 1}, groups []
- agent-8: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-9: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 4}, groups []

## Reliability
- Invalid actions: 73 / 320 proposed (22.8% of proposed actions) | 0.73 per decision
- Invalid categories: {'resource_or_access_unavailable': 51, 'action_budget_or_energy': 14, 'target_or_carry_constraint': 7, 'movement_or_occupancy': 1}
- Observation attribution: {'known_invalid_from_observation': 29, 'potential_same_tick_or_plan_state_change': 23, 'known_constraint_or_plan_sequence': 14, 'not_classified': 7}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
