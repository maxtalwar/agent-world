# Run report: run

- Ticks: 5/5
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 100 calls, $0, 52.6% cache hit
- Per call: 9817.3 input tokens (4649.9 uncached), 301.1 output tokens; agent context chars static/dynamic 6598.0/3362.8
- Simulation plan credits: 33.404565 exact run-scoped credits (input 27.16415 + cached 1.86784 + output 4.372575)
- Codex plan [codex]: primary 11% to 11%, delta +0pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 20 calls, 1 gifts, 0 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 20 calls, 0 gifts, 0 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts

## Occupations
- generalist: 20/20 living, 15.2% proposed actions invalid, 0 offers/0 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 1 {'agent-6->agent-1': 1}
- Gift flow: 2 units / 3 book value | subsistence/material units: 2/0 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 0 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Trade funnel: 0 offers observed by counterparties / 0 attempted / 0 reached settlement checks / 0 completed | expired without attempt: 0
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- gift: t0

## Agents
- agent-1: alive, hp 100, wealth 18, inventory {'food': 3, 'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-10: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 3, 'coin': 4, 'fiber': 3}, groups []
- agent-11: alive, hp 100, wealth 19, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-12: alive, hp 100, wealth 16, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-13: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-14: alive, hp 100, wealth 21, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 100, wealth 21, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-16: alive, hp 100, wealth 21, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-17: alive, hp 100, wealth 18, inventory {'coin': 4, 'wood': 4, 'fiber': 1}, groups []
- agent-18: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-19: alive, hp 100, wealth 19, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-2: alive, hp 100, wealth 10, inventory {'food': 1, 'water': 4, 'coin': 4}, groups []
- agent-20: alive, hp 100, wealth 21, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-3: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-4: alive, hp 100, wealth 12, inventory {'water': 4, 'coin': 4, 'fiber': 2}, groups []
- agent-5: alive, hp 100, wealth 15, inventory {'water': 1, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-6: alive, hp 100, wealth 16, inventory {'food': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-7: alive, hp 100, wealth 16, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 1}, groups []
- agent-8: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'stone': 2}, groups []
- agent-9: alive, hp 100, wealth 12, inventory {'food': 1, 'water': 4, 'coin': 4, 'fiber': 1}, groups []

## Reliability
- Invalid actions: 50 / 328 proposed (15.2% of proposed actions) | 0.5 per decision
- Invalid categories: {'resource_or_access_unavailable': 38, 'target_or_carry_constraint': 7, 'action_budget_or_energy': 4, 'trade_coordination_or_state': 1}
- Observation attribution: {'known_invalid_from_observation': 25, 'potential_same_tick_or_plan_state_change': 14, 'not_classified': 7, 'known_constraint_or_plan_sequence': 4}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
