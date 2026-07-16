# Run report: run

- Ticks: 50/50
- Agents: 3 living / 2 dead
- Action points/tick: 4 | seed: 41
- LLM: 217 calls, $0, 62.7% cache hit
- Per call: 12851.2 input tokens (4791.3 uncached), 343.4 output tokens; agent context chars static/dynamic 6430.0/2700.6
- Simulation plan credits: 41.544555 exact run-scoped credits (input 25.992875 + cached 4.37248 + output 11.1792)
- Codex plan [codex]: primary 52% to 79%, delta +27pp | secondary 30% to 34%, delta +4pp | credits 2658.8093750000 to 2658.8093750000 (delta 0E-10)
- Codex plan [GPT-5.3-Codex-Spark]: primary 0% to 0%, window reset/changed | secondary 0% to 0%, window reset/changed

## Society
- Groups: 0
- Structures complete: {} | co-op builds: 0
- Ownership: {}

## Economy
- Gifts: 5 {'agent-5->agent-3': 3, 'agent-4->agent-1': 2}
- Gift flow: 5 units / 7 book value | subsistence/material units: 5/0 | group status: {'in_group': 0, 'out_group': 5, 'unknown': 0}
- Trades: 0 offered / 0 accepted / 0 expired | conversion: 0.0% | invalid accepts: 0
- Construction contributions: 0 value | productive assets: 0
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 25 | tile claims: 0 | access grants: 0

## Milestones (first tick)
- gift: t25, death: t32

## Agents
- agent-1: alive, hp 55, wealth 22, inventory {'food': 1, 'coin': 4, 'fiber': 8}, groups []
- agent-2: alive, hp 6, wealth 19, inventory {'coin': 4, 'wood': 3, 'fiber': 3}, groups []
- agent-3: DEAD, hp 0, wealth 17, inventory {'water': 2, 'coin': 4, 'ore': 1, 'wood': 1}, groups []
- agent-4: alive, hp 34, wealth 16, inventory {'food': 1, 'water': 2, 'coin': 4, 'fiber': 4}, groups []
- agent-5: DEAD, hp 0, wealth 20, inventory {'coin': 4, 'fiber': 8}, groups []

## Reliability
- Invalid actions: 112 (16.1% of events)
- LLM failure events: 2
- Decision quality: degraded | failure rate 0.91% | flags ['decision_failures_present', 'missing_usage_records']
