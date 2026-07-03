# Observability

The simulation writes JSONL event logs and snapshots. The local observatory reads those files and displays the current/replayed state.

## Common Commands

Open the observatory:

```bash
python3 -m agent_world.cli view --events runs/live.jsonl --snapshot runs/live-snapshot.json
```

Start runs from the browser at `http://127.0.0.1:8765`. The Run panel accepts:

- brain: `survival` for deterministic infrastructure tests or `llm` for API-backed agents
- agents: number of spawned agents
- ticks: target ticks to run
- seed: deterministic world/run seed
- model: model used for `llm` runs, defaulting to `z-ai/glm-5.2` via OpenRouter
- max workers: same-tick brain call concurrency; keep this at `1` for LLM runs unless rate limits allow more
- agent IO log: whether to keep private observations and prompts in the JSONL audit log

The observatory writes each launched run to the watched `runs/live.jsonl` and `runs/live-snapshot.json` files and refreshes the map, agent panels, metrics, and event feed as the run progresses.

Run a simulation from the terminal:

```bash
python3 -m agent_world.cli run --brain llm --ticks 15 --agents 5 --progress --out runs/live.jsonl --snapshot runs/live-snapshot.json
```

Replay recent events in the terminal:

```bash
python3 -m agent_world.cli replay runs/live.jsonl --last 80
```

## Event Logs

Events include:

- observations/prompts/responses when agent IO logging is enabled
- movement, gathering, farming, chopping, mining, crafting
- building, storing, retrieving, repairing
- speech and trade offers/acceptances
- invalid actions
- survival damage/death
- group and agreement events

Private prompt/observation logs are stored for audit but are not fed back into future agent observations.

## Metrics To Watch

- `agents.living` and death count
- `wealth` and `wealth_gini`
- `trade.accepted`, `trade.open`, `trade.volume`
- `infrastructure.structures_by_type`
- `infrastructure.build_readiness.ready_counts`
- `infrastructure.builds`, `farm_actions`, `store_actions`, `retrieve_actions`
- `invalid_actions.reasons`
- `llm.decision_failures`
- `llm.rate_limit_failures`

## Observatory UI

The observatory at `http://127.0.0.1:8765` is a full-screen illustrated map with floating panels (Rebel Inc-style): the world fills the viewport, and dock buttons on the right open windows over it.

- illustrated overhead map: drawn terrain, structures, agent figures, gravestones, claims, and item piles
- forest tree density tracks remaining wood, so depletion is visible on the map
- tile hover tooltips and a click-to-open tile inspector window (resources, structure status, remaining build inputs, stored goods, occupants)
- dock windows: Run (transport controls — Start/Pause/Stop plus the tick scrubber with back/forward/Live for replaying history), Civilization (per-tick trends chart of population/structures/trades/speech plus structure counts), Agents (roster with reserves/inventory; clicking a card highlights the agent on the map and filters the chronicle), Chronicle (filterable event feed), and Legend
- the Run window floats over the map with no backdrop, so the map stays visible while you scrub between ticks
- slim top strip with run vitals (tick, living, builds, co-op builds, trades, LLM errors, invalid actions)
- a "Configure Run" slide-out drawer with all world-config knobs (used for pre-run setup; also has a Start button)

It is a watchable overhead view of the simulated world, but the purpose is observability: every visual is backed by state or event data.

## Rate Limits

LLM runs default to one OpenAI request at a time:

```dotenv
OPENAI_MAX_PARALLEL_AGENTS=1
OPENAI_MIN_REQUEST_INTERVAL_SECONDS=0.75
OPENAI_MAX_RETRIES=4
```

Increase concurrency only if the account rate limits can handle it.
