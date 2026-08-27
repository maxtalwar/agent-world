# Run report: run

- Ticks: 50/50
- Agents: 10 living / 5 dead
- Action points/tick: 4 | seed: 23
- LLM: 681 calls, $0, 60.7% cache hit
- Per call: 13785.7 input tokens (5422.3 uncached), 376.0 output tokens; agent context chars static/dynamic 6493.0/3014.9
- Simulation plan credits: 445.323308 exact run-scoped credits (input 295.374888 + cached 41.38592 + output 108.5625)
- Codex plan [codex]: primary 48% to 53%, delta +5pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 245 calls, 2 gifts, 4 offers/1 accepts
- cohort-2: gpt-5.6-terra — 3/5 living, 226 calls, 1 gifts, 5 offers/0 accepts
- cohort-3: gpt-5.6-luna — 2/5 living, 210 calls, 1 gifts, 2 offers/0 accepts

## Occupations
- generalist: 10/15 living, 19.2% proposed actions invalid, 11 offers/1 accepts, 2 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 2} | co-op builds: 0
- Ownership: {'agent-6': 1, 'agent-14': 1}

## Economy
- Gifts: 4 {'agent-10->agent-5': 1, 'agent-13->agent-9': 1, 'agent-9->agent-13': 1, 'agent-4->agent-2': 1}
- Gift flow: 4 units / 6 book value | subsistence/material units: 3/1 | group status: {'in_group': 0, 'out_group': 4, 'unknown': 0}
- Trades: 11 offered / 1 accepted / 7 expired | conversion: 9.1% | invalid accepts: 10
- Trade funnel: 11 offers observed by counterparties / 6 attempted / 3 reached settlement checks / 1 completed | expired without attempt: 2
- Construction contributions: 20 value | productive assets: 2
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 38 | tile claims: 0 | access grants: 1

## Milestones (first tick)
- craft: t4, offer_trade: t10, build: t18, death: t27, gift: t31, accept_trade: t38, grant_access: t42

## Agents
- agent-1: alive, hp 58, wealth 13, inventory {'coin': 2, 'fiber': 4, 'wood': 1}, groups []
- agent-10: alive, hp 90, wealth 18, inventory {'coin': 4, 'wood': 2, 'ore': 1}, groups []
- agent-11: alive, hp 78, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-12: alive, hp 89, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 2, 'fiber': 6}, groups []
- agent-13: alive, hp 55, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-14: alive, hp 65, wealth 20, inventory {'food': 3, 'coin': 6, 'fiber': 1, 'wood': 2}, groups []
- agent-15: alive, hp 80, wealth 18, inventory {'water': 1, 'coin': 4, 'fiber': 2, 'wood': 3}, groups []
- agent-2: DEAD, hp 0, wealth 21, inventory {'food': 1, 'coin': 4, 'fiber': 6, 'wood': 1}, groups []
- agent-3: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'ore': 2}, groups []
- agent-4: alive, hp 56, wealth 13, inventory {'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-5: DEAD, hp 0, wealth 14, inventory {'water': 1, 'coin': 3, 'fiber': 5}, groups []
- agent-6: alive, hp 60, wealth 14, inventory {'food': 1, 'coin': 4, 'fiber': 1, 'wood': 2}, groups []
- agent-7: DEAD, hp 0, wealth 11, inventory {'water': 3, 'coin': 2, 'wood': 2}, groups []
- agent-8: DEAD, hp 0, wealth 20, inventory {'coin': 2, 'ore': 2, 'fiber': 1}, groups []
- agent-9: alive, hp 17, wealth 18, inventory {'coin': 3, 'fiber': 3, 'wood': 3}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 385
- Activation position diagnostics: {'early': {'decisions': 232, 'proposed_actions': 718, 'invalid_actions': 118, 'broadcast': 11, 'say': 22, 'offer_trade': 3, 'whisper': 3, 'accept_trade': 1, 'invalid_actions_per_proposed_action_pct': 16.4}, 'middle': {'decisions': 222, 'proposed_actions': 691, 'invalid_actions': 143, 'broadcast': 5, 'say': 23, 'whisper': 3, 'offer_trade': 3, 'invalid_actions_per_proposed_action_pct': 20.7}, 'late': {'decisions': 232, 'proposed_actions': 735, 'invalid_actions': 150, 'say': 33, 'offer_trade': 5, 'broadcast': 5, 'whisper': 2, 'invalid_actions_per_proposed_action_pct': 20.4}}
- Invalid actions: 411 / 2144 proposed (19.2% of proposed actions) | 0.599 per decision
- Invalid categories: {'resource_or_access_unavailable': 349, 'target_or_carry_constraint': 20, 'action_budget_or_energy': 13, 'trade_coordination_or_state': 11, 'other': 10, 'movement_or_occupancy': 8}
- Observation attribution: {'known_invalid_from_observation': 218, 'potential_same_tick_or_plan_state_change': 132, 'not_classified': 37, 'known_constraint_or_plan_sequence': 13, 'coordination_state_uncertain': 11}
- LLM failure events: 5
- Decision quality: degraded | failure rate 0.73% | flags ['decision_failures_present', 'missing_usage_records']
