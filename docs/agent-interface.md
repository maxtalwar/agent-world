# Agent Interface

Agents receive a local observation each tick and return a structured decision. They never mutate state directly. The world engine validates every proposed action.

Turn timing is a versioned infrastructure treatment and is not disclosed in the model
prompt. In `simultaneous-v1`, every agent decides from the same pre-resolution state and
the engine resolves decisions in rotating order. In `shuffled-sequential-v1`, agents are
deterministically reshuffled each tick; each agent observes and resolves immediately, so
later agents can see earlier movement, speech, offers, and resource changes. Neither
mode changes action rules or enables remote exchange.

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

The `world` object includes treatment modes, coordination costs, terrain passability, recipes, and required terrain/tools/structures. It does not include exact terrain yield, regeneration probabilities, spoilage cadence, or current build recommendations.

Agents also receive visible standing offers, completed market-price history, and contracts to which they are a party. In organic mode, public offers and price history are local, trade summaries include a physical `escrow_position`, and engine-enforced contract actions are absent. Public structures expose access fees, capacity, upkeep state, treasury, and contributor shares.

## Versioned Model-Facing Boundaries

The full observation above is the engine's canonical private view. The model-facing
rendering is a selectable, manifest-recorded experimental treatment:

- `compact-v2` is the control. It sends the slim local map and self state used by prior runs.
- `body-only-v3` adds only a three-value `body` summary: start-of-tick action points,
  current energy, and remaining carry capacity.
- `indexed-v3` adds the same compact `body` summary and labels the already-present
  current/cardinal map entries with `rel: here|north|east|south|west`. It does not
  repeat those tiles or their contents.
- `grounded-v3` retains that complete compact view and additionally repeats three literal
  embodiment summaries: `body` (start-of-tick action points, energy, and remaining carry
  capacity), `here` (the current tile), and `adjacent` (north/east/south/west tiles with
  passability and movement cost).

None of these treatments enumerate legal actions, recommend a plan, identify profitable
opportunities, or repair proposed actions. They vary only how already-visible physical
facts are indexed or repeated while leaving strategy and validation to the agent and
engine. Select one with `--observation-mode`; omitted runs remain on `compact-v2` for
historical comparability.

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

`agent_world/openai_brain.py` calls either OpenAI's Responses API or an OpenAI-compatible Chat Completions API such as OpenRouter. It uses:

- compact JSON prompt formatting to remove whitespace only
- structured JSON output schema
- retry handling for rate limits
- request throttling
- sequential LLM calls by default to avoid token-per-minute bursts

Prompt compaction does not remove observation fields.

## Codex CLI Adapter

`agent_world/codex_brain.py` invokes `codex exec` once per living agent per tick.
Calls are ephemeral, read-only, schema-constrained, and isolated from the project
and from other simulated agents. API-key environment variables are removed from
the child process so saved ChatGPT authentication supplies the Codex-plan usage.
The simulation remains responsible for memory; the Codex process receives the
same compact static rulebook and current dynamic observation used by API brains.
