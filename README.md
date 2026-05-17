# Agent World

Agent World is a deterministic, tick-based 2D simulation substrate for observing autonomous LLM agents inside a constrained world. Agents are not told to form markets, governments, firms, or social structures. They receive local observations, their own state, remembered facts, and a strict JSON action interface. The world engine validates and resolves every proposed action.

The first milestone is a survival economy: movement, needs, scarce resources, extraction, crafting, ownership, storage, trade, speech, groups, and public records.

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m agent_world.cli run --ticks 25 --agents 5 --seed 7 --out runs/example.jsonl
python3 -m agent_world.cli replay runs/example.jsonl --last 30
python3 -m agent_world.cli prompt --seed 7 --agents 2 --agent agent-1
```

The default CLI run uses deterministic mock brains so the infrastructure can be tested without an LLM key.

## OpenAI Agents

Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
```

```dotenv
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_TIMEOUT_SECONDS=60
```

Then run a tiny LLM simulation:

```bash
python3 -m agent_world.cli run --brain llm --ticks 10 --agents 3 --seed 7 --out runs/llm.jsonl --snapshot runs/llm-snapshot.json
```

You can override the model per run:

```bash
python3 -m agent_world.cli run --brain llm --model gpt-4.1-mini --ticks 5 --agents 2
```

To connect a different provider or local agent policy, implement the `AgentBrain` protocol in `agent_world/agents.py`: receive an observation dictionary, return the same JSON shape described in the prompt, and let `WorldEngine` validate everything.

Runs log private observations, prompts, responses, validation errors, actions, state transitions, trades, messages, claims, groups, and deaths. Use `--no-agent-io-log` when you want smaller event logs.

## Agent Response Shape

Agents return structured JSON-like data:

```json
{
  "intent": "short reason for this tick",
  "actions": [
    { "type": "move", "direction": "east" },
    { "type": "gather", "resource": "food", "quantity": 1 }
  ],
  "messages": [
    { "mode": "say", "text": "I found food east of camp." }
  ],
  "memory_updates": [
    "There is food near the eastern plains."
  ]
}
```

Invalid or unaffordable actions fail explicitly and are logged; they do not mutate world state.

## World Model

- 2D grid with deterministic terrain and resources.
- Discrete ticks with fixed agent resolution order.
- Local observations filtered by visibility radius and event scope.
- Inventories, item piles, structures, tile claims, groups, trade offers, and persistent memories.
- Survival pressure through food, water, energy, health, carrying capacity, and action points.
- Replayable JSONL event logs and summary metrics for economy/social analysis.

## Design Principle

The engine exposes constraints and affordances, not objectives. A prompt may say what actions are possible and what the agent can perceive. It should not tell the agent to trade, cooperate, govern, optimize wealth, or build institutions.
