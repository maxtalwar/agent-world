# Run report: run

- Ticks: 30/30
- Agents: 19 living / 1 dead
- Action points/tick: 4 | seed: 11
- LLM: 595 calls, $0, 57.3% cache hit
- Per call: 9940.6 input tokens (4244.0 uncached), 393.0 output tokens; agent context chars static/dynamic 6592.0/3782.6
- Simulation plan credits: 179.70863 exact run-scoped credits (input 131.420775 + cached 14.24288 + output 34.044975)
- Codex plan [codex]: primary 21% to 24%, delta +3pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 120 calls, 1 gifts, 12 offers/0 accepts
- cohort-2: claude-sonnet-5 — 3/4 living, 115 calls, 0 gifts, 5 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 90 calls, 0 gifts, 1 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 90 calls, 0 gifts, 6 offers/1 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 90 calls, 3 gifts, 3 offers/0 accepts
- cohort-6: fable — 3/3 living, 90 calls, 2 gifts, 11 offers/3 accepts

## Occupations
- generalist: 19/20 living, 25.4% proposed actions invalid, 38 offers/4 accepts, 3 structures

## Society
- Groups: 0
- Structures complete: {'storage': 1, 'farm_plot': 2} | co-op builds: 0
- Ownership: {'agent-15': 1, 'agent-20': 1, 'agent-12': 1}

## Economy
- Gifts: 6 {'agent-2->agent-12': 1, 'agent-4->agent-11': 2, 'agent-20->agent-16': 1, 'agent-4->agent-1': 1, 'agent-10->agent-16': 1}
- Gift flow: 6 units / 9 book value | subsistence/material units: 6/0 | group status: {'in_group': 0, 'out_group': 6, 'unknown': 0}
- Trades: 38 offered / 4 accepted / 20 expired | conversion: 10.5% | invalid accepts: 22
- Trade funnel: 32 offers observed by counterparties / 13 attempted / 7 reached settlement checks / 4 completed | expired without attempt: 13
- Construction contributions: 36 value | productive assets: 3
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 31 | tile claims: 1 | access grants: 1

## Milestones (first tick)
- offer_trade: t2, gift: t3, accept_trade: t4, build_started: t14, build: t15, claim_tile: t19, grant_access: t20, death: t24

## Agents
- agent-1: alive, hp 7, wealth 18, inventory {'water': 1, 'coin': 4, 'fiber': 5, 'wood': 1}, groups []
- agent-10: alive, hp 95, wealth 13, inventory {'water': 3, 'coin': 4, 'fiber': 3}, groups []
- agent-11: alive, hp 74, wealth 2, inventory {'fiber': 1}, groups []
- agent-12: alive, hp 71, wealth 16, inventory {'food': 2, 'coin': 2, 'fiber': 5}, groups []
- agent-13: alive, hp 54, wealth 8, inventory {'water': 5, 'coin': 3}, groups []
- agent-14: alive, hp 47, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-15: alive, hp 100, wealth 8, inventory {'water': 4, 'coin': 4}, groups []
- agent-16: alive, hp 60, wealth 6, inventory {'coin': 4, 'fiber': 1}, groups []
- agent-17: alive, hp 77, wealth 13, inventory {'water': 3, 'coin': 5, 'wood': 1, 'fiber': 1}, groups []
- agent-18: alive, hp 41, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-19: alive, hp 100, wealth 17, inventory {'water': 1, 'fiber': 8}, groups []
- agent-2: alive, hp 62, wealth 23, inventory {'coin': 4, 'fiber': 8, 'wood': 1}, groups []
- agent-20: alive, hp 100, wealth 21, inventory {'food': 5, 'coin': 2, 'fiber': 3, 'wood': 1}, groups []
- agent-3: alive, hp 70, wealth 20, inventory {'coin': 4, 'stone': 1, 'ore': 1, 'fiber': 2}, groups []
- agent-4: alive, hp 100, wealth 16, inventory {'food': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-5: DEAD, hp 0, wealth 25, inventory {'coin': 6, 'fiber': 8, 'wood': 1}, groups []
- agent-6: alive, hp 27, wealth 18, inventory {'coin': 2, 'fiber': 5, 'wood': 2}, groups []
- agent-7: alive, hp 62, wealth 13, inventory {'fiber': 2, 'wood': 3}, groups []
- agent-8: alive, hp 95, wealth 21, inventory {'food': 3, 'water': 1, 'coin': 4, 'ore': 1, 'fiber': 1}, groups []
- agent-9: alive, hp 95, wealth 18, inventory {'water': 1, 'coin': 4, 'fiber': 5, 'wood': 1}, groups []

## Reliability
- Invalid actions: 489 / 1926 proposed (25.4% of proposed actions) | 0.822 per decision
- Invalid categories: {'resource_or_access_unavailable': 332, 'action_budget_or_energy': 66, 'movement_or_occupancy': 39, 'trade_coordination_or_state': 24, 'target_or_carry_constraint': 18, 'other': 10}
- Observation attribution: {'known_invalid_from_observation': 222, 'potential_same_tick_or_plan_state_change': 139, 'known_constraint_or_plan_sequence': 66, 'not_classified': 38, 'coordination_state_uncertain': 24}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
