# Run report: run

- Ticks: 20/20
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 41
- LLM: 400 calls, $0, 61.3% cache hit
- Per call: 9377.6 input tokens (3626.9 uncached), 376.3 output tokens; agent context chars static/dynamic 6493.0/3182.0
- Simulation plan credits: 105.792198 exact run-scoped credits (input 74.174812 + cached 8.98336 + output 22.634025)
- Codex plan [codex]: primary 3% to 8%, delta +5pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 80 calls, 0 gifts, 4 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 80 calls, 0 gifts, 2 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 60 calls, 0 gifts, 1 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 60 calls, 0 gifts, 2 offers/1 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 60 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 60 calls, 0 gifts, 2 offers/0 accepts

## Occupations
- generalist: 20/20 living, 27.4% proposed actions invalid, 11 offers/1 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 11 offered / 1 accepted / 6 expired | conversion: 9.1% | invalid accepts: 7
- Trade funnel: 11 offers observed by counterparties / 5 attempted / 3 reached settlement checks / 1 completed | expired without attempt: 4
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 20 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t4, accept_trade: t12

## Agents
- agent-1: alive, hp 100, wealth 9, inventory {'water': 5, 'coin': 4}, groups []
- agent-10: alive, hp 70, wealth 18, inventory {'coin': 4, 'fiber': 7}, groups []
- agent-11: alive, hp 100, wealth 18, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-12: alive, hp 100, wealth 8, inventory {'water': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-13: alive, hp 90, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-14: alive, hp 97, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []
- agent-15: alive, hp 96, wealth 24, inventory {'coin': 4, 'fiber': 10}, groups []
- agent-16: alive, hp 60, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-17: alive, hp 85, wealth 17, inventory {'water': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-18: alive, hp 75, wealth 19, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-19: alive, hp 95, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-2: alive, hp 100, wealth 18, inventory {'coin': 4, 'fiber': 1, 'wood': 4}, groups []
- agent-20: alive, hp 62, wealth 22, inventory {'coin': 4, 'fiber': 6, 'wood': 2}, groups []
- agent-3: alive, hp 75, wealth 19, inventory {'water': 1, 'coin': 4, 'ore': 1, 'stone': 1, 'fiber': 1}, groups []
- agent-4: alive, hp 100, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-5: alive, hp 100, wealth 8, inventory {'water': 4, 'coin': 4}, groups []
- agent-6: alive, hp 100, wealth 20, inventory {'coin': 4, 'fiber': 2, 'wood': 4}, groups []
- agent-7: alive, hp 100, wealth 17, inventory {'coin': 4, 'fiber': 2, 'wood': 3}, groups []
- agent-8: alive, hp 55, wealth 20, inventory {'coin': 4, 'ore': 2}, groups []
- agent-9: alive, hp 100, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []

## Reliability
- Turn mode: shuffled-sequential-v1 | observations seeing earlier same-tick events: 197 | potential stale invalids after unobserved prior resolutions: 0
- Activation position diagnostics: {'early': {'decisions': 140, 'proposed_actions': 456, 'invalid_actions': 133, 'say': 29, 'broadcast': 9, 'offer_trade': 4, 'whisper': 1, 'accept_trade': 1, 'invalid_actions_per_proposed_action_pct': 29.2}, 'middle': {'decisions': 120, 'proposed_actions': 374, 'invalid_actions': 79, 'say': 33, 'broadcast': 11, 'offer_trade': 4, 'whisper': 1, 'invalid_actions_per_proposed_action_pct': 21.1}, 'late': {'decisions': 140, 'proposed_actions': 442, 'invalid_actions': 137, 'say': 31, 'broadcast': 15, 'offer_trade': 3, 'invalid_actions_per_proposed_action_pct': 31.0}}
- Invalid actions: 349 / 1272 proposed (27.4% of proposed actions) | 0.873 per decision
- Invalid categories: {'resource_or_access_unavailable': 234, 'action_budget_or_energy': 54, 'movement_or_occupancy': 36, 'trade_coordination_or_state': 10, 'target_or_carry_constraint': 9, 'other': 6}
- Observation attribution: {'known_invalid_from_observation': 184, 'potential_same_tick_or_plan_state_change': 87, 'known_constraint_or_plan_sequence': 54, 'not_classified': 19, 'coordination_state_uncertain': 5}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
