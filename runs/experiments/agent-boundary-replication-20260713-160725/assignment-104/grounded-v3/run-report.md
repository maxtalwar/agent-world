# Run report: run

- Ticks: 5/5
- Agents: 20 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 100 calls, $0, 62.8% cache hit
- Per call: 9882.8 input tokens (3672.9 uncached), 318.1 output tokens; agent context chars static/dynamic 6598.0/3470.4
- Simulation plan credits: 26.945425 exact run-scoped credits (input 19.83725 + cached 2.5808 + output 4.527375)
- Codex plan [codex]: primary 13% to 13%, delta +0pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: gpt-5.6-luna — 4/4 living, 20 calls, 1 gifts, 1 offers/0 accepts
- cohort-2: claude-sonnet-5 — 4/4 living, 20 calls, 0 gifts, 0 offers/0 accepts
- cohort-3: gpt-5.6-terra — 3/3 living, 15 calls, 0 gifts, 1 offers/0 accepts
- cohort-4: claude-opus-4-8 — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-5: gpt-5.6-sol — 3/3 living, 15 calls, 0 gifts, 0 offers/0 accepts
- cohort-6: fable — 3/3 living, 15 calls, 0 gifts, 2 offers/0 accepts

## Occupations
- generalist: 20/20 living, 13.4% proposed actions invalid, 4 offers/0 accepts, 0 structures

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 1 {'agent-18->agent-3': 1}
- Gift flow: 2 units / 3 book value | subsistence/material units: 2/0 | group status: {'in_group': 0, 'out_group': 1, 'unknown': 0}
- Trades: 4 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 1
- Trade funnel: 4 offers observed by counterparties / 1 attempted / 1 reached settlement checks / 0 completed | expired without attempt: 0
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 0 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- gift: t1, offer_trade: t2

## Agents
- agent-1: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-10: alive, hp 100, wealth 15, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 3}, groups []
- agent-11: alive, hp 100, wealth 19, inventory {'food': 3, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-12: alive, hp 100, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'fiber': 2, 'wood': 2}, groups []
- agent-13: alive, hp 100, wealth 17, inventory {'water': 1, 'coin': 4, 'stone': 1, 'ore': 1}, groups []
- agent-14: alive, hp 100, wealth 9, inventory {'water': 5, 'coin': 4}, groups []
- agent-15: alive, hp 100, wealth 14, inventory {'coin': 4, 'fiber': 5}, groups []
- agent-16: alive, hp 100, wealth 24, inventory {'food': 2, 'coin': 4, 'fiber': 8}, groups []
- agent-17: alive, hp 100, wealth 15, inventory {'food': 1, 'water': 1, 'coin': 4, 'wood': 2, 'fiber': 1}, groups []
- agent-18: alive, hp 95, wealth 13, inventory {'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-19: alive, hp 100, wealth 14, inventory {'water': 2, 'coin': 4, 'fiber': 1, 'wood': 2}, groups []
- agent-2: alive, hp 100, wealth 11, inventory {'food': 3, 'water': 1, 'coin': 4}, groups []
- agent-20: alive, hp 100, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 5}, groups []
- agent-3: alive, hp 100, wealth 8, inventory {'food': 1, 'water': 2, 'coin': 4}, groups []
- agent-4: alive, hp 100, wealth 18, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 5}, groups []
- agent-5: alive, hp 100, wealth 20, inventory {'water': 1, 'coin': 4, 'fiber': 6, 'wood': 1}, groups []
- agent-6: alive, hp 100, wealth 17, inventory {'food': 2, 'water': 1, 'coin': 4, 'fiber': 4}, groups []
- agent-7: alive, hp 100, wealth 10, inventory {'water': 4, 'coin': 4, 'fiber': 1}, groups []
- agent-8: alive, hp 100, wealth 13, inventory {'water': 1, 'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 100, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []

## Reliability
- Invalid actions: 42 / 314 proposed (13.4% of proposed actions) | 0.42 per decision
- Invalid categories: {'resource_or_access_unavailable': 32, 'target_or_carry_constraint': 5, 'action_budget_or_energy': 3, 'trade_coordination_or_state': 2}
- Observation attribution: {'known_invalid_from_observation': 19, 'potential_same_tick_or_plan_state_change': 15, 'not_classified': 5, 'known_constraint_or_plan_sequence': 3}
- LLM failure events: 1
- Decision quality: degraded | failure rate 1.0% | flags ['decision_failures_present']
