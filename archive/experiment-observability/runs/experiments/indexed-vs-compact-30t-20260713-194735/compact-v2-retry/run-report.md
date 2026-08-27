# Run report: run

- Ticks: 30/30
- Agents: 19 living / 1 dead
- Action points/tick: 4 | seed: 11
- LLM: 597 calls, $0, 65.1% cache hit
- Per call: 9885.0 input tokens (3446.2 uncached), 408.3 output tokens; agent context chars static/dynamic 6493.0/3701.7
- Simulation plan credits: 142.262972 exact run-scoped credits (input 91.723162 + cached 17.99296 + output 32.54685)
- Codex plan [codex]: primary 26% to 28%, delta +2pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 120 calls, 8 gifts, 1 offers/0 accepts
- cohort-2: claude-sonnet-5 — 3/4 living, 117 calls, 0 gifts, 4 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 90 calls, 2 gifts, 5 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 90 calls, 0 gifts, 10 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 90 calls, 1 gifts, 2 offers/0 accepts
- cohort-6: fable — 3/3 living, 90 calls, 1 gifts, 12 offers/3 accepts

## Occupations
- generalist: 19/20 living, 28.7% proposed actions invalid, 34 offers/3 accepts, 5 structures

## Society
- Groups: 0
- Structures complete: {'storage': 2, 'farm_plot': 3} | co-op builds: 1
- Ownership: {'agent-20': 1, 'agent-15': 2, 'agent-8': 1, 'agent-10': 1}

## Economy
- Gifts: 12 {'agent-10->agent-20': 1, 'agent-19->agent-14': 4, 'agent-14->agent-19': 4, 'agent-16->agent-17': 1, 'agent-16->agent-13': 1, 'agent-3->agent-5': 1}
- Gift flow: 15 units / 21 book value | subsistence/material units: 9/6 | group status: {'in_group': 0, 'out_group': 12, 'unknown': 0}
- Trades: 34 offered / 3 accepted / 25 expired | conversion: 8.8% | invalid accepts: 16
- Trade funnel: 32 offers observed by counterparties / 13 attempted / 8 reached settlement checks / 3 completed | expired without attempt: 16
- Construction contributions: 62 value | productive assets: 5
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 31 | tile claims: 0 | access grants: 3

## Milestones (first tick)
- offer_trade: t4, build_started: t4, build: t5, grant_access: t6, gift: t9, accept_trade: t10, death: t26

## Agents
- agent-1: alive, hp 67, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []
- agent-10: alive, hp 100, wealth 17, inventory {'water': 2, 'coin': 9, 'fiber': 3}, groups []
- agent-11: alive, hp 82, wealth 10, inventory {'water': 2, 'coin': 2, 'fiber': 3}, groups []
- agent-12: alive, hp 100, wealth 22, inventory {'food': 2, 'coin': 4, 'fiber': 7}, groups []
- agent-13: alive, hp 64, wealth 24, inventory {'food': 1, 'coin': 4, 'ore': 2, 'fiber': 1}, groups []
- agent-14: alive, hp 62, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-15: alive, hp 100, wealth 5, inventory {'water': 1, 'coin': 4}, groups []
- agent-16: alive, hp 74, wealth 20, inventory {'food': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-17: alive, hp 75, wealth 9, inventory {'water': 2, 'wood': 1, 'fiber': 2}, groups []
- agent-18: alive, hp 47, wealth 16, inventory {'fiber': 8}, groups []
- agent-19: alive, hp 77, wealth 21, inventory {'water': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-2: alive, hp 75, wealth 19, inventory {'food': 3, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-20: alive, hp 97, wealth 7, inventory {'food': 2, 'water': 2, 'coin': 1}, groups []
- agent-3: alive, hp 85, wealth 22, inventory {'coin': 4, 'ore': 1, 'fiber': 5}, groups []
- agent-4: alive, hp 100, wealth 19, inventory {'water': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-5: alive, hp 64, wealth 7, inventory {'water': 1, 'wood': 2}, groups []
- agent-6: alive, hp 63, wealth 23, inventory {'coin': 4, 'fiber': 8, 'wood': 1}, groups []
- agent-7: DEAD, hp 0, wealth 17, inventory {'fiber': 4, 'wood': 3}, groups []
- agent-8: alive, hp 95, wealth 15, inventory {'food': 3, 'water': 1, 'coin': 2, 'fiber': 3}, groups []
- agent-9: alive, hp 100, wealth 18, inventory {'coin': 4, 'fiber': 7}, groups []

## Reliability
- Invalid actions: 557 / 1941 proposed (28.7% of proposed actions) | 0.933 per decision
- Invalid categories: {'resource_or_access_unavailable': 414, 'action_budget_or_energy': 63, 'movement_or_occupancy': 34, 'trade_coordination_or_state': 24, 'target_or_carry_constraint': 16, 'other': 6}
- Observation attribution: {'known_invalid_from_observation': 325, 'potential_same_tick_or_plan_state_change': 124, 'known_constraint_or_plan_sequence': 63, 'not_classified': 26, 'coordination_state_uncertain': 19}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
