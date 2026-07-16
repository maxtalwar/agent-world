# Run report: run

- Ticks: 20/20
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 400 calls, $0, 62.6% cache hit
- Per call: 9334.5 input tokens (3486.7 uncached), 385.4 output tokens; agent context chars static/dynamic 6493.0/3234.2
- Simulation plan credits: 99.207048 exact run-scoped credits (input 67.215712 + cached 9.51616 + output 22.475175)
- Codex plan [codex]: primary 3% to 8%, delta +5pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 80 calls, 0 gifts, 0 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 80 calls, 0 gifts, 2 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 60 calls, 0 gifts, 1 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 60 calls, 0 gifts, 13 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 60 calls, 1 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 60 calls, 0 gifts, 5 offers/0 accepts

## Occupations
- generalist: 20/20 living, 27.1% proposed actions invalid, 21 offers/0 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 1 {'agent-11->agent-9': 1}
- Gift flow: 1 units / 2 book value | subsistence/material units: 1/0 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 21 offered / 0 accepted / 13 expired | conversion: 0.0% | invalid accepts: 9
- Trade funnel: 21 offers observed by counterparties / 6 attempted / 3 reached settlement checks / 0 completed | expired without attempt: 11
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 23 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t3, gift: t18

## Agents
- agent-1: alive, hp 100, wealth 19, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 6}, groups []
- agent-10: alive, hp 100, wealth 20, inventory {'coin': 4, 'fiber': 6, 'stone': 1}, groups []
- agent-11: alive, hp 100, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-12: alive, hp 72, wealth 18, inventory {'coin': 4, 'fiber': 1, 'wood': 4}, groups []
- agent-13: alive, hp 50, wealth 10, inventory {'coin': 2, 'ore': 1}, groups []
- agent-14: alive, hp 95, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []
- agent-15: alive, hp 95, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []
- agent-16: alive, hp 67, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-17: alive, hp 70, wealth 18, inventory {'coin': 4, 'wood': 2, 'fiber': 4}, groups []
- agent-18: alive, hp 57, wealth 1, inventory {'water': 1}, groups []
- agent-19: alive, hp 100, wealth 20, inventory {'water': 1, 'coin': 4, 'fiber': 6, 'wood': 1}, groups []
- agent-2: alive, hp 100, wealth 15, inventory {'coin': 4, 'wood': 1, 'fiber': 4}, groups []
- agent-20: alive, hp 60, wealth 17, inventory {'coin': 2, 'fiber': 3, 'wood': 3}, groups []
- agent-3: alive, hp 83, wealth 14, inventory {'water': 2, 'coin': 4, 'stone': 2}, groups []
- agent-4: alive, hp 100, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-5: alive, hp 90, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-6: alive, hp 67, wealth 18, inventory {'coin': 2, 'fiber': 8}, groups []
- agent-7: alive, hp 87, wealth 16, inventory {'water': 1, 'coin': 2, 'fiber': 2, 'wood': 3}, groups []
- agent-8: alive, hp 100, wealth 12, inventory {'water': 4, 'coin': 4, 'fiber': 2}, groups []
- agent-9: alive, hp 95, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []

## Reliability
- Turn mode: shuffled-sequential-v1 | observations seeing earlier same-tick events: 185 | potential stale invalids after unobserved prior resolutions: 0
- Activation position diagnostics: {'early': {'decisions': 140, 'proposed_actions': 451, 'invalid_actions': 112, 'say': 23, 'offer_trade': 5, 'whisper': 2, 'broadcast': 13, 'invalid_actions_per_proposed_action_pct': 24.8}, 'middle': {'decisions': 120, 'proposed_actions': 384, 'invalid_actions': 112, 'say': 18, 'offer_trade': 6, 'whisper': 1, 'broadcast': 8, 'invalid_actions_per_proposed_action_pct': 29.2}, 'late': {'decisions': 140, 'proposed_actions': 446, 'invalid_actions': 123, 'say': 35, 'broadcast': 9, 'offer_trade': 10, 'whisper': 3, 'invalid_actions_per_proposed_action_pct': 27.6}}
- Invalid actions: 347 / 1281 proposed (27.1% of proposed actions) | 0.868 per decision
- Invalid categories: {'resource_or_access_unavailable': 239, 'action_budget_or_energy': 47, 'movement_or_occupancy': 24, 'trade_coordination_or_state': 18, 'target_or_carry_constraint': 14, 'other': 5}
- Observation attribution: {'known_invalid_from_observation': 178, 'potential_same_tick_or_plan_state_change': 89, 'known_constraint_or_plan_sequence': 47, 'not_classified': 24, 'coordination_state_uncertain': 9}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
