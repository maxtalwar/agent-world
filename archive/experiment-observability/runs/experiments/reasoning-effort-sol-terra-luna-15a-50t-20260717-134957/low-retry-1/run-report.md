# Run report: run

- Ticks: 50/50
- Agents: 12 living / 3 dead
- Action points/tick: 4 | seed: 11
- LLM: 711 calls, $0, 69.5% cache hit
- Per call: 13743.5 input tokens (4194.5 uncached), 299.6 output tokens; agent context chars static/dynamic 6493.0/3064.6
- Simulation plan credits: 351.568658 exact run-scoped credits (input 211.406112 + cached 51.48352 + output 88.679025)
- Codex plan [codex]: primary 29% to 33%, delta +4pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 250 calls, 2 gifts, 4 offers/1 accepts
- cohort-2: gpt-5.6-terra — 4/5 living, 228 calls, 1 gifts, 6 offers/0 accepts
- cohort-3: gpt-5.6-luna — 3/5 living, 233 calls, 6 gifts, 12 offers/1 accepts

## Occupations
- generalist: 12/15 living, 19.5% proposed actions invalid, 22 offers/2 accepts, 2 structures

## Society
- Groups: 0
- Structures complete: {'storage': 2} | co-op builds: 0
- Ownership: {'agent-15': 1, 'agent-14': 1}

## Economy
- Gifts: 9 {'agent-5->agent-3': 1, 'agent-12->agent-9': 1, 'agent-2->agent-4': 3, 'agent-3->agent-5': 1, 'agent-4->agent-2': 1, 'agent-10->agent-2': 1, 'agent-9->agent-12': 1}
- Gift flow: 9 units / 13 book value | subsistence/material units: 9/0 | group status: {'in_group': 0, 'out_group': 9, 'unknown': 0}
- Trades: 22 offered / 2 accepted / 15 expired | conversion: 9.1% | invalid accepts: 16
- Trade funnel: 22 offers observed by counterparties / 12 attempted / 8 reached settlement checks / 2 completed | expired without attempt: 8
- Construction contributions: 32 value | productive assets: 2
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 39 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- build: t6, offer_trade: t8, gift: t16, death: t27, accept_trade: t28

## Agents
- agent-1: alive, hp 5, wealth 19, inventory {'coin': 4, 'fiber': 7, 'water': 1}, groups []
- agent-10: alive, hp 50, wealth 16, inventory {'coin': 3, 'fiber': 4, 'water': 2, 'wood': 1}, groups []
- agent-11: alive, hp 64, wealth 24, inventory {'coin': 4, 'fiber': 10}, groups []
- agent-12: alive, hp 54, wealth 21, inventory {'coin': 4, 'fiber': 6, 'food': 1, 'wood': 1}, groups []
- agent-13: alive, hp 35, wealth 12, inventory {'coin': 4, 'fiber': 3, 'water': 2}, groups []
- agent-14: alive, hp 100, wealth 9, inventory {'coin': 4, 'fiber': 1, 'water': 3}, groups []
- agent-15: alive, hp 100, wealth 10, inventory {'coin': 4, 'fiber': 1, 'water': 4}, groups []
- agent-2: alive, hp 45, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-3: alive, hp 18, wealth 11, inventory {'coin': 3, 'fiber': 3, 'water': 2}, groups []
- agent-4: DEAD, hp 0, wealth 18, inventory {'coin': 2, 'fiber': 8}, groups []
- agent-5: DEAD, hp 0, wealth 22, inventory {'coin': 3, 'fiber': 8, 'wood': 1}, groups []
- agent-6: alive, hp 100, wealth 17, inventory {'coin': 3, 'fiber': 4, 'wood': 2}, groups []
- agent-7: alive, hp 82, wealth 9, inventory {'coin': 4, 'fiber': 1, 'wood': 1}, groups []
- agent-8: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'ore': 2}, groups []
- agent-9: alive, hp 40, wealth 14, inventory {'fiber': 5, 'water': 1, 'wood': 1}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 406
- Activation position diagnostics: {'early': {'decisions': 236, 'proposed_actions': 730, 'invalid_actions': 123, 'say': 21, 'whisper': 5, 'offer_trade': 7, 'broadcast': 15, 'invalid_actions_per_proposed_action_pct': 16.8}, 'middle': {'decisions': 239, 'proposed_actions': 771, 'invalid_actions': 138, 'say': 25, 'offer_trade': 7, 'broadcast': 9, 'whisper': 8, 'accept_trade': 1, 'invalid_actions_per_proposed_action_pct': 17.9}, 'late': {'decisions': 236, 'proposed_actions': 726, 'invalid_actions': 174, 'say': 14, 'broadcast': 8, 'offer_trade': 8, 'accept_trade': 1, 'whisper': 2, 'invalid_actions_per_proposed_action_pct': 24.0}}
- Invalid actions: 435 / 2227 proposed (19.5% of proposed actions) | 0.612 per decision
- Invalid categories: {'resource_or_access_unavailable': 355, 'action_budget_or_energy': 23, 'target_or_carry_constraint': 22, 'trade_coordination_or_state': 17, 'movement_or_occupancy': 10, 'other': 8}
- Observation attribution: {'known_invalid_from_observation': 252, 'potential_same_tick_or_plan_state_change': 115, 'not_classified': 32, 'known_constraint_or_plan_sequence': 23, 'coordination_state_uncertain': 13}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
