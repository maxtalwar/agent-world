# Run report: run

- Ticks: 50/50
- Agents: 9 living / 6 dead
- Action points/tick: 4 | seed: 23
- LLM: 697 calls, $0, 63.5% cache hit
- Per call: 13910.5 input tokens (5077.3 uncached), 308.8 output tokens; agent context chars static/dynamic 6493.0/3444.0
- Simulation plan credits: 409.300525 exact run-scoped credits (input 271.527975 + cached 45.1504 + output 92.62215)
- Codex plan [codex]: primary 34% to 43%, delta +9pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-sol — 5/5 living, 244 calls, 8 gifts, 12 offers/6 accepts
- cohort-2: gpt-5.6-terra — 2/5 living, 232 calls, 1 gifts, 8 offers/0 accepts
- cohort-3: gpt-5.6-luna — 2/5 living, 221 calls, 0 gifts, 8 offers/0 accepts

## Occupations
- generalist: 9/15 living, 20.3% proposed actions invalid, 28 offers/6 accepts, 1 structures

## Society
- Groups: 0
- Structures complete: {'farm_plot': 1} | co-op builds: 0
- Ownership: {'agent-14': 1}

## Economy
- Gifts: 9 {'agent-14->agent-13': 4, 'agent-14->agent-8': 1, 'agent-13->agent-1': 1, 'agent-9->agent-4': 1, 'agent-14->agent-1': 1, 'agent-14->agent-6': 1}
- Gift flow: 11 units / 20 book value | subsistence/material units: 11/0 | group status: {'in_group': 0, 'out_group': 9, 'unknown': 0}
- Trades: 28 offered / 6 accepted / 19 expired | conversion: 21.4% | invalid accepts: 18
- Trade funnel: 27 offers observed by counterparties / 17 attempted / 11 reached settlement checks / 6 completed | expired without attempt: 8
- Construction contributions: 10 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 45 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t2, craft: t3, accept_trade: t14, build: t19, gift: t24, death: t32

## Agents
- agent-1: DEAD, hp 0, wealth 21, inventory {'coin': 4, 'fiber': 7, 'wood': 1}, groups []
- agent-10: alive, hp 90, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-11: alive, hp 74, wealth 18, inventory {'coin': 2, 'fiber': 8}, groups []
- agent-12: alive, hp 51, wealth 22, inventory {'coin': 4, 'wood': 2, 'fiber': 6}, groups []
- agent-13: DEAD, hp 0, wealth 17, inventory {'coin': 3, 'stone': 2, 'fiber': 3}, groups []
- agent-14: alive, hp 100, wealth 19, inventory {'food': 3, 'water': 2, 'coin': 7, 'fiber': 2}, groups []
- agent-15: alive, hp 60, wealth 20, inventory {'food': 1, 'coin': 2, 'fiber': 8}, groups []
- agent-2: DEAD, hp 0, wealth 22, inventory {'coin': 4, 'wood': 2, 'fiber': 6}, groups []
- agent-3: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'ore': 1, 'fiber': 4}, groups []
- agent-4: DEAD, hp 0, wealth 22, inventory {'food': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-5: alive, hp 10, wealth 15, inventory {'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-6: alive, hp 24, wealth 14, inventory {'coin': 1, 'fiber': 2, 'wood': 3}, groups []
- agent-7: alive, hp 75, wealth 12, inventory {'food': 1, 'water': 4, 'coin': 4, 'fiber': 1}, groups []
- agent-8: DEAD, hp 0, wealth 18, inventory {'coin': 2, 'fiber': 8}, groups []
- agent-9: alive, hp 80, wealth 19, inventory {'coin': 4, 'fiber': 3, 'wood': 3}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 416
- Activation position diagnostics: {'early': {'decisions': 237, 'proposed_actions': 764, 'invalid_actions': 143, 'say': 29, 'offer_trade': 8, 'broadcast': 11, 'whisper': 4, 'accept_trade': 1, 'invalid_actions_per_proposed_action_pct': 18.7}, 'middle': {'decisions': 229, 'proposed_actions': 727, 'invalid_actions': 156, 'offer_trade': 13, 'say': 29, 'accept_trade': 3, 'broadcast': 7, 'whisper': 2, 'invalid_actions_per_proposed_action_pct': 21.5}, 'late': {'decisions': 237, 'proposed_actions': 730, 'invalid_actions': 152, 'offer_trade': 7, 'say': 40, 'whisper': 6, 'accept_trade': 2, 'broadcast': 3, 'invalid_actions_per_proposed_action_pct': 20.8}}
- Invalid actions: 451 / 2221 proposed (20.3% of proposed actions) | 0.642 per decision
- Invalid categories: {'resource_or_access_unavailable': 373, 'target_or_carry_constraint': 25, 'trade_coordination_or_state': 20, 'action_budget_or_energy': 17, 'movement_or_occupancy': 10, 'other': 6}
- Observation attribution: {'known_invalid_from_observation': 262, 'potential_same_tick_or_plan_state_change': 123, 'not_classified': 32, 'known_constraint_or_plan_sequence': 17, 'coordination_state_uncertain': 17}
- LLM failure events: 6
- Decision quality: degraded | failure rate 0.85% | flags ['decision_failures_present', 'missing_usage_records']
