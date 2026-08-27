# Run report: run

- Ticks: 20/20
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 23
- LLM: 400 calls, $0, 60.9% cache hit
- Per call: 9381.7 input tokens (3663.6 uncached), 385.6 output tokens; agent context chars static/dynamic 6493.0/3225.3
- Simulation plan credits: 106.457438 exact run-scoped credits (input 75.658112 + cached 8.84 + output 21.959325)
- Codex plan [codex]: primary 6% to 8%, delta +2pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 80 calls, 0 gifts, 4 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 80 calls, 0 gifts, 3 offers/1 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 60 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 60 calls, 0 gifts, 12 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 60 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 60 calls, 1 gifts, 4 offers/1 accepts

## Occupations
- generalist: 20/20 living, 26.2% proposed actions invalid, 23 offers/2 accepts, 1 structures

## Society
- Groups: 0
- Structures complete: {'storage': 1} | co-op builds: 0
- Ownership: {'agent-5': 1}

## Economy
- Gifts: 1 {'agent-5->agent-10': 1}
- Gift flow: 4 units / 4 book value | subsistence/material units: 0/4 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 23 offered / 2 accepted / 19 expired | conversion: 8.7% | invalid accepts: 4
- Trade funnel: 23 offers observed by counterparties / 5 attempted / 3 reached settlement checks / 2 completed | expired without attempt: 17
- Construction contributions: 16 value | productive assets: 1
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 27 | tile claims: 0 | access grants: 1

## Milestones (first tick)
- offer_trade: t3, accept_trade: t9, build: t10, grant_access: t11, gift: t18

## Agents
- agent-1: alive, hp 81, wealth 15, inventory {'food': 2, 'coin': 4, 'fiber': 2, 'wood': 1}, groups []
- agent-10: alive, hp 95, wealth 28, inventory {'coin': 8, 'fiber': 10}, groups []
- agent-11: alive, hp 100, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-12: alive, hp 100, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []
- agent-13: alive, hp 52, wealth 20, inventory {'coin': 4, 'ore': 1, 'stone': 2}, groups []
- agent-14: alive, hp 100, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-15: alive, hp 95, wealth 9, inventory {'water': 5, 'coin': 4}, groups []
- agent-16: alive, hp 100, wealth 18, inventory {'food': 1, 'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-17: alive, hp 90, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-18: alive, hp 85, wealth 17, inventory {'water': 1, 'coin': 2, 'fiber': 7}, groups []
- agent-19: alive, hp 100, wealth 19, inventory {'coin': 4, 'fiber': 3, 'wood': 3}, groups []
- agent-2: alive, hp 64, wealth 21, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-20: alive, hp 65, wealth 14, inventory {'coin': 4, 'fiber': 5}, groups []
- agent-3: alive, hp 52, wealth 24, inventory {'coin': 4, 'ore': 1, 'fiber': 6}, groups []
- agent-4: alive, hp 72, wealth 5, inventory {'food': 1, 'coin': 3}, groups []
- agent-5: alive, hp 90, wealth 8, inventory {'fiber': 4}, groups []
- agent-6: alive, hp 95, wealth 24, inventory {'coin': 4, 'fiber': 10}, groups []
- agent-7: alive, hp 85, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []
- agent-8: alive, hp 61, wealth 0, inventory {}, groups []
- agent-9: alive, hp 70, wealth 20, inventory {'coin': 4, 'fiber': 5, 'wood': 2}, groups []

## Reliability
- Turn mode: simultaneous-v1 | observations seeing earlier same-tick events: 0 | potential stale invalids after unobserved prior resolutions: 331
- Activation position diagnostics: {'early': {'decisions': 140, 'proposed_actions': 450, 'invalid_actions': 113, 'say': 53, 'offer_trade': 5, 'accept_trade': 1, 'whisper': 1, 'broadcast': 11, 'invalid_actions_per_proposed_action_pct': 25.1}, 'middle': {'decisions': 120, 'proposed_actions': 378, 'invalid_actions': 106, 'say': 49, 'offer_trade': 9, 'whisper': 1, 'broadcast': 3, 'invalid_actions_per_proposed_action_pct': 28.0}, 'late': {'decisions': 140, 'proposed_actions': 467, 'invalid_actions': 120, 'say': 41, 'broadcast': 20, 'offer_trade': 9, 'accept_trade': 1, 'whisper': 1, 'invalid_actions_per_proposed_action_pct': 25.7}}
- Invalid actions: 339 / 1295 proposed (26.2% of proposed actions) | 0.848 per decision
- Invalid categories: {'resource_or_access_unavailable': 240, 'action_budget_or_energy': 56, 'target_or_carry_constraint': 18, 'other': 13, 'movement_or_occupancy': 7, 'trade_coordination_or_state': 5}
- Observation attribution: {'known_invalid_from_observation': 153, 'potential_same_tick_or_plan_state_change': 94, 'known_constraint_or_plan_sequence': 56, 'not_classified': 32, 'coordination_state_uncertain': 4}
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
