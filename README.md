# Agent World

Agent World is a deterministic, tick-based 2D simulation substrate for observing autonomous LLM agents inside a constrained world. Agents are not told to form markets, governments, firms, or social structures. They receive local observations, their own state, remembered facts, and a strict JSON action interface. The world engine validates and resolves every proposed action.

The project goal is to study whether richer social behavior can emerge from world constraints: survival needs, scarcity, geography, production, ownership, communication, exchange, shared records, and eventually institutions. The engine should provide affordances and consequences, not goals like "form a market" or "create a government."

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m agent_world.cli map
python3 -m agent_world.cli run --ticks 25 --agents 5 --seed 7 --progress --out runs/example.jsonl --snapshot runs/example-snapshot.json
python3 -m agent_world.cli replay runs/example.jsonl --last 30
python3 -m agent_world.cli prompt --seed 7 --agents 2 --agent agent-1
python3 -m agent_world.cli ablate --agents 4 --ticks 30 --seed 11
```

The default CLI run uses deterministic mock brains so the infrastructure can be tested without an LLM key.

## Project Map

- `agent_world/world.py`: source-of-truth world engine and action validation.
- `agent_world/rules.py`: resources, terrain, recipes, action schema, and structure rules.
- `agent_world/maps.py`: canonical handcrafted 16x16 world map.
- `agent_world/interface.py`: per-agent observation and neutral prompt construction.
- `agent_world/openai_brain.py`: OpenAI-backed `AgentBrain` with retry/throttle handling.
- `agent_world/runner.py`: observe -> decide -> validate simulation orchestration.
- `agent_world/observer.py`: local web observatory for live/replay visualization.
- `agent_world/metrics.py`: aggregate run metrics and diagnostics.
- `agent_world/run_report.py`: per-run structured data export (`-report.json`/`-report.md`) and cross-run comparison.
- `tests/`: regression coverage for world rules, maps, observer, and OpenAI adapter helpers.
- `docs/`: design notes and future handoff context.

## LLM Agents

Agents are driven through an OpenAI-compatible API. The default configuration uses **OpenRouter** running **GLM-5.2** (open weights, strong long-horizon agentic performance at a fraction of frontier-model cost). Copy `.env.example` to `.env` and fill in your key:

```bash
cp .env.example .env
```

```dotenv
OPENAI_API_KEY=sk-or-v1-your-openrouter-key-here
OPENAI_MODEL=z-ai/glm-5.2
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_TIMEOUT_SECONDS=180
OPENAI_MAX_OUTPUT_TOKENS=8000
OPENAI_REASONING_EFFORT=medium
OPENAI_MAX_RETRIES=4
OPENAI_MIN_REQUEST_INTERVAL_SECONDS=0.5
OPENAI_MAX_PARALLEL_AGENTS=1
SSL_CERT_FILE=/etc/ssl/cert.pem
```

`OpenAIBrain` auto-selects the request style from the base URL: the standard **Chat Completions** API (`/chat/completions`, used by OpenRouter and most providers) when the base URL is OpenRouter, or OpenAI's **Responses** API (`/responses`) for `api.openai.com`. Force it with `LLM_API_STYLE=chat|responses`. To use OpenAI instead, set `OPENAI_BASE_URL=https://api.openai.com/v1` and `OPENAI_MODEL=gpt-5.4-mini`.

LLM runs default to one request at a time to avoid token-per-minute bursts. Increase `OPENAI_MAX_PARALLEL_AGENTS` or pass `--max-workers` only if your rate limits can handle it. Cost knobs: lower `OPENAI_REASONING_EFFORT` (minimal/low) and `OPENAI_MAX_OUTPUT_TOKENS` to reduce spend per tick.
If the API returns hard quota/credit exhaustion, the run stops early and reports `quota_failures` so the log is not mistaken for agent behavior.

Then run a tiny LLM simulation:

```bash
python3 -m agent_world.cli run --brain llm --ticks 10 --agents 3 --seed 7 --progress --out runs/llm.jsonl --snapshot runs/llm-snapshot.json
```

You can override the model and reasoning effort per run:

```bash
python3 -m agent_world.cli run --brain llm --model z-ai/glm-5.2 --reasoning-effort medium --ticks 5 --agents 2
```

To connect a different provider or local agent policy, implement the `AgentBrain` protocol in `agent_world/agents.py`: receive an observation dictionary, return the same JSON shape described in the prompt, and let `WorldEngine` validate everything.

Runs log private observations, prompts, responses, validation errors, actions, state transitions, trades, messages, claims, groups, and deaths. Use `--no-agent-io-log` when you want smaller event logs.

## Run Reports

Every `run` with `--out` automatically exports `<name>-report.json` (machine-readable: config, survival, action mix, structure timeline, groups, gift network, trades, milestone first-ticks, reliability, LLM cost, full say transcript) and `<name>-report.md` (human summary) next to the event log. All reports share one schema, so runs are directly comparable across experiments. Regenerate reports for old logs — or compare several runs side by side — with:

```bash
python3 -m agent_world.cli report runs/a.jsonl runs/b.jsonl
```

Passing multiple logs prints a metric-by-metric comparison table after writing the reports.

The LLM request is split to minimize input tokens (~85% of API cost): the static rulebook (actions, costs, recipes, terrain, mechanics) is rendered once as terse text in the system message — byte-identical across every agent and tick, so provider-side prompt caching can reuse it — while the per-tick user message carries only the slim dynamic state (tiles omit empty/derivable fields, events omit engine internals). No information is removed, only redundancy: everything an agent could act on is still present each call. Build-readiness diagnostics are intentionally kept out of agent observations so agents are not nudged with "you can now build X" hints.

## Observatory

Open the local observatory:

```bash
python3 -m agent_world.cli view --events runs/live.jsonl --snapshot runs/live-snapshot.json
```

Then visit `http://127.0.0.1:8765`. The observatory can now launch runs directly from the browser. Choose the brain type, agent count, tick count, seed, model, max workers, and whether to log private agent IO, then press Start. The server writes the selected run into the same live event log and snapshot files.

You can still run simulations from the terminal if you want a scriptable batch run:

```bash
python3 -m agent_world.cli run --brain llm --ticks 25 --agents 3 --progress --out runs/live.jsonl --snapshot runs/live-snapshot.json
```

The observatory renders the world as an illustrated overhead map — drawn terrain (forests visibly thin out as wood is depleted), hand-drawn structures (houses, farms, wells, storage, shelters, workshops, dashed construction sites), agent figures with per-agent colors, and gravestones where agents died. Hovering a tile shows its resources and occupants; clicking opens a tile inspector with structure status, remaining build inputs, and stored goods. A civilization panel charts population, completed structures, accepted trades, and speech over ticks, alongside structure counts and a filterable event chronicle.

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

- Standard 16x16 handcrafted world with a coast, river/lake system, forests, plains, and an eastern mountain range.
- Water tiles are not occupiable; agents gather water or fish from adjacent land.
- Discrete ticks with fixed agent resolution order.
- Local observations filtered by visibility radius and event scope.
- Inventories, item piles, structures, tile claims, groups, trade offers, and persistent memories.
- Trade offers can target a specific visible agent or be posted locally for any visible counterparty; offered goods are escrowed until the offer resolves.
- Groups can receive access grants, directly own claimed tiles/structures, and keep persistent agreement ledgers, making shared infrastructure mechanically useful.
- Survival pressure through food, water, energy, health, carrying capacity, action points, and carried-food spoilage.
- Replayable JSONL event logs and summary metrics for economy/social analysis.
- Infrastructure diagnostics for built structures, farm plots, storage use, and which structures agents are currently able to build.

Current inventory resources:

- `water`: consumed to restore thirst, gathered from adjacent water.
- `food`: consumed to restore hunger and a little energy. Carried food spoils periodically; stored food is protected.
- `fiber`: building/crafting input, especially early farms/storage/tools.
- `wood`: building/crafting/repair input, produced by chopping forest resources.
- `stone`: building/crafting input, produced by mining.
- `ore`: high-value raw material, present for later production chains.
- `tool`: craftable/equippable item, present for later tool/skill mechanics.

## Structures

- `farm_plot`: persistent improved land on plains/forest that can support more reliable food production than wild foraging.
- `storage`: large shared/private container with agent or group access controls; stored food is protected from spoilage.
- `shelter`: simple rest structure that improves waiting and prevents passive energy decay.
- `house`: better rest structure with smaller storage, useful for settlement clustering.
- `workshop`: material cache and crafting site that lowers crafting energy costs.
- `well`: local water infrastructure for settlements away from open water.

Building places a **construction site** on the current tile. Any materials the initiator is carrying are deposited immediately; if the structure still needs more, it stays under construction and provides no effects until it is finished. Any agent standing on the tile can `contribute` materials to an in-progress site, and the structure completes (and its effects turn on) only once every required input has been supplied. Heavy structures (shelter, house, workshop) weigh more than one agent can carry at once, so they must be funded across several trips or by several agents working together — making cooperative, persistent infrastructure a natural outcome rather than something the prompt asks for. A half-built site persists if its initiator dies, so others can finish it.

Map legend:

```text
. = plains
F = forest
M = mountain
W = water
```

## Current Research State

The first GLM-5.2 run (5 agents, 18 ticks) produced solo infrastructure investment (a well, two farm plots, storage), the first accepted trade, access grants, functional coordination speech, and spontaneous division-of-labor language ("I farm, you bring water") — with zero deaths. Two gaps drove the current tuning: agents verbally promised structure access without executing `grant_access` (owners now receive an `access_denied` event when someone is turned away at their structure, and visible structures show `access_granted` per observer), and a survival treadmill left no surplus for heavy cooperative builds (reserve ceilings raised: food/water 15→20, energy 25→30 with start 25, so agents can bank a good trip into project time). Decay rates are unchanged — pressure still binds, but a full tank now buys more ticks. Cooperative construction (`contribute` on under-construction sites) has not yet been exercised by real agents; watch `construction.cooperative_sites`.

The most important diagnostics to watch are:

- `llm.decision_failures` and `llm.rate_limit_failures`
- `infrastructure.build_readiness.ready_counts`
- `infrastructure.builds`, `farm_actions`, `store_actions`, `retrieve_actions`
- `construction.sites_started`, `construction.sites_completed`, `construction.sites_in_progress`, `construction.contributions`, and especially `construction.cooperative_sites` (structures funded by more than one agent — the clearest signal of emergent cooperation)
- `capacity.median_spare_action_points` and `capacity.median_energy` (whether agents have any surplus beyond survival to invest)
- `agents.median_lifespan` (whether agents survive long enough for investment to pay back)
- invalid action reasons
- wealth distribution and accepted trade count

Use `agent_world.cli ablate` to sweep one variable at a time (carry capacity, energy ceiling, water decay, food density, horizon) on a fixed seed and diff these metrics, so model quality and world balance can be separated.

For richer context, see:

- [docs/world-design.md](docs/world-design.md)
- [docs/agent-interface.md](docs/agent-interface.md)
- [docs/observability.md](docs/observability.md)
- [docs/research-notes.md](docs/research-notes.md)

## Design Principle

The engine exposes constraints and affordances, not objectives. A prompt may say what actions are possible and what the agent can perceive. It should not tell the agent to trade, cooperate, govern, optimize wealth, or build institutions.
