# Run report: run

- Ticks: 50/50
- Agents: 5 living / 15 dead
- Action points/tick: 4 | seed: 41
- LLM: 805 calls, $0, 60.9% cache hit
- Per call: 13235.5 input tokens (5180.9 uncached), 363.9 output tokens; agent context chars static/dynamic 6430.0/3301.2
- Simulation plan credits: 164.410295 exact run-scoped credits (input 104.264775 + cached 16.20992 + output 43.9356)
- Codex plan [codex]: primary 52% to 81%, delta +29pp | secondary 30% to 34%, delta +4pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed | secondary 0% to 0%, window reset/changed

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 9 {'agent-20->agent-16': 1, 'agent-4->agent-9': 1, 'agent-20->agent-3': 1, 'agent-6->agent-1': 2, 'agent-4->agent-2': 1, 'agent-14->agent-2': 3}
- Gift flow: 9 units / 14 book value | subsistence/material units: 9/0 | group status: {'in_group': 0, 'out_group': 9, 'unknown': 0}
- Trades: 53 offered / 3 accepted / 49 expired | conversion: 5.7% | invalid accepts: 67
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 42 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- offer_trade: t1, accept_trade: t6, gift: t8, death: t20

## Agents
- agent-1: DEAD, hp 0, wealth 19, inventory {'coin': 3, 'fiber': 8}, groups []
- agent-10: DEAD, hp 0, wealth 5, inventory {'coin': 3, 'fiber': 1}, groups []
- agent-11: DEAD, hp 0, wealth 14, inventory {'coin': 3, 'fiber': 4, 'wood': 1}, groups []
- agent-12: DEAD, hp 0, wealth 16, inventory {'coin': 2, 'wood': 4, 'fiber': 1}, groups []
- agent-13: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'ore': 2}, groups []
- agent-14: alive, hp 75, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-15: alive, hp 30, wealth 12, inventory {'water': 2, 'coin': 4, 'fiber': 3}, groups []
- agent-16: DEAD, hp 0, wealth 10, inventory {'food': 1, 'coin': 4, 'fiber': 2}, groups []
- agent-17: DEAD, hp 0, wealth 18, inventory {'coin': 2, 'wood': 2, 'fiber': 5}, groups []
- agent-18: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'ore': 1}, groups []
- agent-19: alive, hp 57, wealth 18, inventory {'water': 2, 'coin': 4, 'fiber': 6}, groups []
- agent-2: DEAD, hp 0, wealth 17, inventory {'food': 1, 'water': 1, 'coin': 4, 'wood': 2, 'fiber': 2}, groups []
- agent-20: alive, hp 23, wealth 20, inventory {'food': 1, 'coin': 4, 'fiber': 7}, groups []
- agent-3: DEAD, hp 0, wealth 18, inventory {'food': 2, 'coin': 4, 'stone': 2, 'fiber': 1}, groups []
- agent-4: alive, hp 55, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []
- agent-5: DEAD, hp 0, wealth 12, inventory {'coin': 4, 'fiber': 4}, groups []
- agent-6: DEAD, hp 0, wealth 8, inventory {'coin': 4, 'fiber': 2}, groups []
- agent-7: DEAD, hp 0, wealth 19, inventory {'coin': 3, 'wood': 2, 'fiber': 5}, groups []
- agent-8: DEAD, hp 0, wealth 4, inventory {'coin': 4}, groups []
- agent-9: DEAD, hp 0, wealth 22, inventory {'coin': 4, 'fiber': 9}, groups []

## Reliability
- Invalid actions: 438 (16.6% of events)
- LLM failure events: 5
- Decision quality: degraded | failure rate 0.64% | flags ['decision_failures_present']
