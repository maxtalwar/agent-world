# Run report: run

- Ticks: 50/50
- Agents: 8 living / 7 dead
- Action points/tick: 4 | seed: 11
- LLM: 685 calls, $0, 60.5% cache hit
- Per call: 13783.6 input tokens (5450.3 uncached), 389.4 output tokens; agent context chars static/dynamic 6493.0/3267.9
- Simulation plan credits: 442.094882 exact run-scoped credits (input 289.049662 + cached 41.65312 + output 111.3921)
- Codex plan [codex]: primary 18% to 22%, delta +4pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 250 calls, 5 gifts, 6 offers/1 accepts
- cohort-2: gpt-5.6-terra — 0/5 living, 202 calls, 3 gifts, 11 offers/3 accepts
- cohort-3: gpt-5.6-luna — 3/5 living, 233 calls, 2 gifts, 11 offers/1 accepts

## Occupations
- generalist: 8/15 living, 20.1% proposed actions invalid, 28 offers/5 accepts, 2 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 1, 'storage': 1} | co-op builds: 0
- Ownership: {'agent-15': 1, 'agent-6': 1}

## Economy
- Gifts: 10 {'agent-14->agent-11': 1, 'agent-10->agent-8': 1, 'agent-7->agent-2': 1, 'agent-12->agent-4': 2, 'agent-2->agent-9': 2, 'agent-6->agent-12': 1, 'agent-9->agent-2': 1, 'agent-15->agent-5': 1}
- Gift flow: 10 units / 16 book value | subsistence/material units: 6/4 | group status: {'in_group': 0, 'out_group': 10, 'unknown': 0}
- Trades: 28 offered / 5 accepted / 20 expired | conversion: 17.9% | invalid accepts: 29
- Trade funnel: 28 offers observed by counterparties / 19 attempted / 13 reached settlement checks / 5 completed | expired without attempt: 9
- Construction contributions: 26 value | productive assets: 2
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 38 | tile claims: 0 | access grants: 3

## Milestones (first tick)
- offer_trade: t3, build: t4, gift: t5, craft: t6, accept_trade: t14, grant_access: t29, death: t33

## Agents
- agent-1: DEAD, hp 0, wealth 19, inventory {'coin': 2, 'fiber': 7, 'wood': 1}, groups []
- agent-10: alive, hp 60, wealth 16, inventory {'coin': 5, 'fiber': 4, 'wood': 1}, groups []
- agent-11: alive, hp 68, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-12: DEAD, hp 0, wealth 14, inventory {'water': 1, 'coin': 1, 'fiber': 3, 'wood': 2}, groups []
- agent-13: DEAD, hp 0, wealth 15, inventory {'water': 1, 'coin': 2, 'ore': 1, 'fiber': 2}, groups []
- agent-14: alive, hp 65, wealth 19, inventory {'coin': 3, 'fiber': 6, 'stone': 1}, groups []
- agent-15: alive, hp 95, wealth 17, inventory {'coin': 4, 'fiber': 2, 'wood': 3}, groups []
- agent-2: alive, hp 17, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-3: DEAD, hp 0, wealth 24, inventory {'coin': 4, 'ore': 2, 'fiber': 2}, groups []
- agent-4: DEAD, hp 0, wealth 23, inventory {'coin': 5, 'fiber': 9}, groups []
- agent-5: alive, hp 19, wealth 21, inventory {'food': 1, 'coin': 4, 'fiber': 6, 'wood': 1}, groups []
- agent-6: alive, hp 95, wealth 18, inventory {'water': 2, 'coin': 4, 'tool': 1}, groups []
- agent-7: DEAD, hp 0, wealth 14, inventory {'fiber': 7}, groups []
- agent-8: DEAD, hp 0, wealth 15, inventory {'coin': 1, 'stone': 2, 'fiber': 3}, groups []
- agent-9: alive, hp 65, wealth 18, inventory {'coin': 4, 'fiber': 4, 'wood': 2}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 404
- Activation position diagnostics: {'early': {'decisions': 228, 'proposed_actions': 703, 'invalid_actions': 125, 'say': 43, 'whisper': 3, 'broadcast': 6, 'offer_trade': 4, 'accept_trade': 2, 'invalid_actions_per_proposed_action_pct': 17.8}, 'middle': {'decisions': 229, 'proposed_actions': 713, 'invalid_actions': 142, 'say': 54, 'broadcast': 8, 'offer_trade': 15, 'whisper': 5, 'accept_trade': 2, 'invalid_actions_per_proposed_action_pct': 19.9}, 'late': {'decisions': 228, 'proposed_actions': 742, 'invalid_actions': 166, 'say': 38, 'offer_trade': 9, 'whisper': 4, 'accept_trade': 1, 'broadcast': 2, 'invalid_actions_per_proposed_action_pct': 22.4}}
- Invalid actions: 433 / 2158 proposed (20.1% of proposed actions) | 0.632 per decision
- Invalid categories: {'resource_or_access_unavailable': 341, 'trade_coordination_or_state': 29, 'target_or_carry_constraint': 26, 'action_budget_or_energy': 14, 'movement_or_occupancy': 12, 'other': 11}
- Observation attribution: {'known_invalid_from_observation': 247, 'potential_same_tick_or_plan_state_change': 111, 'not_classified': 44, 'coordination_state_uncertain': 17, 'known_constraint_or_plan_sequence': 14}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
