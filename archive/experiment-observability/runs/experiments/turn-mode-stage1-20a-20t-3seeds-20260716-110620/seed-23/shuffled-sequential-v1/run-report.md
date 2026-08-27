# Run report: run

- Ticks: 20/20
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 23
- LLM: 400 calls, $0, 61.9% cache hit
- Per call: 9555.1 input tokens (3643.8 uncached), 407.8 output tokens; agent context chars static/dynamic 6493.0/3479.5
- Simulation plan credits: 102.98468 exact run-scoped credits (input 70.0637 + cached 9.35808 + output 23.5629)
- Codex plan [codex]: primary 1% to 6%, delta +5pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 80 calls, 0 gifts, 1 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 80 calls, 0 gifts, 6 offers/1 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 60 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 60 calls, 0 gifts, 8 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 60 calls, 0 gifts, 3 offers/0 accepts
- cohort-6: fable — 3/3 living, 60 calls, 0 gifts, 5 offers/1 accepts

## Occupations
- generalist: 20/20 living, 27.4% proposed actions invalid, 23 offers/2 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 23 offered / 2 accepted / 15 expired | conversion: 8.7% | invalid accepts: 10
- Trade funnel: 21 offers observed by counterparties / 7 attempted / 4 reached settlement checks / 2 completed | expired without attempt: 11
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 20 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t1, accept_trade: t16

## Agents
- agent-1: alive, hp 90, wealth 22, inventory {'food': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-10: alive, hp 85, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-11: alive, hp 69, wealth 15, inventory {'water': 1, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-12: alive, hp 52, wealth 21, inventory {'coin': 4, 'fiber': 4, 'wood': 3}, groups []
- agent-13: alive, hp 72, wealth 8, inventory {'ore': 1}, groups []
- agent-14: alive, hp 90, wealth 19, inventory {'coin': 4, 'fiber': 3, 'wood': 3}, groups []
- agent-15: alive, hp 100, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-16: alive, hp 100, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-17: alive, hp 95, wealth 19, inventory {'coin': 4, 'fiber': 6, 'wood': 1}, groups []
- agent-18: alive, hp 100, wealth 22, inventory {'coin': 6, 'ore': 2}, groups []
- agent-19: alive, hp 100, wealth 13, inventory {'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-2: alive, hp 98, wealth 18, inventory {'food': 2, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-20: alive, hp 70, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-3: alive, hp 88, wealth 5, inventory {'water': 1, 'stone': 1}, groups []
- agent-4: alive, hp 100, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-5: alive, hp 80, wealth 17, inventory {'coin': 2, 'fiber': 3, 'wood': 3}, groups []
- agent-6: alive, hp 100, wealth 15, inventory {'water': 2, 'coin': 4, 'fiber': 3, 'wood': 1}, groups []
- agent-7: alive, hp 100, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-8: alive, hp 82, wealth 8, inventory {'ore': 1}, groups []
- agent-9: alive, hp 85, wealth 14, inventory {'water': 2, 'coin': 4, 'fiber': 4}, groups []

## Reliability
- Turn mode: shuffled-sequential-v1 | observations seeing earlier same-tick events: 221 | potential stale invalids after unobserved prior resolutions: 0
- Activation position diagnostics: {'early': {'decisions': 140, 'proposed_actions': 448, 'invalid_actions': 123, 'say': 45, 'offer_trade': 11, 'broadcast': 15, 'accept_trade': 2, 'invalid_actions_per_proposed_action_pct': 27.5}, 'middle': {'decisions': 120, 'proposed_actions': 366, 'invalid_actions': 100, 'say': 34, 'offer_trade': 6, 'broadcast': 16, 'invalid_actions_per_proposed_action_pct': 27.3}, 'late': {'decisions': 140, 'proposed_actions': 429, 'invalid_actions': 117, 'say': 44, 'broadcast': 17, 'offer_trade': 6, 'invalid_actions_per_proposed_action_pct': 27.3}}
- Invalid actions: 340 / 1243 proposed (27.4% of proposed actions) | 0.85 per decision
- Invalid categories: {'resource_or_access_unavailable': 231, 'action_budget_or_energy': 60, 'movement_or_occupancy': 19, 'trade_coordination_or_state': 18, 'target_or_carry_constraint': 9, 'other': 3}
- Observation attribution: {'known_invalid_from_observation': 166, 'potential_same_tick_or_plan_state_change': 91, 'known_constraint_or_plan_sequence': 60, 'not_classified': 13, 'coordination_state_uncertain': 10}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
