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
python3 -m agent_world.cli experiment --agents 5 --ticks 20 --seeds 11 --environment all --objective all --progress
python3 -m agent_world.cli experiment --brain llm --model openai/gpt-5.6-luna --environment organic --objective neutral --ticks 40 --agents 5 --seeds 29 --progress
python3 -m agent_world.cli run --brain codex --model gpt-5.6-luna --reasoning-effort low --ticks 3 --agents 2 --progress
python3 -m agent_world.cli run --brain claude --model claude-sonnet-5 --reasoning-effort low --ticks 3 --agents 2 --progress
```

The default CLI run uses deterministic mock brains so the infrastructure can be tested without an LLM key.

The `experiment` command runs the environment × objective factorial design. It
defaults to the free scripted survival brain and all four cells. Select one cell
explicitly for a paid LLM run, for example:

```bash
python3 -m agent_world.cli experiment \
  --brain llm --environment commerce --objective individual \
  --seeds 21 --ticks 60 --agents 5 --progress \
  --out-dir runs/experiments/commerce-individual-glm
```

Each run directory contains raw events, a final snapshot, usage records, a run
report, and a manifest with the Git SHA, dirty-worktree flag, source/rule and
initial prompt hashes, model/provider/reasoning settings, condition, seed, and
tick completion. The experiment root contains `experiment-manifest.json`,
`summary.json`, and `summary.md` with per-condition aggregates and paired
factorial contrasts. Use `--overwrite` only when intentionally reusing an output
directory.

## Project Map

- `agent_world/world.py`: source-of-truth world engine and action validation.
- `agent_world/rules.py`: resources, terrain, recipes, action schema, and structure rules.
- `agent_world/maps.py`: canonical handcrafted 16x16 world map.
- `agent_world/interface.py`: per-agent observation and neutral prompt construction.
- `agent_world/openai_brain.py`: OpenAI-backed `AgentBrain` with retry/throttle handling.
- `agent_world/codex_brain.py`: ChatGPT-plan-backed `AgentBrain` using isolated `codex exec` decisions.
- `agent_world/claude_brain.py`: Claude-plan-backed `AgentBrain` using isolated headless `claude -p` decisions.
- `agent_world/runner.py`: observe -> decide -> validate simulation orchestration.
- `agent_world/observer.py`: local web observatory for live/replay visualization.
- `agent_world/metrics.py`: aggregate run metrics and diagnostics.
- `agent_world/run_report.py`: per-run structured data export (`-report.json`/`-report.md`) and cross-run comparison.
- `agent_world/experiments.py`: reproducible multi-seed environment × objective experiments with provenance manifests and paired contrasts.
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

### Codex plan agents

`CodexBrain` runs Luna or Terra through the locally installed Codex CLI and its
saved ChatGPT login. It does not use `OPENAI_API_KEY` or `CODEX_API_KEY`, and it
records each call with `provider=codex_cli`, `billing_mode=chatgpt_plan`, token
usage, prompt hashes, and zero marginal API cost. Codex runs also sample the
account's plan limits before the first decision and after every tick. The
`*-plan-usage.json` artifact preserves the raw 5-hour/weekly utilization and
credit-balance checkpoints; reports show the observed before/after drawdown.
These are account-level readings, so concurrent Codex work may contribute to a
run's observed delta. Install and sign in to Codex,
then verify the login before starting a run:

```bash
codex login status
python3 -m agent_world.cli run \
  --brain codex --model gpt-5.6-luna --reasoning-effort low \
  --ticks 10 --agents 3 --progress \
  --out runs/codex-luna.jsonl --snapshot runs/codex-luna-snapshot.json
```

Use `gpt-5.6-terra` for a stronger Codex-plan condition. Each living agent gets
an independent, ephemeral, read-only Codex invocation per tick. The adapter
disables shell tools, apps, and subagent delegation, runs outside the repository,
and constrains the final response to an equivalent strict decision contract that
the adapter normalizes back to Agent World's flat action shape.
Codex-plan results should be labeled separately from raw API results because the
Codex harness adds its own runtime instructions. Runs default to one concurrent
Codex decision; raise `CODEX_MAX_PARALLEL_AGENTS` or pass `--max-workers` only
after benchmarking account limits and host load.

### Claude plan agents

`ClaudeBrain` runs Anthropic models through the locally installed Claude Code
CLI and its saved claude.ai login, so decisions draw on the Pro/Max plan's usage
limits instead of the metered Anthropic API. The adapter strips
`ANTHROPIC_API_KEY` (and Bedrock/Vertex/Foundry toggles) from the child
environment so the subscription login is always used, and records each call
with `provider=claude_cli`, `billing_mode=claude_plan`, token usage, prompt
hashes, and zero marginal API cost. Sign in to Claude Code (`claude` then
`/login`, or check `claude auth`) before starting a run:

```bash
python3 -m agent_world.cli run \
  --brain claude --model claude-sonnet-5 --reasoning-effort low \
  --ticks 10 --agents 3 --progress \
  --out runs/claude-sonnet.jsonl --snapshot runs/claude-sonnet-snapshot.json
```

Each living agent gets an independent, tool-less, session-less `claude -p`
invocation per tick with the run's rulebook as a stable system prompt (so the
provider prompt cache is reused) and a `--json-schema` constrained decision. The
adapter runs in an empty temporary directory with user/project settings, MCP
servers, and skills disabled so nothing outside the observation leaks into the
decision. Models: `claude-haiku-4-5` (cheapest against plan limits),
`claude-sonnet-5` (default), `claude-opus-4-8`. Unlike Codex, the Claude CLI
has no headless plan-limit endpoint, so no `*-plan-usage.json` is produced;
per-call token usage is still recorded. When plan limits are hit the run stops
early with `Claude quota unavailable` so the log is not mistaken for agent
behavior. Run startup also checks `claude auth status` without spending a model
turn and stops at tick zero if the saved Claude-plan login is unavailable.
Extended thinking is disabled by default. Enable it reproducibly with
`--claude-thinking-budget-tokens N` (or set `CLAUDE_MAX_THINKING_TOKENS`);
the resolved budget is saved in the population, run manifest, checkpoint, and
every Claude usage record. Other environment knobs: `CLAUDE_MODEL`,
`CLAUDE_REASONING_EFFORT`, `CLAUDE_TIMEOUT_SECONDS`, `CLAUDE_EXECUTABLE`,
`CLAUDE_MAX_PARALLEL_AGENTS`.

### Mixed-model populations

A run can assign deterministic cohorts to different providers and models. Repeat
`--population COUNT@MODEL`; familiar Claude and GPT-5.6 model names infer the
`claude` and `codex` brains automatically:

```bash
python3 -m agent_world.cli run \
  --preset organic-generalists \
  --population 10@claude-sonnet-5 \
  --population 10@gpt-5.6-luna \
  --ticks 50 --seed 41 --economy-mode organic \
  --max-workers 8 --progress \
  --out runs/sonnet-luna.jsonl \
  --snapshot runs/sonnet-luna-snapshot.json
```

`--preset organic-generalists` expands to an organic, dispersed world with no
preset occupations or agent-specific production/need advantages. Use
`--preset experimental-organic-specialists` to deliberately test preset
farmer, forester, miner, fisher, and artisan roles with asymmetric aptitudes,
starting inventories, and needs. That specialist preset is an experimental
economic treatment, not the neutral/default society condition. The CLI
prints the resolved world, population, assignment seed, concurrency, and harness
before spending model capacity. Mixed populations default to deterministic
stratified assignment within each specialty (or across all agents in the
generalist condition); override with
`--assignment-seed N`, or use `--assignment-strategy ordered` only for legacy
comparisons.

For a paired treatment/control comparison, preserve the exact model-to-spawn
mapping from a compatible prior run with
`--assignment-from-manifest runs/prior-run-manifest.json`. Reusing only the
assignment seed is insufficient when a treatment changes the assignment
strata, such as specialists versus generalists.

Provider concurrency is independently bounded even when the global worker pool
is larger:

```bash
--max-workers 8 --claude-max-workers 4 --codex-max-workers 4
```

Reasoning experiments can keep the same model-to-agent mapping while changing
effort and Claude's extended-thinking budget:

```bash
--reasoning-effort medium --claude-thinking-budget-tokens 1024 \
--assignment-from-manifest runs/prior-run-manifest.json
```

`--decision-mode raw` preserves every model-proposed action for unassisted
research. `--decision-mode validated` is an explicit assisted condition that
truncates only the portion of an action list exceeding the declared AP budget.
Never mix these conditions in one comparison.

Use `COUNT@BRAIN:MODEL` when inference is ambiguous or for a newly released
model, for example `10@claude:claude-fable-model-id`. An optional effort suffix
is accepted as `COUNT@BRAIN:MODEL:EFFORT`. Cohorts are assigned in command-line
order (`agent-1` onward), saved with the checkpoint, and restored unchanged on
resume. Do not repeat the population flags when resuming:

```bash
python3 -m agent_world.cli run \
  --resume-checkpoint runs/sonnet-luna-checkpoint.pkl \
  --ticks 75 --progress
```

The run report includes each cohort's model, membership, survival, action mix,
gifts, trades, token use, API cost, and Codex plan credits. A shared usage JSONL
retains provider/model/agent identity per call. Quota and throttling state are
isolated by provider, while any provider quota failure stops the complete run so
the remaining ticks are not mistaken for comparable mixed-model behavior.
Every ordinary run with `--out` also writes `*-manifest.json` with the resolved
preset, complete assignment, assignment seed, harness condition, concurrency,
command, git provenance, resolved response-model versions, and output paths.

For a balanced comparison, run equal cohorts across several world and assignment
seeds, then add homogeneous controls on those same world seeds. For example,
repeat a 5/5/5/5 mixed population with `--seed 11 --assignment-seed 101`, then
rotate assignment seeds while keeping the world seed fixed before changing the
world seed. Reports expose offer conversion and cross-cohort trade, gift, and
construction matrices so these runs can be aggregated without re-parsing logs.

Runs log private observations, prompts, responses, validation errors, actions, state transitions, trades, messages, claims, groups, and deaths. Use `--no-agent-io-log` when you want smaller event logs.

## Run Reports

Every `run` with `--out` automatically exports `<name>-report.json` (machine-readable: config, survival, action mix, structure timeline, groups, valued gift flows, trades, productive assets, milestone first-ticks, reliability, LLM cost, full say transcript) and `<name>-report.md` (human summary) next to the event log. All reports share one schema, so runs are directly comparable across experiments. Regenerate reports for old logs — or compare several runs side by side — with:

```bash
python3 -m agent_world.cli report runs/a.jsonl runs/b.jsonl
```

Passing multiple logs prints a metric-by-metric comparison table after writing the reports.

Reports use proposed model actions—not the much larger event stream—as the
invalid-action denominator. They also include invalidity attribution from each
logged pre-tick observation, a trade funnel, occupation and
model-by-occupation outcomes, and provider game-context fingerprints in the
run manifest. Disable agent IO logging only when smaller logs matter more than
those diagnostics.

Before changing the experimental specialist packages, measure their non-social
scripted survival floor across many seeds:

```bash
python3 -m agent_world.cli benchmark-roles --seeds $(seq 1 100) --ticks 50 \
  --out runs/role-viability.json
```

### Efficient, run-scoped telemetry

Codex reports now calculate `simulation_credits` from the token usage of the simulation's own decisions. Uncached input, cached input, and output are priced separately with a versioned Luna/Terra/Sol rate table; reasoning tokens are reported but not double-charged because they are already included in output. This is separate from `*-plan-usage.json`, whose sparse account snapshots can include work done by the supervising Codex task or another window. Account snapshots default to run start and terminal state only; set `CODEX_PLAN_SNAPSHOT_INTERVAL_TICKS` to a positive interval if you want additional diagnostics during a long run.

Run persistence is incremental: new events are appended once, while the current snapshot and full crash checkpoint are atomically replaced each tick. `--out runs/example.jsonl` creates `runs/example-checkpoint.pkl`; resume that trusted local file and preserve the exact engine/RNG state with:

```bash
python3 -m agent_world.cli run \
  --resume-checkpoint runs/example-checkpoint.pkl --ticks 60 --progress
```

The audit log stores each distinct static prompt context once and links compact per-decision observations to it by hash. This keeps the run auditable without repeating the full rulebook and prompt for every agent on every tick. Checkpoints use Python pickle and must not be loaded from untrusted sources.

The LLM request is split to minimize input tokens (~85% of API cost): the static rulebook (actions, costs, recipes, terrain, mechanics) is rendered once as terse text in the system message — byte-identical across every agent and tick, so provider-side prompt caching can reuse it — while the per-tick user message carries only the slim dynamic state (tiles omit empty/derivable fields, events omit engine internals). No information is removed, only redundancy: everything an agent could act on is still present each call. Build-readiness diagnostics are intentionally kept out of agent observations so agents are not nudged with "you can now build X" hints.

The model-facing agent boundary is versioned. `compact-v2` remains the default control;
`--observation-mode grounded-v3` adds neutral `body`, `here`, and direction-keyed
`adjacent` summaries without recommending or pre-validating actions. Runs, checkpoints,
event logs, and provider usage records retain the selected format for clean A/B analysis.
Lighter experimental treatments are also available: `body-only-v3` adds only AP, energy,
and free carry capacity, while `indexed-v3` additionally labels the existing current and
cardinal map entries without duplicating tile contents.

Turn timing is versioned separately from the observation boundary. The historical
control is `--turn-mode simultaneous-v1`: all agents decide against the same state, then
resolve in rotating order. `--turn-mode shuffled-sequential-v1` deterministically
reshuffles agents each tick and gives every activation a fresh post-activation view.
It does not change world rules or tell agents which mode is active. Reports record order,
same-tick event visibility, and early/middle/late activation diagnostics.

## Observatory

Open the local observatory:

```bash
python3 -m agent_world.cli view --events runs/live.jsonl --snapshot runs/live-snapshot.json
```

Then visit `http://127.0.0.1:8765`. The observatory has two purpose-built pages:

- **World** is the watch surface: an animated overhead map, agent/tile/structure inspector, searchable chronicle, replay timeline, map layers, and economy, population, civilization, and model analytics.
- **Run Lab** at `/runs` is the control surface: compose mixed Codex, Claude, API, and deterministic populations; choose a world preset and harness settings; launch a timestamped run; browse preserved runs; clone configurations; and compare up to four reports.

Browser-launched runs are archived under `runs/observatory/<timestamp>-<name>/` with their events, snapshot, checkpoint, manifest, usage, and reports. The active world switches to the new run automatically. The archive reads the local run catalog, including older CLI and experiment runs whose durable evidence is available.

You can still run simulations from the terminal if you want a scriptable batch run:

```bash
python3 -m agent_world.cli run --brain llm --ticks 25 --agents 3 --progress --out runs/live.jsonl --snapshot runs/live-snapshot.json
```

The world renders terrain, resources, claims, structures, agents, and item piles directly from the snapshot. Hovering surveys a tile; clicking opens an agent dossier, civil-asset view, or terrain survey. The intelligence drawer shows market funnels and holdings, survival and health distributions, civilization milestones, cohort outcomes, provider usage, and reliability. All visuals are derived from preserved state, events, manifests, or reports.

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
- Discrete ticks with a deterministic rotating resolution order, avoiding permanent first-mover priority.
- Local observations filtered by visibility radius and event scope.
- Inventories, item piles, structures, tile claims, groups, trade offers, and persistent memories.
- Trade offers can target a specific visible agent or be posted locally for any visible counterparty; offered goods are escrowed until the offer resolves.
- Optional commerce treatments add global standing offers, completed-price history, secured credit, access fees, contributor dividends, and productive-asset upkeep/capacity.
- The optional organic treatment keeps exchange physical and knowledge local: offers deposit goods at a tile, both parties must meet there, and expired escrow remains as an owned pile. It adds stronger comparative advantage, high-fixed-cost/high-capacity infrastructure, and carried coins without telling agents to use any of them.
- Optional dispersed geography gives agents separated resource regions, different specialties, aptitudes, endowments, and needs so comparative advantage is mechanically meaningful.
- Groups can receive access grants, directly own claimed tiles/structures, and keep persistent agreement ledgers, making shared infrastructure mechanically useful.
- Survival pressure through food, water, energy, health, carrying capacity, action points, and carried-food spoilage.
- Replayable JSONL event logs and summary metrics for economy/social analysis.
- Infrastructure diagnostics for built structures, farm plots, storage use, and which structures agents are currently able to build.

Current inventory resources:

- `coin`: durable, negligible-weight physical token. Organic agents begin with a small stock; workshops can mint eight coins from one ingot.
- `water`: consumed to restore thirst, gathered from adjacent water.
- `food`: consumed to restore hunger and a little energy. Carried food spoils periodically; stored food is protected.
- `fiber`: building/crafting input, especially early farms/storage/tools.
- `wood`: building/crafting/repair input, produced by chopping forest resources.
- `stone`: building/crafting input, produced by mining.
- `ore`: high-value raw material, present for later production chains.
- `tool`: craftable/equippable item, present for later tool/skill mechanics.
- `ingot`: workshop-smelted intermediate made from ore and wood.
- `advanced_tool`: durable workshop-made capital good with a larger productivity and energy advantage.

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

The completed 60-tick Lakeside GLM-5.2 run produced ten structures, two heavy cooperative builds, one five-member polity, six group-owned structures, 27 gifts, eight trade offers, and one accepted barter trade with no deaths. Detailed inspection showed that 23 gift actions were food/water aid, while only four moved productive materials. This motivated explicit objective/geography/economy treatments instead of interpreting a single small-group run as evidence for one economic ideology.

The commerce treatment now supplies the previously missing conditions for exchange and entrepreneurship: real skill/tool productivity, a deeper capital chain, separated specialists, priced productive access, contributor returns, standing markets with price history, secured credit, upkeep, finite service capacity, and nonzero coordination costs. Use `agent_world.cli experiment` to run matched multi-seed cells; ordinary runs retain the neutral historical baseline.

The organic treatment asks a different question: can stronger models discover society without a global order book or engine-assisted delivery? It uses a neutral objective, local information, physical escrow/settlement, much stronger skill differences, expensive but high-capacity infrastructure, free local speech, and physical coins. The engine supplies constraints and objects; agents still have to travel, bargain, transport goods, share assets, and decide whether coins mean anything.

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
- [docs/architecture.md](docs/architecture.md)
- [docs/agent-interface.md](docs/agent-interface.md)
- [docs/observability.md](docs/observability.md)
- [docs/research-notes.md](docs/research-notes.md)
- [docs/research-ledger.md](docs/research-ledger.md)
- [docs/economy-experiments.md](docs/economy-experiments.md)

## Design Principle

The engine exposes constraints and affordances, not objectives. A prompt may say what actions are possible and what the agent can perceive. It should not tell the agent to trade, cooperate, govern, optimize wealth, or build institutions.
