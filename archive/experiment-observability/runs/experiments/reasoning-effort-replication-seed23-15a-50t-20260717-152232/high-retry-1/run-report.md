# Run report: run

- Ticks: 42/50 — **stopped early: interrupted**
- Agents: 15 living / 0 dead
- Action points/tick: 4 | seed: 23
- LLM: 642 calls, $0, 59.1% cache hit
- Per call: 13909.1 input tokens (5693.5 uncached), 633.7 output tokens; agent context chars static/dynamic 6493.0/3295.3
- Simulation plan credits: 453.798088 exact run-scoped credits (input 275.093738 + cached 37.2368 + output 141.46755)

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 212 calls, 3 gifts, 9 offers/2 accepts
- cohort-2: gpt-5.6-terra — 5/5 living, 215 calls, 0 gifts, 7 offers/0 accepts
- cohort-3: gpt-5.6-luna — 5/5 living, 215 calls, 1 gifts, 9 offers/6 accepts

## Occupations
- generalist: 15/15 living, 16.7% proposed actions invalid, 25 offers/8 accepts, 4 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 3, 'storage': 1} | co-op builds: 0
- Ownership: {'agent-5': 1, 'agent-9': 1, 'agent-15': 1, 'agent-14': 1}

## Economy
- Gifts: 4 {'agent-2->agent-12': 1, 'agent-9->agent-12': 2, 'agent-15->agent-4': 1}
- Gift flow: 4 units / 7 book value | subsistence/material units: 4/0 | group status: {'in_group': 0, 'out_group': 4, 'unknown': 0}
- Trades: 25 offered / 8 accepted / 16 expired | conversion: 32.0% | invalid accepts: 23
- Trade funnel: 25 offers observed by counterparties / 19 attempted / 19 reached settlement checks / 8 completed | expired without attempt: 5
- Construction contributions: 46 value | productive assets: 4
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 33 | tile claims: 0 | access grants: 2

## Milestones (first tick)
- craft: t4, offer_trade: t9, accept_trade: t20, build: t21, grant_access: t24, gift: t36

## Agents
- agent-1: alive, hp 95, wealth 22, inventory {'coin': 4, 'fiber': 4, 'food': 5}, groups []
- agent-10: alive, hp 60, wealth 16, inventory {'coin': 2, 'fiber': 4, 'wood': 2}, groups []
- agent-11: alive, hp 95, wealth 21, inventory {'coin': 4, 'fiber': 7, 'food': 1, 'water': 1}, groups []
- agent-12: alive, hp 36, wealth 15, inventory {'coin': 3, 'fiber': 2, 'water': 2, 'wood': 2}, groups []
- agent-13: alive, hp 37, wealth 11, inventory {'coin': 3, 'fiber': 3, 'water': 2}, groups []
- agent-14: alive, hp 75, wealth 16, inventory {'coin': 2, 'fiber': 4, 'wood': 2}, groups []
- agent-15: alive, hp 90, wealth 2, inventory {'coin': 2}, groups []
- agent-2: alive, hp 95, wealth 17, inventory {'coin': 1, 'fiber': 8}, groups []
- agent-3: alive, hp 92, wealth 18, inventory {'coin': 2, 'fiber': 2, 'ore': 1, 'stone': 1}, groups []
- agent-4: alive, hp 86, wealth 22, inventory {'coin': 6, 'fiber': 8}, groups []
- agent-5: alive, hp 87, wealth 17, inventory {'coin': 6, 'fiber': 4, 'water': 3}, groups []
- agent-6: alive, hp 95, wealth 16, inventory {'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-7: alive, hp 65, wealth 19, inventory {'coin': 4, 'fiber': 3, 'wood': 3}, groups []
- agent-8: alive, hp 47, wealth 20, inventory {'coin': 4, 'fiber': 2, 'ore': 1, 'stone': 1}, groups []
- agent-9: alive, hp 90, wealth 17, inventory {'coin': 4, 'fiber': 1, 'food': 1, 'wood': 3}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 309
- Activation position diagnostics: {'early': {'decisions': 210, 'proposed_actions': 678, 'invalid_actions': 127, 'say': 17, 'whisper': 9, 'offer_trade': 7, 'accept_trade': 3, 'broadcast': 1, 'invalid_actions_per_proposed_action_pct': 18.7}, 'middle': {'decisions': 210, 'proposed_actions': 666, 'invalid_actions': 96, 'say': 16, 'offer_trade': 8, 'whisper': 11, 'accept_trade': 2, 'broadcast': 1, 'invalid_actions_per_proposed_action_pct': 14.4}, 'late': {'decisions': 210, 'proposed_actions': 672, 'invalid_actions': 113, 'say': 19, 'whisper': 16, 'offer_trade': 10, 'accept_trade': 3, 'broadcast': 4, 'invalid_actions_per_proposed_action_pct': 16.8}}
- Invalid actions: 336 / 2016 proposed (16.7% of proposed actions) | 0.533 per decision
- Invalid categories: {'resource_or_access_unavailable': 265, 'trade_coordination_or_state': 24, 'target_or_carry_constraint': 23, 'action_budget_or_energy': 9, 'other': 9, 'movement_or_occupancy': 6}
- Observation attribution: {'known_invalid_from_observation': 165, 'potential_same_tick_or_plan_state_change': 110, 'not_classified': 35, 'coordination_state_uncertain': 17, 'known_constraint_or_plan_sequence': 9}
- LLM failure events: 3
- Decision quality: degraded | failure rate 0.48% | flags ['decision_failures_present']
