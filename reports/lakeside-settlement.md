# The Lakeside Settlement 🏕️

*An Agent World field report — 5 AI agents, 60 turns, $3.31 of inference*

Five GLM-5.2 agents were dropped into a 16×16 survival world with **no goals, no roles, and no instructions** beyond the laws of physics (eat, drink, rest, or die — and heavy buildings need more material than one agent can carry). Everything below emerged on its own.

## What happened

- **t0** — Before anything exists, Agent 2 scouts: *"This spot has water, forest, mountain, and plains nearby. Great settlement location. Let's cooperate — form a group, share labor, build infrastructure."*
- **t1** — Agent 1 founds **lakeside_settlement**. First farm breaks ground.
- **t13–28** — Every agent petitions to join (*"please invite me to group-1 so I can help with shared builds"*). By t28: one polity, five citizens.
- **t19–23** — The first **barn-raising**: Agent 4 stakes a shelter it can't afford alone; four agents ferry wood/stone/fiber until it's done.
- **t39–42** — Three agents raise a **workshop** and deed it to the group.
- **t60** — Ten buildings, zero deaths, everyone prosperous (84–100 HP, four agents carrying crafted tools).

## The economy: gifts beat markets, 27 to 1

The world has a full escrowed trading system. The agents ignored it — 8 offers posted, 1 accepted — and ran the village on **27 outright gifts** instead. The network has a shape: the settlement's *founder* gave 19 of the 27, provisioning the builders. Political leadership and economic redistribution fused into the same agent. It's a chiefdom.

And by the end, **half the town was communal property**: both wells, the shelter, the workshop, and a storage were deeded to the group itself. The engine merely allows group ownership — the agents chose it.

## The experiment

Versus the previous baseline run, agents got **one extra action point per turn** (4 instead of 3) and 50% more time (60 ticks vs 40):

| | Baseline | This run |
|---|---|---|
| Structures | 5 | **10** |
| Heavy co-op builds | 0 | **2** |
| Political groups | 0 | **1 (all 5 members)** |
| Communal buildings | 0 | **5** |

One action point was the difference between subsistence farmers and a town with industry and a government. **Surplus is where society begins.**

Bonus finding: an earlier interrupted timeline on the *same world seed* produced **four rival one-member factions in a single tick** ("Settlement-8-8," "settlers," "settlement," "Settlers"). Same map, same physics, completely different politics — pure path dependence.

## The receipts

300 LLM decisions · ~1.1¢ each · **$3.31 total** · zero deaths · 299/300 calls succeeded. Open-weights model (GLM-5.2 via OpenRouter) at ~1/6th frontier pricing is what makes running whole societies affordable.

*Next experiment: five comfortable agents in surplus used none of the formal institutions available (published rules, recorded agreements). What pressure makes them need law?*
