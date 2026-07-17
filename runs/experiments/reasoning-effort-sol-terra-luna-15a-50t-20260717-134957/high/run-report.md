# Run report: run

- Ticks: 50/50
- Agents: 11 living / 4 dead
- Action points/tick: 4 | seed: 11
- LLM: 709 calls, $0, 59.2% cache hit
- Per call: 13826.1 input tokens (5638.1 uncached), 628.4 output tokens; agent context chars static/dynamic 6493.0/3164.2
- Simulation plan credits: 514.18461 exact run-scoped credits (input 307.421225 + cached 42.30496 + output 164.458425)
- Codex plan [codex]: primary 23% to 32%, delta +9pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 250 calls, 6 gifts, 3 offers/4 accepts
- cohort-2: gpt-5.6-terra — 4/5 living, 231 calls, 0 gifts, 7 offers/2 accepts
- cohort-3: gpt-5.6-luna — 2/5 living, 228 calls, 2 gifts, 10 offers/0 accepts

## Occupations
- generalist: 11/15 living, 17.8% proposed actions invalid, 20 offers/6 accepts, 1 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 1} | co-op builds: 0
- Ownership: {'agent-14': 1}

## Economy
- Gifts: 8 {'agent-2->agent-7': 1, 'agent-14->agent-1': 1, 'agent-2->agent-9': 1, 'agent-9->agent-2': 1, 'agent-15->agent-5': 2, 'agent-14->agent-12': 1, 'agent-14->agent-8': 1}
- Gift flow: 8 units / 11 book value | subsistence/material units: 8/0 | group status: {'in_group': 0, 'out_group': 8, 'unknown': 0}
- Trades: 20 offered / 6 accepted / 13 expired | conversion: 30.0% | invalid accepts: 19
- Trade funnel: 17 offers observed by counterparties / 15 attempted / 13 reached settlement checks / 6 completed | expired without attempt: 4
- Construction contributions: 10 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 45 | tile claims: 1 | access grants: 0

## Milestones (first tick)
- gift: t2, offer_trade: t4, craft: t5, accept_trade: t5, build: t13, claim_tile: t22, death: t28

## Agents
- agent-1: alive, hp 54, wealth 18, inventory {'coin': 1, 'fiber': 3, 'food': 1, 'wood': 3}, groups []
- agent-10: alive, hp 50, wealth 22, inventory {'coin': 4, 'fiber': 6, 'wood': 2}, groups []
- agent-11: alive, hp 7, wealth 11, inventory {'coin': 1, 'fiber': 5}, groups []
- agent-12: alive, hp 80, wealth 28, inventory {'coin': 4, 'fiber': 4, 'tool': 1, 'water': 1, 'wood': 1}, groups []
- agent-13: DEAD, hp 0, wealth 16, inventory {'coin': 4, 'stone': 3}, groups []
- agent-14: alive, hp 85, wealth 24, inventory {'coin': 6, 'fiber': 1, 'food': 5, 'wood': 2}, groups []
- agent-15: alive, hp 70, wealth 24, inventory {'coin': 4, 'fiber': 1, 'tool': 1, 'wood': 2}, groups []
- agent-2: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []
- agent-3: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-4: alive, hp 70, wealth 20, inventory {'coin': 3, 'fiber': 7, 'food': 1, 'water': 1}, groups []
- agent-5: DEAD, hp 0, wealth 18, inventory {'coin': 4, 'fiber': 7}, groups []
- agent-6: alive, hp 55, wealth 20, inventory {'coin': 5, 'fiber': 3, 'wood': 3}, groups []
- agent-7: alive, hp 100, wealth 18, inventory {'coin': 4, 'fiber': 4, 'wood': 2}, groups []
- agent-8: alive, hp 3, wealth 17, inventory {'fiber': 3, 'ore': 1, 'wood': 1}, groups []
- agent-9: alive, hp 52, wealth 18, inventory {'coin': 4, 'fiber': 4, 'wood': 2}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 380
- Activation position diagnostics: {'early': {'decisions': 231, 'proposed_actions': 726, 'invalid_actions': 119, 'say': 21, 'whisper': 21, 'offer_trade': 8, 'broadcast': 10, 'accept_trade': 1, 'invalid_actions_per_proposed_action_pct': 16.4}, 'middle': {'decisions': 247, 'proposed_actions': 803, 'invalid_actions': 150, 'say': 19, 'offer_trade': 5, 'whisper': 10, 'accept_trade': 2, 'broadcast': 10, 'invalid_actions_per_proposed_action_pct': 18.7}, 'late': {'decisions': 231, 'proposed_actions': 741, 'invalid_actions': 134, 'say': 27, 'offer_trade': 7, 'accept_trade': 3, 'whisper': 18, 'broadcast': 19, 'invalid_actions_per_proposed_action_pct': 18.1}}
- Invalid actions: 403 / 2270 proposed (17.8% of proposed actions) | 0.568 per decision
- Invalid categories: {'resource_or_access_unavailable': 309, 'target_or_carry_constraint': 45, 'trade_coordination_or_state': 20, 'action_budget_or_energy': 13, 'other': 11, 'movement_or_occupancy': 5}
- Observation attribution: {'known_invalid_from_observation': 196, 'potential_same_tick_or_plan_state_change': 122, 'not_classified': 57, 'coordination_state_uncertain': 15, 'known_constraint_or_plan_sequence': 13}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
