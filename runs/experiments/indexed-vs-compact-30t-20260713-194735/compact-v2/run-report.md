# Run report: run

- Ticks: 30/30
- Agents: 18 living / 2 dead
- Action points/tick: 4 | seed: 11
- LLM: 594 calls, $0, 66.2% cache hit
- Per call: 9717.9 input tokens (3289.5 uncached), 385.7 output tokens; agent context chars static/dynamic 6493.0/3525.8
- Simulation plan credits: 133.74657 exact run-scoped credits (input 84.6903 + cached 18.07872 + output 30.97755)
- Codex plan [codex]: primary 24% to 26%, window reset/changed | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 3/4 living, 119 calls, 1 gifts, 5 offers/1 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 120 calls, 0 gifts, 1 offers/0 accepts
- cohort-3: gpt-5.6-terra — 2/3 living, 86 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 90 calls, 0 gifts, 3 offers/1 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 89 calls, 0 gifts, 8 offers/0 accepts
- cohort-6: fable — 3/3 living, 90 calls, 0 gifts, 14 offers/1 accepts

## Occupations
- generalist: 18/20 living, 29.5% proposed actions invalid, 31 offers/3 accepts, 1 structures

## Society
- Groups: 0
- Structures complete: {'storage': 1} | co-op builds: 0
- Ownership: {'agent-20': 1}

## Economy
- Gifts: 1 {'agent-2->agent-19': 1}
- Gift flow: 1 units / 1 book value | subsistence/material units: 1/0 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 31 offered / 3 accepted / 17 expired | conversion: 9.7% | invalid accepts: 16
- Trade funnel: 28 offers observed by counterparties / 14 attempted / 9 reached settlement checks / 3 completed | expired without attempt: 8
- Construction contributions: 16 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 25 | tile claims: 0 | access grants: 2

## Milestones (first tick)
- offer_trade: t1, build: t4, grant_access: t5, accept_trade: t6, craft: t16, death: t25, gift: t27

## Agents
- agent-1: alive, hp 85, wealth 21, inventory {'water': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-10: alive, hp 100, wealth 14, inventory {'water': 1, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-11: alive, hp 100, wealth 15, inventory {'water': 3, 'coin': 6, 'fiber': 3}, groups []
- agent-12: alive, hp 100, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []
- agent-13: DEAD, hp 0, wealth 9, inventory {'water': 5, 'coin': 4}, groups []
- agent-14: alive, hp 73, wealth 17, inventory {'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 19, wealth 10, inventory {'coin': 2, 'fiber': 1, 'wood': 2}, groups []
- agent-16: alive, hp 79, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-17: alive, hp 100, wealth 20, inventory {'coin': 4, 'wood': 2, 'fiber': 5}, groups []
- agent-18: DEAD, hp 0, wealth 24, inventory {'coin': 4, 'ore': 2, 'fiber': 2}, groups []
- agent-19: alive, hp 90, wealth 21, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-2: alive, hp 95, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []
- agent-20: alive, hp 100, wealth 14, inventory {'water': 1, 'coin': 2, 'fiber': 4, 'wood': 1}, groups []
- agent-3: alive, hp 71, wealth 16, inventory {'ore': 2}, groups []
- agent-4: alive, hp 45, wealth 12, inventory {'water': 2, 'coin': 2, 'fiber': 4}, groups []
- agent-5: alive, hp 42, wealth 10, inventory {'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-6: alive, hp 84, wealth 24, inventory {'coin': 4, 'fiber': 4, 'tool': 1}, groups []
- agent-7: alive, hp 2, wealth 16, inventory {'fiber': 2, 'wood': 4}, groups []
- agent-8: alive, hp 73, wealth 12, inventory {'water': 2, 'coin': 2, 'ore': 1}, groups []
- agent-9: alive, hp 90, wealth 9, inventory {'water': 3, 'coin': 4, 'fiber': 1}, groups []

## Reliability
- Invalid actions: 565 / 1916 proposed (29.5% of proposed actions) | 0.95 per decision
- Invalid categories: {'resource_or_access_unavailable': 421, 'action_budget_or_energy': 70, 'movement_or_occupancy': 29, 'trade_coordination_or_state': 21, 'other': 14, 'target_or_carry_constraint': 10}
- Observation attribution: {'known_invalid_from_observation': 316, 'potential_same_tick_or_plan_state_change': 138, 'known_constraint_or_plan_sequence': 70, 'not_classified': 31, 'coordination_state_uncertain': 10}
- LLM failure events: 1
- Decision quality: degraded | failure rate 0.17% | flags ['decision_failures_present', 'missing_usage_records']
