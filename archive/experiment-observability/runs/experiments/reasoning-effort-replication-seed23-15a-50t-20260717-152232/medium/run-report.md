# Run report: run

- Ticks: 50/50
- Agents: 9 living / 6 dead
- Action points/tick: 4 | seed: 23
- LLM: 692 calls, $0, 58.2% cache hit
- Per call: 13934.8 input tokens (5827.9 uncached), 397.2 output tokens; agent context chars static/dynamic 6493.0/3536.0
- Simulation plan credits: 474.359462 exact run-scoped credits (input 322.473438 + cached 39.4176 + output 112.468425)
- Codex plan [codex]: primary 34% to 44%, delta +10pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 240 calls, 5 gifts, 7 offers/3 accepts
- cohort-2: gpt-5.6-terra — 3/5 living, 234 calls, 0 gifts, 6 offers/0 accepts
- cohort-3: gpt-5.6-luna — 1/5 living, 218 calls, 0 gifts, 13 offers/0 accepts

## Occupations
- generalist: 9/15 living, 27.9% proposed actions invalid, 26 offers/3 accepts, 2 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 1, 'storage': 1} | co-op builds: 0
- Ownership: {'agent-15': 2}

## Economy
- Gifts: 5 {'agent-10->agent-15': 1, 'agent-10->agent-4': 1, 'agent-10->agent-2': 1, 'agent-14->agent-9': 1, 'agent-6->agent-9': 1}
- Gift flow: 5 units / 7 book value | subsistence/material units: 5/0 | group status: {'in_group': 0, 'out_group': 5, 'unknown': 0}
- Trades: 26 offered / 3 accepted / 21 expired | conversion: 11.5% | invalid accepts: 19
- Trade funnel: 26 offers observed by counterparties / 13 attempted / 12 reached settlement checks / 3 completed | expired without attempt: 11
- Construction contributions: 26 value | productive assets: 2
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 35 | tile claims: 1 | access grants: 0

## Milestones (first tick)
- claim_tile: t0, offer_trade: t6, build: t8, accept_trade: t22, gift: t25, death: t30, build_started: t40

## Agents
- agent-1: DEAD, hp 0, wealth 17, inventory {'coin': 1, 'fiber': 5, 'wood': 2}, groups []
- agent-10: alive, hp 68, wealth 16, inventory {'coin': 5, 'fiber': 1, 'wood': 3}, groups []
- agent-11: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'ore': 2}, groups []
- agent-12: alive, hp 80, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-13: alive, hp 32, wealth 7, inventory {'water': 2, 'coin': 1, 'fiber': 2}, groups []
- agent-14: alive, hp 40, wealth 19, inventory {'water': 1, 'coin': 4, 'fiber': 4, 'wood': 2}, groups []
- agent-15: alive, hp 90, wealth 20, inventory {'food': 6, 'water': 1, 'coin': 4, 'wood': 1}, groups []
- agent-2: DEAD, hp 0, wealth 20, inventory {'coin': 3, 'fiber': 7, 'wood': 1}, groups []
- agent-3: DEAD, hp 0, wealth 19, inventory {'water': 1, 'coin': 2, 'ore': 2}, groups []
- agent-4: alive, hp 22, wealth 12, inventory {'water': 2, 'coin': 2, 'fiber': 4}, groups []
- agent-5: DEAD, hp 0, wealth 22, inventory {'coin': 3, 'fiber': 8, 'wood': 1}, groups []
- agent-6: alive, hp 60, wealth 19, inventory {'water': 1, 'coin': 3, 'fiber': 6, 'wood': 1}, groups []
- agent-7: alive, hp 70, wealth 15, inventory {'food': 2, 'coin': 4, 'fiber': 2, 'wood': 1}, groups []
- agent-8: DEAD, hp 0, wealth 16, inventory {'water': 2, 'coin': 4, 'ore': 1, 'fiber': 1}, groups []
- agent-9: alive, hp 4, wealth 18, inventory {'coin': 4, 'fiber': 7}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 558
- Activation position diagnostics: {'early': {'decisions': 234, 'proposed_actions': 722, 'invalid_actions': 219, 'say': 35, 'offer_trade': 5, 'whisper': 11, 'accept_trade': 1, 'broadcast': 5, 'invalid_actions_per_proposed_action_pct': 30.3}, 'middle': {'decisions': 234, 'proposed_actions': 740, 'invalid_actions': 192, 'say': 38, 'whisper': 8, 'accept_trade': 2, 'offer_trade': 11, 'broadcast': 9, 'invalid_actions_per_proposed_action_pct': 25.9}, 'late': {'decisions': 234, 'proposed_actions': 737, 'invalid_actions': 202, 'say': 34, 'broadcast': 7, 'offer_trade': 10, 'whisper': 14, 'invalid_actions_per_proposed_action_pct': 27.4}}
- Invalid actions: 613 / 2199 proposed (27.9% of proposed actions) | 0.873 per decision
- Invalid categories: {'resource_or_access_unavailable': 520, 'target_or_carry_constraint': 36, 'trade_coordination_or_state': 21, 'movement_or_occupancy': 15, 'action_budget_or_energy': 13, 'other': 8}
- Observation attribution: {'known_invalid_from_observation': 326, 'potential_same_tick_or_plan_state_change': 214, 'not_classified': 47, 'coordination_state_uncertain': 13, 'known_constraint_or_plan_sequence': 13}
- LLM failure events: 10
- Decision quality: degraded | failure rate 1.42% | flags ['decision_failures_present', 'missing_usage_records']
