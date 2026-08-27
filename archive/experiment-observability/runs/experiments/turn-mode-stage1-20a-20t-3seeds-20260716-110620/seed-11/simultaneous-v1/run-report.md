# Run report: run

- Ticks: 20/20
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 400 calls, $0, 57.7% cache hit
- Per call: 9352.4 input tokens (3959.9 uncached), 394.1 output tokens; agent context chars static/dynamic 6493.0/3299.3
- Simulation plan credits: 120.851028 exact run-scoped credits (input 88.765712 + cached 7.46304 + output 24.622275)
- Codex plan [codex]: primary 1% to 3%, delta +2pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 80 calls, 1 gifts, 4 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 80 calls, 0 gifts, 3 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 60 calls, 0 gifts, 1 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 60 calls, 0 gifts, 6 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 60 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 60 calls, 0 gifts, 5 offers/0 accepts

## Occupations
- generalist: 20/20 living, 26.8% proposed actions invalid, 19 offers/0 accepts, 1 structures

## Society
- Groups: 0
- Structures complete: {'storage': 1} | co-op builds: 0
- Ownership: {'agent-20': 1}

## Economy
- Gifts: 1 {'agent-5->agent-15': 1}
- Gift flow: 1 units / 1 book value | subsistence/material units: 1/0 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 19 offered / 0 accepted / 13 expired | conversion: 0.0% | invalid accepts: 11
- Trade funnel: 17 offers observed by counterparties / 5 attempted / 2 reached settlement checks / 0 completed | expired without attempt: 8
- Construction contributions: 16 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 26 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t2, build: t4, gift: t5

## Agents
- agent-1: alive, hp 100, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []
- agent-10: alive, hp 100, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-11: alive, hp 80, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-12: alive, hp 58, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []
- agent-13: alive, hp 61, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-14: alive, hp 90, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []
- agent-15: alive, hp 80, wealth 15, inventory {'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-16: alive, hp 100, wealth 24, inventory {'coin': 4, 'fiber': 10}, groups []
- agent-17: alive, hp 64, wealth 17, inventory {'coin': 4, 'wood': 1, 'fiber': 5}, groups []
- agent-18: alive, hp 95, wealth 5, inventory {'water': 3, 'fiber': 1}, groups []
- agent-19: alive, hp 100, wealth 18, inventory {'food': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-2: alive, hp 79, wealth 15, inventory {'water': 1, 'coin': 4, 'wood': 2, 'fiber': 2}, groups []
- agent-20: alive, hp 85, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-3: alive, hp 67, wealth 12, inventory {'coin': 4, 'stone': 2}, groups []
- agent-4: alive, hp 90, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-5: alive, hp 60, wealth 13, inventory {'water': 3, 'coin': 4, 'fiber': 3}, groups []
- agent-6: alive, hp 70, wealth 18, inventory {'coin': 4, 'fiber': 1, 'wood': 4}, groups []
- agent-7: alive, hp 100, wealth 20, inventory {'food': 1, 'coin': 2, 'fiber': 5, 'wood': 2}, groups []
- agent-8: alive, hp 66, wealth 3, inventory {'water': 3}, groups []
- agent-9: alive, hp 97, wealth 21, inventory {'water': 1, 'coin': 4, 'fiber': 8}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 326
- Activation position diagnostics: {'early': {'decisions': 140, 'proposed_actions': 448, 'invalid_actions': 124, 'say': 45, 'offer_trade': 9, 'broadcast': 14, 'whisper': 2, 'invalid_actions_per_proposed_action_pct': 27.7}, 'middle': {'decisions': 120, 'proposed_actions': 377, 'invalid_actions': 98, 'say': 48, 'offer_trade': 5, 'broadcast': 7, 'invalid_actions_per_proposed_action_pct': 26.0}, 'late': {'decisions': 140, 'proposed_actions': 453, 'invalid_actions': 121, 'say': 48, 'broadcast': 5, 'offer_trade': 5, 'invalid_actions_per_proposed_action_pct': 26.7}}
- Invalid actions: 343 / 1278 proposed (26.8% of proposed actions) | 0.858 per decision
- Invalid categories: {'resource_or_access_unavailable': 235, 'action_budget_or_energy': 52, 'movement_or_occupancy': 21, 'target_or_carry_constraint': 19, 'trade_coordination_or_state': 14, 'other': 2}
- Observation attribution: {'known_invalid_from_observation': 170, 'potential_same_tick_or_plan_state_change': 90, 'known_constraint_or_plan_sequence': 52, 'not_classified': 21, 'coordination_state_uncertain': 10}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
