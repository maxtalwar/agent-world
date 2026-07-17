# Run report: run

- Ticks: 50/50
- Agents: 10 living / 5 dead
- Action points/tick: 4 | seed: 11
- LLM: 684 calls, $0, 60.6% cache hit
- Per call: 13819.2 input tokens (5448.7 uncached), 317.7 output tokens; agent context chars static/dynamic 6493.0/3338.8
- Simulation plan credits: 421.234605 exact run-scoped credits (input 285.9265 + cached 40.99808 + output 94.310025)
- Codex plan [codex]: primary 23% to 29%, delta +6pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 4/5 living, 241 calls, 6 gifts, 19 offers/3 accepts
- cohort-2: gpt-5.6-terra — 2/5 living, 203 calls, 1 gifts, 12 offers/1 accepts
- cohort-3: gpt-5.6-luna — 4/5 living, 240 calls, 3 gifts, 3 offers/0 accepts

## Occupations
- generalist: 10/15 living, 19.3% proposed actions invalid, 34 offers/4 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 10 {'agent-15->agent-8': 1, 'agent-9->agent-2': 2, 'agent-10->agent-11': 2, 'agent-2->agent-12': 1, 'agent-7->agent-2': 1, 'agent-2->agent-3': 2, 'agent-10->agent-6': 1}
- Gift flow: 11 units / 15 book value | subsistence/material units: 11/0 | group status: {'in_group': 0, 'out_group': 10, 'unknown': 0}
- Trades: 34 offered / 4 accepted / 30 expired | conversion: 11.8% | invalid accepts: 22
- Trade funnel: 33 offers observed by counterparties / 16 attempted / 13 reached settlement checks / 4 completed | expired without attempt: 18
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 37 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t3, accept_trade: t15, death: t25, gift: t27

## Agents
- agent-1: alive, hp 61, wealth 24, inventory {'coin': 4, 'fiber': 10}, groups []
- agent-10: alive, hp 100, wealth 16, inventory {'water': 1, 'coin': 4, 'fiber': 4, 'wood': 1}, groups []
- agent-11: alive, hp 29, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-12: DEAD, hp 0, wealth 21, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-13: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-14: alive, hp 75, wealth 22, inventory {'food': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-15: DEAD, hp 0, wealth 22, inventory {'coin': 5, 'fiber': 7, 'wood': 1}, groups []
- agent-2: alive, hp 52, wealth 17, inventory {'coin': 4, 'fiber': 5, 'wood': 1}, groups []
- agent-3: alive, hp 19, wealth 14, inventory {'coin': 4, 'ore': 1, 'fiber': 1}, groups []
- agent-4: alive, hp 92, wealth 13, inventory {'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-5: DEAD, hp 0, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-6: alive, hp 6, wealth 13, inventory {'fiber': 2, 'wood': 3}, groups []
- agent-7: alive, hp 62, wealth 8, inventory {'water': 4, 'coin': 4}, groups []
- agent-8: DEAD, hp 0, wealth 15, inventory {'water': 1, 'coin': 2, 'stone': 2, 'fiber': 2}, groups []
- agent-9: alive, hp 60, wealth 19, inventory {'coin': 4, 'fiber': 6, 'wood': 1}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 385
- Activation position diagnostics: {'early': {'decisions': 230, 'proposed_actions': 739, 'invalid_actions': 156, 'offer_trade': 9, 'broadcast': 15, 'say': 38, 'accept_trade': 1, 'whisper': 1, 'invalid_actions_per_proposed_action_pct': 21.1}, 'middle': {'decisions': 225, 'proposed_actions': 715, 'invalid_actions': 133, 'offer_trade': 13, 'say': 48, 'accept_trade': 1, 'whisper': 3, 'broadcast': 7, 'invalid_actions_per_proposed_action_pct': 18.6}, 'late': {'decisions': 230, 'proposed_actions': 735, 'invalid_actions': 133, 'say': 53, 'offer_trade': 12, 'broadcast': 9, 'whisper': 1, 'accept_trade': 2, 'invalid_actions_per_proposed_action_pct': 18.1}}
- Invalid actions: 422 / 2189 proposed (19.3% of proposed actions) | 0.616 per decision
- Invalid categories: {'resource_or_access_unavailable': 329, 'trade_coordination_or_state': 27, 'action_budget_or_energy': 24, 'target_or_carry_constraint': 23, 'movement_or_occupancy': 10, 'other': 9}
- Observation attribution: {'known_invalid_from_observation': 241, 'potential_same_tick_or_plan_state_change': 104, 'not_classified': 33, 'known_constraint_or_plan_sequence': 24, 'coordination_state_uncertain': 20}
- LLM failure events: 1
- Decision quality: degraded | failure rate 0.15% | flags ['decision_failures_present', 'missing_usage_records']
