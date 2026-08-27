# Run report: run

- Ticks: 50/50
- Agents: 8 living / 7 dead
- Action points/tick: 4 | seed: 23
- LLM: 623 calls, $0, 66.2% cache hit
- Per call: 13701.8 input tokens (4636.6 uncached), 292.3 output tokens; agent context chars static/dynamic 6493.0/2939.2
- Simulation plan credits: 327.289812 exact run-scoped credits (input 209.665262 + cached 42.0304 + output 75.59415)
- Codex plan [codex]: primary 45% to 48%, delta +3pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 3/5 living, 216 calls, 0 gifts, 4 offers/0 accepts
- cohort-2: gpt-5.6-terra — 2/5 living, 199 calls, 2 gifts, 4 offers/0 accepts
- cohort-3: gpt-5.6-luna — 3/5 living, 208 calls, 1 gifts, 0 offers/1 accepts

## Occupations
- generalist: 8/15 living, 21.1% proposed actions invalid, 8 offers/1 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 3 {'agent-11->agent-6': 1, 'agent-8->agent-3': 1, 'agent-1->agent-2': 1}
- Gift flow: 3 units / 5 book value | subsistence/material units: 3/0 | group status: {'in_group': 0, 'out_group': 3, 'unknown': 0}
- Trades: 8 offered / 1 accepted / 7 expired | conversion: 12.5% | invalid accepts: 8
- Trade funnel: 8 offers observed by counterparties / 6 attempted / 4 reached settlement checks / 1 completed | expired without attempt: 2
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 33 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- gift: t0, offer_trade: t10, accept_trade: t12, death: t25

## Agents
- agent-1: alive, hp 27, wealth 20, inventory {'coin': 4, 'wood': 2, 'fiber': 5}, groups []
- agent-10: DEAD, hp 0, wealth 19, inventory {'coin': 2, 'fiber': 7, 'wood': 1}, groups []
- agent-11: alive, hp 73, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-12: DEAD, hp 0, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []
- agent-13: DEAD, hp 0, wealth 22, inventory {'coin': 4, 'ore': 1, 'fiber': 5}, groups []
- agent-14: alive, hp 45, wealth 18, inventory {'food': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-15: DEAD, hp 0, wealth 19, inventory {'coin': 4, 'fiber': 3, 'wood': 3}, groups []
- agent-2: alive, hp 30, wealth 13, inventory {'water': 2, 'coin': 4, 'wood': 1, 'fiber': 2}, groups []
- agent-3: DEAD, hp 0, wealth 16, inventory {'coin': 4, 'ore': 1, 'stone': 1}, groups []
- agent-4: alive, hp 45, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-5: DEAD, hp 0, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-6: alive, hp 75, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []
- agent-7: alive, hp 15, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-8: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'stone': 2}, groups []
- agent-9: alive, hp 100, wealth 18, inventory {'coin': 4, 'fiber': 4, 'wood': 2}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 374
- Activation position diagnostics: {'early': {'decisions': 211, 'proposed_actions': 664, 'invalid_actions': 138, 'broadcast': 5, 'whisper': 3, 'offer_trade': 3, 'say': 18, 'invalid_actions_per_proposed_action_pct': 20.8}, 'middle': {'decisions': 202, 'proposed_actions': 617, 'invalid_actions': 131, 'whisper': 1, 'say': 26, 'broadcast': 12, 'offer_trade': 2, 'invalid_actions_per_proposed_action_pct': 21.2}, 'late': {'decisions': 211, 'proposed_actions': 657, 'invalid_actions': 140, 'broadcast': 6, 'accept_trade': 1, 'say': 25, 'offer_trade': 3, 'invalid_actions_per_proposed_action_pct': 21.3}}
- Invalid actions: 409 / 1938 proposed (21.1% of proposed actions) | 0.655 per decision
- Invalid categories: {'resource_or_access_unavailable': 355, 'action_budget_or_energy': 25, 'target_or_carry_constraint': 15, 'trade_coordination_or_state': 8, 'movement_or_occupancy': 5, 'other': 1}
- Observation attribution: {'known_invalid_from_observation': 219, 'potential_same_tick_or_plan_state_change': 141, 'known_constraint_or_plan_sequence': 25, 'not_classified': 18, 'coordination_state_uncertain': 6}
- LLM failure events: 1
- Decision quality: degraded | failure rate 0.16% | flags ['decision_failures_present', 'missing_usage_records']
