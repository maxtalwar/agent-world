# Run report: run

- Ticks: 50/50
- Agents: 17 living / 13 dead
- Action points/tick: 4 | seed: 11
- LLM: 1287 calls, $0, 59.2% cache hit
- Per call: 9880.8 input tokens (4035.0 uncached), 358.6 output tokens; agent context chars static/dynamic 6430.0/4478.4
- Simulation plan credits: 187.44015 exact run-scoped credits (input 131.748225 + cached 17.7648 + output 37.927125)
- Codex plan [codex]: primary 1% to 9%, delta +8pp | secondary 4% to 5%, delta +1pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed | secondary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: claude-sonnet-5 — 6/10 living, 410 calls, 0 gifts, 34 offers/0 accepts
- cohort-2: gpt-5.6-luna — 5/10 living, 452 calls, 6 gifts, 30 offers/1 accepts
- cohort-3: claude-opus-4-8 — 4/5 living, 234 calls, 2 gifts, 18 offers/7 accepts
- cohort-4: gpt-5.6-terra — 2/5 living, 191 calls, 0 gifts, 12 offers/0 accepts

## Society
- Groups: 0
- Structures complete: {'farm_plot': 3} | co-op builds: 0
- Ownership: {'agent-16': 1, 'agent-11': 1, 'agent-12': 1}

## Economy
- Gifts: 8 {'agent-20->agent-5': 1, 'agent-1->agent-10': 1, 'agent-29->agent-11': 1, 'agent-2->agent-5': 1, 'agent-12->agent-27': 1, 'agent-5->agent-15': 2, 'agent-15->agent-5': 1}
- Gift flow: 10 units / 15 book value | subsistence/material units: 7/3 | group status: {'in_group': 0, 'out_group': 8, 'unknown': 0}
- Trades: 94 offered / 8 accepted / 80 expired | conversion: 8.5% | invalid accepts: 79
- Construction contributions: 30 value | productive assets: 3
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 66 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- gift: t1, offer_trade: t2, build: t10, build_started: t12, accept_trade: t16, death: t21

## Agents
- agent-1: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-10: alive, hp 15, wealth 18, inventory {'coin': 2, 'fiber': 8}, groups []
- agent-11: alive, hp 60, wealth 9, inventory {'water': 3, 'coin': 2, 'fiber': 2}, groups []
- agent-12: alive, hp 75, wealth 19, inventory {'food': 2, 'water': 1, 'coin': 8, 'wood': 2}, groups []
- agent-13: alive, hp 11, wealth 4, inventory {'water': 4}, groups []
- agent-14: alive, hp 12, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 10, wealth 1, inventory {'water': 1}, groups []
- agent-16: alive, hp 90, wealth 22, inventory {'food': 1, 'coin': 8, 'fiber': 6}, groups []
- agent-17: alive, hp 40, wealth 12, inventory {'food': 2, 'coin': 2, 'fiber': 3}, groups []
- agent-18: DEAD, hp 0, wealth 1, inventory {'water': 1}, groups []
- agent-19: alive, hp 29, wealth 6, inventory {'water': 2, 'coin': 4}, groups []
- agent-2: DEAD, hp 0, wealth 13, inventory {'food': 1, 'wood': 1, 'fiber': 4}, groups []
- agent-20: alive, hp 2, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-21: DEAD, hp 0, wealth 23, inventory {'coin': 3, 'fiber': 10}, groups []
- agent-22: DEAD, hp 0, wealth 19, inventory {'coin': 4, 'wood': 3, 'fiber': 3}, groups []
- agent-23: DEAD, hp 0, wealth 2, inventory {'food': 1}, groups []
- agent-24: alive, hp 30, wealth 8, inventory {'fiber': 4}, groups []
- agent-25: DEAD, hp 0, wealth 14, inventory {'water': 1, 'fiber': 5, 'wood': 1}, groups []
- agent-26: DEAD, hp 0, wealth 16, inventory {'fiber': 8}, groups []
- agent-27: alive, hp 11, wealth 5, inventory {'water': 1, 'fiber': 2}, groups []
- agent-28: DEAD, hp 0, wealth 18, inventory {'coin': 2, 'ore': 1, 'stone': 2}, groups []
- agent-29: alive, hp 74, wealth 16, inventory {'water': 1, 'coin': 5, 'fiber': 5}, groups []
- agent-3: DEAD, hp 0, wealth 20, inventory {'food': 4, 'coin': 4, 'ore': 1}, groups []
- agent-30: alive, hp 19, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-4: alive, hp 30, wealth 7, inventory {'coin': 1, 'fiber': 3}, groups []
- agent-5: alive, hp 33, wealth 20, inventory {'fiber': 10}, groups []
- agent-6: DEAD, hp 0, wealth 0, inventory {}, groups []
- agent-7: DEAD, hp 0, wealth 20, inventory {'food': 1, 'coin': 3, 'wood': 3, 'fiber': 3}, groups []
- agent-8: DEAD, hp 0, wealth 24, inventory {'coin': 4, 'ore': 2, 'fiber': 2}, groups []
- agent-9: alive, hp 79, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []

## Reliability
- Invalid actions: 1417 (27.5% of events)
- LLM failure events: 0
- Decision quality: clean | failure rate 0.0% | flags []
