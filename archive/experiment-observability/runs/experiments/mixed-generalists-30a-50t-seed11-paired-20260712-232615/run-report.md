# Run report: run

- Ticks: 50/50
- Agents: 15 living / 15 dead
- Action points/tick: 4 | seed: 11
- LLM: 1314 calls, $0, 59.2% cache hit
- Per call: 9640.0 input tokens (3935.4 uncached), 348.6 output tokens; agent context chars static/dynamic 6493.0/3770.4
- Simulation plan credits: 198.316268 exact run-scoped credits (input 143.276988 + cached 16.76768 + output 38.2716)
- Codex plan [codex]: primary 1% to 3%, delta +2pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: claude-sonnet-5 — 3/10 living, 417 calls, 0 gifts, 18 offers/2 accepts
- cohort-2: gpt-5.6-luna — 5/10 living, 446 calls, 5 gifts, 23 offers/1 accepts
- cohort-3: claude-opus-4-8 — 5/5 living, 250 calls, 0 gifts, 21 offers/0 accepts
- cohort-4: gpt-5.6-terra — 2/5 living, 201 calls, 0 gifts, 8 offers/0 accepts

## Occupations
- generalist: 15/30 living, 37.3% proposed actions invalid, 70 offers/3 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 5 {'agent-2->agent-13': 4, 'agent-26->agent-21': 1}
- Gift flow: 5 units / 6 book value | subsistence/material units: 5/0 | group status: {'in_group': 0, 'out_group': 5, 'unknown': 0}
- Trades: 70 offered / 3 accepted / 65 expired | conversion: 4.3% | invalid accepts: 37
- Trade funnel: 66 offers observed by counterparties / 22 attempted / 10 reached settlement checks / 3 completed | expired without attempt: 47
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 55 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t3, gift: t18, accept_trade: t23, death: t25

## Agents
- agent-1: alive, hp 12, wealth 8, inventory {'fiber': 4}, groups []
- agent-10: DEAD, hp 0, wealth 20, inventory {'fiber': 10}, groups []
- agent-11: DEAD, hp 0, wealth 7, inventory {'water': 3, 'fiber': 2}, groups []
- agent-12: alive, hp 90, wealth 22, inventory {'coin': 5, 'fiber': 4, 'wood': 3}, groups []
- agent-13: DEAD, hp 0, wealth 19, inventory {'food': 1, 'coin': 2, 'ore': 1, 'fiber': 2, 'wood': 1}, groups []
- agent-14: alive, hp 39, wealth 7, inventory {'water': 3, 'coin': 4}, groups []
- agent-15: alive, hp 14, wealth 5, inventory {'water': 1, 'fiber': 2}, groups []
- agent-16: alive, hp 77, wealth 13, inventory {'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-17: DEAD, hp 0, wealth 15, inventory {'fiber': 6, 'wood': 1}, groups []
- agent-18: alive, hp 38, wealth 10, inventory {'fiber': 5}, groups []
- agent-19: alive, hp 66, wealth 12, inventory {'water': 4, 'coin': 4, 'fiber': 2}, groups []
- agent-2: alive, hp 64, wealth 15, inventory {'food': 1, 'coin': 4, 'wood': 1, 'fiber': 3}, groups []
- agent-20: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'fiber': 1, 'wood': 2}, groups []
- agent-21: alive, hp 34, wealth 20, inventory {'food': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-22: alive, hp 10, wealth 10, inventory {'coin': 1, 'fiber': 3, 'wood': 1}, groups []
- agent-23: DEAD, hp 0, wealth 0, inventory {}, groups []
- agent-24: DEAD, hp 0, wealth 21, inventory {'coin': 4, 'wood': 3, 'fiber': 4}, groups []
- agent-25: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'stone': 2}, groups []
- agent-26: alive, hp 21, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-27: DEAD, hp 0, wealth 9, inventory {'coin': 1, 'fiber': 1, 'wood': 2}, groups []
- agent-28: DEAD, hp 0, wealth 8, inventory {'ore': 1}, groups []
- agent-29: alive, hp 19, wealth 12, inventory {'fiber': 6}, groups []
- agent-3: DEAD, hp 0, wealth 0, inventory {}, groups []
- agent-30: DEAD, hp 0, wealth 15, inventory {'coin': 4, 'fiber': 4, 'wood': 1}, groups []
- agent-4: alive, hp 19, wealth 17, inventory {'coin': 1, 'fiber': 8}, groups []
- agent-5: DEAD, hp 0, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-6: alive, hp 21, wealth 18, inventory {'coin': 4, 'fiber': 4, 'wood': 2}, groups []
- agent-7: alive, hp 25, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-8: DEAD, hp 0, wealth 0, inventory {}, groups []
- agent-9: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []

## Reliability
- Invalid actions: 1516 / 4066 proposed (37.3% of proposed actions) | 1.154 per decision
- Invalid categories: {'resource_or_access_unavailable': 1043, 'action_budget_or_energy': 254, 'movement_or_occupancy': 133, 'trade_coordination_or_state': 47, 'target_or_carry_constraint': 22, 'other': 17}
- Observation attribution: {'known_invalid_from_observation': 923, 'known_constraint_or_plan_sequence': 254, 'potential_same_tick_or_plan_state_change': 253, 'not_classified': 56, 'coordination_state_uncertain': 30}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
