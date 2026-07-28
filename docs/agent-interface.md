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
- treatment-specific specialty, aptitudes, asymmetric needs, and equipped-tool durability

Agents see only local map tiles within visibility radius. They do not see the full map, hidden private memories, or private prompts/observations from other agents.

The default `baseline` feedback treatment supplies up to five recent failed actions and their existing engine explanations. `causal` preserves that payload and adds a neutral explanation when structured evidence proves another agent changed the relevant shared state earlier in the tick; it never names the competing agent. `minimal` reports only failed action types from the immediately preceding tick. `none` removes the payload, prompt instruction, and private failure events from the agent's recent-event stream while retaining them in researcher logs. Researcher reports distinguish invalid proposals from same-tick contention failures; this classification does not repair actions or alter outcomes.

The `world` object includes treatment modes, coordination costs, terrain passability, recipes, and required terrain/tools/structures. It does not include exact terrain yield, regeneration probabilities, spoilage cadence, or current build recommendations.

Agents also receive visible standing offers, completed market-price history, and contracts to which they are a party. In organic mode, public offers and price history are local, trade summaries include a physical `escrow_position`, and engine-enforced contract actions are absent. Public structures expose access fees, capacity, upkeep state, treasury, and contributor shares.

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

## OpenRouter Adapter

`agent_world/openrouter_brain.py` calls OpenRouter's Chat Completions API.
OpenAI `gpt-*` models route through `CodexBrain` by default instead. The
OpenRouter connector uses:

- compact JSON prompt formatting to remove whitespace only
- structured JSON output schema
- retry handling for rate limits
- request throttling
- sequential LLM calls by default to avoid token-per-minute bursts

Prompt compaction does not remove observation fields.

## Codex CLI Adapter

`agent_world/codex_brain.py` invokes `codex exec` once per living agent per tick.
Calls are read-only, schema-constrained, and isolated from the project and from
other simulated agents. Depending on the explicit conversation mode, a call is
either ephemeral or resumes that agent's bounded private session. API-key environment variables are removed from
the child process so saved ChatGPT authentication supplies the Codex-plan usage.
The simulation remains responsible for memory; the Codex process receives the
same compact static rulebook and current dynamic observation used by API brains.
