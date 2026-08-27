# Run report: live

- Ticks: 60/60
- Agents: 5 living / 0 dead
- Action points/tick: 4 | seed: 11
- LLM: 299 calls, $3.3137, 42.8% cache hit

## Society
- Groups: 1 — lakeside_settlement (5 members)
- Structures complete: {'farm_plot': 3, 'well': 2, 'storage': 3, 'shelter': 1, 'workshop': 1} | co-op builds: 2
- Ownership: {'agent-2': 2, 'group-1': 6, 'agent-5': 2}

## Economy
- Gifts: 27 {'agent-4->agent-5': 1, 'agent-2->agent-4': 1, 'agent-2->agent-5': 3, 'agent-3->agent-5': 1, 'agent-3->agent-4': 1, 'agent-1->agent-3': 9, 'agent-1->agent-4': 5, 'agent-4->agent-3': 1, 'agent-1->agent-2': 1, 'agent-1->agent-5': 4}
- Gift flow: 29 units / 49 book value | subsistence/material units: 23/6 | group status: {'in_group': 22, 'out_group': 5, 'unknown': 0}
- Trades: 8 offered / 1 accepted / 6 expired | conversion: 12.5% | invalid accepts: 2
- Construction contributions: 97 value | productive assets: 10
- Contracts: 0 offered / 0 fulfilled / 0 defaulted | access-fee value: 0 | dividend value: 0
- Food spoilage events: 23 | tile claims: 0 | access grants: 7

## Milestones (first tick)
- create_group: t1, build: t1, gift: t4, grant_access: t6, offer_trade: t6, craft: t8, accept_trade: t8, join_group: t13, build_started: t19

## Agents
- agent-1: alive, hp 100, wealth 14, inventory {'food': 1, 'tool': 1}, groups ['group-1']
- agent-2: alive, hp 100, wealth 2, inventory {'food': 1}, groups ['group-1']
- agent-3: alive, hp 84, wealth 19, inventory {'food': 2, 'tool': 1, 'wood': 1}, groups ['group-1']
- agent-4: alive, hp 100, wealth 20, inventory {'ore': 1, 'tool': 1}, groups ['group-1']
- agent-5: alive, hp 87, wealth 16, inventory {'food': 2, 'tool': 1}, groups ['group-1']

## Reliability
- Invalid actions: 88 (6.3% of events)
- LLM failure events: 1
