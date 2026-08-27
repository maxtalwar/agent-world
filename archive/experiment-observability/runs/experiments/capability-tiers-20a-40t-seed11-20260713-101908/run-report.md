# Run report: run

- Ticks: 40/40
- Agents: 16 living / 4 dead
- Action points/tick: 4 | seed: 11
- LLM: 774 calls, $0, 53.0% cache hit
- Per call: 9948.5 input tokens (4671.8 uncached), 408.3 output tokens; agent context chars static/dynamic 6493.0/3767.0
- Simulation plan credits: 257.035422 exact run-scoped credits (input 199.669338 + cached 15.90016 + output 41.465925)
- Codex plan [codex]: primary 4% to 5%, window reset/changed | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 160 calls, 0 gifts, 9 offers/1 accepts
- cohort-2: claude-sonnet-5 — 0/4 living, 134 calls, 0 gifts, 0 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 120 calls, 0 gifts, 1 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 120 calls, 0 gifts, 18 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 120 calls, 2 gifts, 1 offers/1 accepts
- cohort-6: fable — 3/3 living, 120 calls, 1 gifts, 15 offers/6 accepts

## Occupations
- generalist: 16/20 living, 30.2% proposed actions invalid, 44 offers/8 accepts, 3 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 3} | co-op builds: 0
- Ownership: {'agent-4': 1, 'agent-12': 1, 'agent-15': 1}

## Economy
- Gifts: 3 {'agent-12->agent-16': 2, 'agent-4->agent-14': 1}
- Gift flow: 5 units / 9 book value | subsistence/material units: 5/0 | group status: {'in_group': 0, 'out_group': 3, 'unknown': 0}
- Trades: 44 offered / 8 accepted / 30 expired | conversion: 18.2% | invalid accepts: 41
- Trade funnel: 43 offers observed by counterparties / 25 attempted / 22 reached settlement checks / 8 completed | expired without attempt: 15
- Construction contributions: 30 value | productive assets: 3
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 8 | dividend value: 4
- Food spoilage events: 42 | tile claims: 0 | access grants: 1

## Milestones (first tick)
- offer_trade: t1, accept_trade: t2, build: t8, craft: t11, death: t26, grant_access: t34, gift: t36

## Agents
- agent-1: alive, hp 95, wealth 22, inventory {'food': 2, 'coin': 4, 'fiber': 7}, groups []
- agent-10: alive, hp 84, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-11: DEAD, hp 0, wealth 24, inventory {'coin': 4, 'fiber': 10}, groups []
- agent-12: alive, hp 100, wealth 21, inventory {'food': 3, 'coin': 4, 'fiber': 4, 'wood': 1}, groups []
- agent-13: alive, hp 23, wealth 20, inventory {'coin': 4, 'ore': 1, 'stone': 1, 'fiber': 2}, groups []
- agent-14: alive, hp 100, wealth 9, inventory {'food': 3, 'wood': 1}, groups []
- agent-15: alive, hp 95, wealth 10, inventory {'food': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-16: alive, hp 36, wealth 14, inventory {'food': 3, 'coin': 4, 'fiber': 2}, groups []
- agent-17: alive, hp 100, wealth 27, inventory {'coin': 4, 'fiber': 4, 'wood': 1, 'tool': 1}, groups []
- agent-18: alive, hp 29, wealth 15, inventory {'water': 1, 'coin': 4, 'ore': 1, 'fiber': 1}, groups []
- agent-19: DEAD, hp 0, wealth 23, inventory {'coin': 4, 'fiber': 8, 'wood': 1}, groups []
- agent-2: alive, hp 77, wealth 10, inventory {'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-20: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-3: alive, hp 40, wealth 20, inventory {'coin': 4, 'stone': 1, 'ore': 1, 'fiber': 2}, groups []
- agent-4: alive, hp 100, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-5: alive, hp 25, wealth 17, inventory {'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-6: alive, hp 49, wealth 20, inventory {'food': 1, 'coin': 2, 'fiber': 8}, groups []
- agent-7: DEAD, hp 0, wealth 21, inventory {'coin': 4, 'fiber': 4, 'wood': 3}, groups []
- agent-8: alive, hp 16, wealth 20, inventory {'coin': 4, 'ore': 2}, groups []
- agent-9: alive, hp 91, wealth 9, inventory {'food': 2, 'water': 1, 'fiber': 2}, groups []

## Reliability
- Invalid actions: 770 / 2547 proposed (30.2% of proposed actions) | 0.995 per decision
- Invalid categories: {'resource_or_access_unavailable': 553, 'action_budget_or_energy': 85, 'trade_coordination_or_state': 50, 'movement_or_occupancy': 48, 'other': 23, 'target_or_carry_constraint': 11}
- Observation attribution: {'known_invalid_from_observation': 397, 'potential_same_tick_or_plan_state_change': 215, 'known_constraint_or_plan_sequence': 85, 'not_classified': 44, 'coordination_state_uncertain': 29}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
