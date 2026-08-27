# Run report: run

- Ticks: 50/50
- Agents: 9 living / 21 dead
- Action points/tick: 4 | seed: 11
- LLM: 652 calls, $0, 59.8% cache hit
- Per call: 12779.1 input tokens (5130.9 uncached), 322.0 output tokens; agent context chars static/dynamic 6430.0/3167.1
- Simulation plan credits: 176.906372 exact run-scoped credits (input 120.591438 + cached 17.06016 + output 39.254775)
- Codex plan [codex]: primary 7% to 17%, delta +10pp | secondary 1% to 3%, delta +2pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed | secondary 0% to 0%, window reset/changed

## Model cohorts
- cohort-1: claude-sonnet-5 — 0/10 living, 0 calls, 0 gifts, 0 offers/0 accepts
- cohort-2: gpt-5.6-luna — 9/10 living, 490 calls, 19 gifts, 7 offers/0 accepts
- cohort-3: claude-opus-4-8 — 0/5 living, 0 calls, 0 gifts, 0 offers/0 accepts
- cohort-4: gpt-5.6-terra — 0/5 living, 162 calls, 1 gifts, 8 offers/0 accepts

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 20 {'agent-14->agent-4': 2, 'agent-21->agent-16': 2, 'agent-21->agent-1': 1, 'agent-12->agent-22': 1, 'agent-10->agent-15': 1, 'agent-14->agent-24': 1, 'agent-5->agent-10': 1, 'agent-19->agent-21': 5, 'agent-14->agent-26': 1, 'agent-12->agent-9': 3, 'agent-14->agent-17': 2}
- Gift flow: 26 units / 34 book value | subsistence/material units: 24/2 | group status: {'in_group': 0, 'out_group': 20, 'unknown': 0}
- Trades: 15 offered / 0 accepted / 15 expired | conversion: 0.0% | invalid accepts: 13
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 70 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t3, gift: t5, death: t16

## Agents
- agent-1: DEAD, hp 0, wealth 10, inventory {'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-10: DEAD, hp 0, wealth 14, inventory {'water': 2, 'fiber': 6}, groups []
- agent-11: DEAD, hp 0, wealth 10, inventory {'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-12: alive, hp 39, wealth 17, inventory {'water': 2, 'coin': 4, 'wood': 1, 'fiber': 4}, groups []
- agent-13: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-14: alive, hp 35, wealth 15, inventory {'water': 3, 'coin': 4, 'fiber': 4}, groups []
- agent-15: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-16: DEAD, hp 0, wealth 11, inventory {'water': 3, 'coin': 4, 'fiber': 2}, groups []
- agent-17: alive, hp 80, wealth 16, inventory {'coin': 4, 'fiber': 6}, groups []
- agent-18: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-19: alive, hp 75, wealth 8, inventory {'water': 2, 'coin': 4, 'fiber': 1}, groups []
- agent-2: DEAD, hp 0, wealth 22, inventory {'food': 3, 'coin': 4, 'fiber': 6}, groups []
- agent-20: alive, hp 4, wealth 18, inventory {'coin': 4, 'fiber': 4, 'wood': 2}, groups []
- agent-21: alive, hp 72, wealth 20, inventory {'food': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-22: DEAD, hp 0, wealth 13, inventory {'water': 3, 'coin': 4, 'wood': 2}, groups []
- agent-23: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-24: DEAD, hp 0, wealth 10, inventory {'food': 2, 'water': 2, 'coin': 4}, groups []
- agent-25: DEAD, hp 0, wealth 16, inventory {'coin': 4, 'fiber': 3, 'wood': 2}, groups []
- agent-26: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []
- agent-27: DEAD, hp 0, wealth 12, inventory {'water': 2, 'coin': 4, 'wood': 2}, groups []
- agent-28: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-29: DEAD, hp 0, wealth 8, inventory {'food': 1, 'water': 2, 'coin': 4}, groups []
- agent-3: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-30: DEAD, hp 0, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []
- agent-4: DEAD, hp 0, wealth 11, inventory {'food': 2, 'water': 3, 'coin': 4}, groups []
- agent-5: alive, hp 11, wealth 16, inventory {'water': 1, 'coin': 3, 'fiber': 6}, groups []
- agent-6: DEAD, hp 0, wealth 10, inventory {'water': 2, 'coin': 4, 'fiber': 2}, groups []
- agent-7: alive, hp 35, wealth 15, inventory {'coin': 4, 'wood': 3, 'fiber': 1}, groups []
- agent-8: DEAD, hp 0, wealth 14, inventory {'water': 2, 'coin': 4, 'ore': 1}, groups []
- agent-9: alive, hp 42, wealth 21, inventory {'water': 1, 'coin': 4, 'fiber': 8}, groups []

## Reliability
- Invalid actions: 375 (13.5% of events)
- LLM failure events: 270
- Decision quality: degraded | failure rate 29.28% | flags ['decision_failures_present', 'missing_usage_records']
