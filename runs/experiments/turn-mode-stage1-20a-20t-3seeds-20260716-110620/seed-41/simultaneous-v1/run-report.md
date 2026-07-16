# Run report: run

- Ticks: 20/20
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 41
- LLM: 400 calls, $0, 56.6% cache hit
- Per call: 9500.5 input tokens (4121.6 uncached), 373.9 output tokens; agent context chars static/dynamic 6493.0/3399.7
- Simulation plan credits: 119.806108 exact run-scoped credits (input 89.880062 + cached 7.39072 + output 22.535325)
- Codex plan [codex]: primary 1% to 3%, delta +2pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 80 calls, 0 gifts, 0 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 80 calls, 0 gifts, 0 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 60 calls, 0 gifts, 3 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 60 calls, 0 gifts, 17 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 60 calls, 0 gifts, 1 offers/0 accepts
- cohort-6: fable — 3/3 living, 60 calls, 0 gifts, 10 offers/0 accepts

## Occupations
- generalist: 20/20 living, 25.3% proposed actions invalid, 31 offers/0 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 0 {}
- Gift flow: 0 units / 0 book value | subsistence/material units: 0/0 | group status: {'in_group': 0, 'out_group': 0, 'unknown': 0}
- Trades: 31 offered / 0 accepted / 26 expired | conversion: 0.0% | invalid accepts: 14
- Trade funnel: 28 offers observed by counterparties / 8 attempted / 3 reached settlement checks / 0 completed | expired without attempt: 18
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 26 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t2, craft: t13

## Agents
- agent-1: alive, hp 76, wealth 19, inventory {'water': 1, 'coin': 4, 'fiber': 5, 'stone': 1}, groups []
- agent-10: alive, hp 95, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-11: alive, hp 70, wealth 18, inventory {'coin': 4, 'fiber': 5, 'stone': 1}, groups []
- agent-12: alive, hp 100, wealth 11, inventory {'water': 2, 'coin': 4, 'fiber': 1, 'wood': 1}, groups []
- agent-13: alive, hp 100, wealth 14, inventory {'water': 2, 'coin': 4, 'stone': 2}, groups []
- agent-14: alive, hp 100, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-15: alive, hp 70, wealth 22, inventory {'coin': 4, 'fiber': 6, 'wood': 2}, groups []
- agent-16: alive, hp 100, wealth 9, inventory {'water': 5, 'coin': 4}, groups []
- agent-17: alive, hp 80, wealth 5, inventory {'water': 3, 'fiber': 1}, groups []
- agent-18: alive, hp 67, wealth 20, inventory {'ore': 2, 'fiber': 2}, groups []
- agent-19: alive, hp 100, wealth 14, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-2: alive, hp 100, wealth 15, inventory {'coin': 2, 'fiber': 2, 'wood': 3}, groups []
- agent-20: alive, hp 60, wealth 18, inventory {'coin': 4, 'fiber': 7}, groups []
- agent-3: alive, hp 85, wealth 22, inventory {'coin': 4, 'fiber': 3, 'tool': 1}, groups []
- agent-4: alive, hp 100, wealth 21, inventory {'water': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-5: alive, hp 70, wealth 18, inventory {'coin': 4, 'fiber': 7}, groups []
- agent-6: alive, hp 100, wealth 15, inventory {'coin': 1, 'fiber': 4, 'wood': 2}, groups []
- agent-7: alive, hp 88, wealth 16, inventory {'water': 2, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-8: alive, hp 47, wealth 18, inventory {'coin': 2, 'ore': 2}, groups []
- agent-9: alive, hp 100, wealth 20, inventory {'food': 2, 'coin': 4, 'fiber': 6}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 298
- Activation position diagnostics: {'early': {'decisions': 140, 'proposed_actions': 439, 'invalid_actions': 114, 'say': 39, 'offer_trade': 16, 'broadcast': 12, 'invalid_actions_per_proposed_action_pct': 26.0}, 'middle': {'decisions': 120, 'proposed_actions': 363, 'invalid_actions': 99, 'say': 16, 'offer_trade': 5, 'broadcast': 9, 'invalid_actions_per_proposed_action_pct': 27.3}, 'late': {'decisions': 140, 'proposed_actions': 436, 'invalid_actions': 100, 'say': 34, 'broadcast': 20, 'offer_trade': 10, 'whisper': 1, 'invalid_actions_per_proposed_action_pct': 22.9}}
- Invalid actions: 313 / 1238 proposed (25.3% of proposed actions) | 0.782 per decision
- Invalid categories: {'resource_or_access_unavailable': 213, 'action_budget_or_energy': 44, 'trade_coordination_or_state': 19, 'movement_or_occupancy': 18, 'target_or_carry_constraint': 12, 'other': 7}
- Observation attribution: {'known_invalid_from_observation': 153, 'potential_same_tick_or_plan_state_change': 78, 'known_constraint_or_plan_sequence': 44, 'not_classified': 21, 'coordination_state_uncertain': 17}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
