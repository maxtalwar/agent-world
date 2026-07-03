# Agent Interface

Agents receive a local observation each tick and return a structured decision. They never mutate state directly. The world engine validates every proposed action.

## Prompt Principle

Prompts expose constraints and affordances, not goals. They should not instruct agents to trade, cooperate, build, form firms, create laws, or optimize wealth.

The LLM brings its own prior knowledge. The experiment is whether the world makes concepts like trade, storage, property, and governance useful enough for agents to choose them.

## Observation Contents

Current top-level observation keys:

- `tick`
- `world`
- `self`
- `local_map`
- `visible_agents`
- `recent_events`
- `recent_action_feedback`
- `memory`
- `open_trades`
- `known_groups`
- `action_format`
- `valid_actions`

Agents know their own:

- position
- health/alive state
- food/water/energy reserves, where higher is better and `0` is danger
- inventory
- carry weight and carry capacity
- skills
- equipped items
- groups, relationships, and reputation

Agents see only local map tiles within visibility radius. They do not see the full map, hidden private memories, or private prompts/observations from other agents.

The `world` object includes terrain passability and recipes with required terrain/tools. It does not include exact terrain yield, regeneration, structure productivity, spoilage cadence, or current build recommendations.

## Explicitly Not Included

Agent observations do not include `buildable_structures_here` or other "you can afford X now" hints. Build readiness exists in researcher diagnostics only.

## Decision Shape

Agents return:

```json
{
  "intent": "short reason",
  "actions": [
    { "type": "move", "direction": "east" }
  ],
  "messages": [
    { "mode": "say", "text": "I found food east of camp." }
  ],
  "memory_updates": [
    "The eastern plains still have food."
  ]
}
```

Invalid actions fail explicitly and are logged. A failed action does not mutate world state.

Action objects are flat JSON objects. Arguments go directly beside `type`; do not nest them under `fields`, `parameters`, or `example`.

Valid:

```json
{ "type": "move", "direction": "east" }
```

Invalid:

```json
{ "type": "move", "fields": { "direction": "east" } }
```

## OpenAI Adapter

`agent_world/openai_brain.py` calls the OpenAI Responses API. It uses:

- compact JSON prompt formatting to remove whitespace only
- structured JSON output schema
- retry handling for rate limits
- request throttling
- sequential LLM calls by default to avoid token-per-minute bursts

Prompt compaction does not remove observation fields.
