# Run report: run

- Ticks: 50/50
- Agents: 13 living / 2 dead
- Action points/tick: 4 | seed: 23
- LLM: 696 calls, $0, 58.7% cache hit
- Per call: 13937.7 input tokens (5757.1 uncached), 677.5 output tokens; agent context chars static/dynamic 6493.0/3645.0
- Simulation plan credits: 519.847412 exact run-scoped credits (input 312.858412 + cached 40.2736 + output 166.7154)
- Codex plan [codex]: primary 34% to 45%, delta +11pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 240 calls, 8 gifts, 8 offers/5 accepts
- cohort-2: gpt-5.6-terra — 4/5 living, 227 calls, 1 gifts, 6 offers/3 accepts
- cohort-3: gpt-5.6-luna — 4/5 living, 229 calls, 4 gifts, 20 offers/5 accepts

## Occupations
- generalist: 13/15 living, 12.6% proposed actions invalid, 34 offers/13 accepts, 7 structures

## Society
- Groups: 0
- Structures complete: {'storage': 2, 'farm_plot': 5} | co-op builds: 0
- Ownership: {'agent-14': 2, 'agent-9': 2, 'agent-15': 1, 'agent-6': 1, 'agent-11': 1}

## Economy
- Gifts: 13 {'agent-11->agent-6': 3, 'agent-6->agent-11': 3, 'agent-8->agent-1': 1, 'agent-14->agent-2': 2, 'agent-6->agent-4': 1, 'agent-5->agent-1': 1, 'agent-10->agent-13': 2}
- Gift flow: 14 units / 20 book value | subsistence/material units: 13/1 | group status: {'in_group': 0, 'out_group': 13, 'unknown': 0}
- Trades: 34 offered / 13 accepted / 17 expired | conversion: 38.2% | invalid accepts: 17
- Trade funnel: 32 offers observed by counterparties / 25 attempted / 20 reached settlement checks / 13 completed | expired without attempt: 8
- Construction contributions: 82 value | productive assets: 7
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 54 | tile claims: 3 | access grants: 7

## Milestones (first tick)
- gift: t1, offer_trade: t7, build: t16, build_started: t16, claim_tile: t19, grant_access: t23, accept_trade: t25, death: t26

## Agents
- agent-1: alive, hp 52, wealth 22, inventory {'coin': 4, 'fiber': 6, 'wood': 2}, groups []
- agent-10: alive, hp 70, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-11: alive, hp 85, wealth 14, inventory {'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-12: alive, hp 75, wealth 16, inventory {'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-13: alive, hp 34, wealth 19, inventory {'water': 1, 'coin': 4, 'ore': 1, 'fiber': 3}, groups []
- agent-14: alive, hp 100, wealth 5, inventory {'water': 1, 'coin': 4}, groups []
- agent-15: alive, hp 90, wealth 14, inventory {'water': 2, 'coin': 4, 'wood': 2, 'fiber': 1}, groups []
- agent-2: alive, hp 70, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-3: DEAD, hp 0, wealth 4, inventory {'coin': 4}, groups []
- agent-4: alive, hp 75, wealth 19, inventory {'water': 1, 'coin': 3, 'fiber': 6, 'wood': 1}, groups []
- agent-5: alive, hp 65, wealth 19, inventory {'water': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-6: alive, hp 100, wealth 20, inventory {'food': 4, 'coin': 4, 'wood': 2, 'fiber': 1}, groups []
- agent-7: alive, hp 100, wealth 8, inventory {'water': 4, 'coin': 4}, groups []
- agent-8: DEAD, hp 0, wealth 18, inventory {'coin': 2, 'stone': 2, 'ore': 1}, groups []
- agent-9: alive, hp 100, wealth 5, inventory {'water': 1, 'coin': 4}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 262
- Activation position diagnostics: {'early': {'decisions': 229, 'proposed_actions': 701, 'invalid_actions': 85, 'whisper': 11, 'say': 37, 'offer_trade': 13, 'broadcast': 14, 'accept_trade': 5, 'invalid_actions_per_proposed_action_pct': 12.1}, 'middle': {'decisions': 248, 'proposed_actions': 803, 'invalid_actions': 107, 'say': 45, 'broadcast': 16, 'offer_trade': 11, 'whisper': 12, 'accept_trade': 2, 'invalid_actions_per_proposed_action_pct': 13.3}, 'late': {'decisions': 229, 'proposed_actions': 720, 'invalid_actions': 88, 'say': 32, 'broadcast': 9, 'offer_trade': 10, 'whisper': 11, 'accept_trade': 6, 'invalid_actions_per_proposed_action_pct': 12.2}}
- Invalid actions: 280 / 2224 proposed (12.6% of proposed actions) | 0.397 per decision
- Invalid categories: {'resource_or_access_unavailable': 197, 'target_or_carry_constraint': 41, 'trade_coordination_or_state': 19, 'action_budget_or_energy': 12, 'other': 9, 'movement_or_occupancy': 2}
- Observation attribution: {'known_invalid_from_observation': 111, 'potential_same_tick_or_plan_state_change': 79, 'not_classified': 63, 'coordination_state_uncertain': 15, 'known_constraint_or_plan_sequence': 12}
- LLM failure events: 10
- Decision quality: degraded | failure rate 1.42% | flags ['decision_failures_present', 'missing_usage_records']
