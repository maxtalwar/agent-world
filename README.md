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
account's plan limits before the first decision and at the terminal state. The
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

Use `gpt-5.6-terra` for a stronger Codex-plan condition. By default, each living
agent gets an independent, ephemeral, read-only Codex invocation per tick.
Bounded-session mode instead resumes a short private conversation for that
agent. The adapter disables shell tools, apps, and subagent delegation, runs
outside the repository, and constrains the final response to an equivalent
strict decision contract that the adapter normalizes back to Agent World's flat
action shape.
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

Each living agent gets a tool-less `claude -p` invocation per tick. The default
is session-less; `bounded-session-v1` can instead retain a private rotating
conversation per agent. The run's rulebook is a stable system prompt (so the
provider prompt cache is reused) and a `--json-schema` constrained decision. The
adapter runs in a stable empty directory with user/project settings, MCP
servers, and skills disabled so nothing outside the observation leaks into the
decision. Models: `claude-haiku-4-5` (cheapest against plan limits),
`claude-sonnet-5` (default), `claude-opus-4-8`. Unlike Codex, the Claude CLI
has no headless plan-limit endpoint, so no `*-plan-usage.json` is produced;
per-call token usage is still recorded. When Claude or Codex plan/rate limits
are hit, the incomplete tick is discarded and the run is marked
`paused_checkpoint`; successful calls from that partial tick are preserved in a
separate `*-usage-partial-tick-N.jsonl` audit ledger. Resume the normal checkpoint
after the provider resets without introducing an all-wait tick into the world.
Run startup also checks `claude auth status` without spending a model
turn and stops at tick zero if the saved Claude-plan login is unavailable.
Extended thinking is disabled by default (it costs thousands of plan
tokens and ~a minute per decision); set `CLAUDE_MAX_THINKING_TOKENS` to a
positive budget to re-enable it. Other environment knobs: `CLAUDE_MODEL`,
`CLAUDE_REASONING_EFFORT`, `CLAUDE_TIMEOUT_SECONDS`, `CLAUDE_EXECUTABLE`,
`CLAUDE_MAX_PARALLEL_AGENTS`.

### Cursor subscription agents

`CursorBrain` runs Grok and other models exposed by the installed Cursor Agent
CLI using the saved Cursor subscription login, not a metered API key. The
adapter removes `CURSOR_API_KEY` and related overrides from every child process,
runs each decision in an empty read-only workspace with Ask mode, and records
the CLI's per-call tokens with `provider=cursor_cli`,
`billing_mode=cursor_subscription`, prompt hashes, and zero marginal API cost.

Install Cursor Agent, authenticate once in a browser, and inspect the exact
models currently available to the account:

```bash
cursor agent --help
cursor-agent login
cursor-agent status
cursor-agent --list-models
```

Then run Grok through the subscription:

```bash
python3 -m agent_world.cli run \
  --brain cursor --model cursor-grok-4.5 --reasoning-effort low \
  --ticks 10 --agents 3 --progress \
  --out runs/cursor-grok.jsonl --snapshot runs/cursor-grok-snapshot.json
```

For model families with separate effort variants, the adapter resolves a base
name plus `--reasoning-effort` against the live account model list (for example,
`cursor-grok-4.5` plus `low` becomes `cursor-grok-4.5-low`). An exact model ID
always remains exact. Availability is checked before tick zero, because Cursor's
catalog can vary by account and over time. Cursor does not currently expose a
headless subscription-limit endpoint, so the simulation records decision-token
usage but cannot calculate a 5-hour or weekly percentage drawdown.

### Mixed-model populations

A run can assign deterministic cohorts to different providers and models. Repeat
`--population COUNT@MODEL`; familiar Claude, GPT-5.6, and Cursor/Grok model
names infer their native brains automatically. Use an explicit `cursor:` brain
for overlapping model families that should consume Cursor capacity:

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

Provider concurrency is independently bounded even when the global worker pool
is larger:

```bash
--max-workers 8 --claude-max-workers 4 --codex-max-workers 4
```

For a mixed native/Cursor run, for example:

```bash
--population 5@cursor:cursor-grok-4.5:low \
--population 5@cursor:gemini-3.1-pro:medium \
--population 5@codex:gpt-5.6-luna:low \
--cursor-max-workers 3 --codex-max-workers 3
```

`--decision-mode raw` preserves every model-proposed action for unassisted
research. `--decision-mode validated` is an explicit assisted condition that
truncates only the portion of an action list exceeding the declared AP budget.
Never mix these conditions in one comparison.

Use `COUNT@BRAIN:MODEL` when inference is ambiguous or for a newly released
model, for example `10@claude:claude-fable-model-id` or
`10@cursor:cursor-grok-4.5:high`. An optional effort suffix
is accepted as `COUNT@BRAIN:MODEL:EFFORT`. Cohorts are assigned in command-line
order (`agent-1` onward), saved with the checkpoint, and restored unchanged on
resume. Do not repeat the population flags when resuming:

```bash
python3 -m agent_world.cli run \
  --resume-checkpoint runs/sonnet-luna-checkpoint.pkl \
  --ticks 75 --progress
```

### Connector efficiency and conversation memory

Provider invocation overhead and provider conversation memory are independent,
versioned controls:

```bash
--connector-profile stateless-v3 \
--conversation-mode bounded-session-v1 \
--session-max-turns 10
```

`stateless-v3` keeps decisions stateless while giving Codex and Cursor
cross-process stable empty workspaces and removing irrelevant Codex tool,
plugin, discovery, and skill instructions. Claude's
already-lean stateless invocation is unchanged. `bounded-session-v1` is an
optional behavioral treatment: it keeps one private provider conversation per
agent, sends compact continuation observations, and rotates after the configured
number of successful decisions. Checkpoint resume starts a fresh provider
conversation from canonical simulation state so a partially submitted provider
turn cannot leak across the completed-tick boundary. See
[docs/agent-boundaries.md](docs/agent-boundaries.md).

The run report includes each cohort's model, membership, survival, action mix,
gifts, trades, token use, API cost, and Codex plan credits. A shared usage JSONL
retains provider/model/agent identity per call. Quota and throttling state are
isolated by provider, while any provider quota failure stops the complete run so
the remaining ticks are not mistaken for comparable mixed-model behavior.
Every ordinary run with `--out` also writes `*-manifest.json` with the resolved
preset, complete assignment, assignment seed, harness condition, concurrency,
command, git provenance, resolved response-model versions, and output paths.

## Standardized model benchmarks

Agent World Participant v3 provides three versioned 0-100 scores: planning
execution, sustained competence, and entrepreneurial agency. Any run receives
diagnostic cohort scores. A usage-constrained model can earn a provisional
benchmark from one clean, complete 50-tick seed-11 trial. Replicated
certification requires clean trials on both locked seeds, 11 and 41.

Start a standardized trial with:

```bash
python3 -m agent_world.cli run \
  --benchmark-protocol participant-v3 \
  --brain codex --model gpt-5.6-luna \
  --seed 11 \
  --out runs/benchmarks/luna-v3/seed-11/run.jsonl \
  --snapshot runs/benchmarks/luna-v3/seed-11/run-snapshot.json
```

Aggregate seed 11 alone for a provisional result. Add seed 41 later and pool
both generated reports with `python3 -m agent_world.cli benchmark ...` for
replicated certification. Both tiers retain the full 50-tick horizon; a
shorter run is diagnostic rather than a cheaper benchmark. Reports preserve
diagnostic score trajectories at ticks 30 and 40 before the official tick-50
endpoint. The protocol, formulas, quality rules, and interpretation guidance
are documented in [docs/model-benchmarks.md](docs/model-benchmarks.md).

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

### Efficient, run-scoped telemetry

Codex reports now calculate `simulation_credits` from the token usage of the simulation's own decisions. Uncached input, cached input, and output are priced separately with a versioned Luna/Terra/Sol rate table; reasoning tokens are reported but not double-charged because they are already included in output. This is separate from `*-plan-usage.json`, whose sparse account snapshots can include work done by the supervising Codex task or another window. Account snapshots default to run start and terminal state only; set `CODEX_PLAN_SNAPSHOT_INTERVAL_TICKS` to a positive interval if you want additional diagnostics during a long run.

Run persistence is incremental: new events are appended once, while the current snapshot and full crash checkpoint are atomically replaced each tick. `--out runs/example.jsonl` creates `runs/example-checkpoint.pkl`; resume that trusted local file and preserve the exact engine/RNG state with:

```bash
python3 -m agent_world.cli run \
  --resume-checkpoint runs/example-checkpoint.pkl --ticks 60 --progress
```

The audit log stores each distinct static prompt context once and links compact per-decision observations to it by hash. This keeps the run auditable without repeating the full rulebook and prompt for every agent on every tick. Checkpoints use Python pickle and must not be loaded from untrusted sources.

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
- [docs/economy-experiments.md](docs/economy-experiments.md)

## Design Principle

The engine exposes constraints and affordances, not objectives. A prompt may say what actions are possible and what the agent can perceive. It should not tell the agent to trade, cooperate, govern, optimize wealth, or build institutions.
