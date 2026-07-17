# Observability

The simulation writes JSONL event logs and snapshots. The local observatory reads those files and displays the current/replayed state.

## Common Commands

Open the observatory:

```bash
python3 -m agent_world.cli view --events runs/live.jsonl --snapshot runs/live-snapshot.json
```

Start runs from the browser at `http://127.0.0.1:8765/runs`. Run Lab accepts:

- one or more population cohorts, mixing Codex-plan, Claude-plan, API-backed, and deterministic brains
- model, reasoning effort, and agent count per cohort
- run name, target ticks, world seed, assignment strategy, and assignment seed
- named world presets plus optional economy, geography, specialization, objective, abundance, survival, and carrying-capacity controls
- observation boundary, decision boundary, turn structure, global concurrency, and provider-specific concurrency
- optional private agent IO preservation

Every browser launch receives a new timestamped directory under `runs/observatory/`; it never overwrites the run currently on screen. The directory receives the same raw events, snapshot, checkpoint, manifest, usage, and terminal reports as the CLI infrastructure. The active World page follows the new run automatically, while the Run Archive remains available for old evidence.

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

Private prompt/observation logs are stored for audit but are not fed back into future agent observations. To avoid duplicating megabytes of text, the log writes each distinct static prompt context once (`agent_prompt_context`), compact dynamic state per decision (`agent_observation`), and hashes linking the two (`agent_prompt`).

The event ledger is append-only during a run. Snapshots and crash checkpoints are atomically replaced once per tick, so persistence work scales with new events instead of repeatedly rewriting the complete run history. A terminal run with `--out runs/example.jsonl` automatically writes `runs/example-checkpoint.pkl`. Resume a trusted local checkpoint with a total target tick:

```bash
python3 -m agent_world.cli run --resume-checkpoint runs/example-checkpoint.pkl --ticks 60
```

Checkpoints preserve the complete engine and random-number-generator state. They are Python pickle files; never resume a checkpoint from an untrusted source.

## Metrics To Watch

- `agents.living` and death count
- `wealth` and `wealth_gini`
- `trade.accepted`, `trade.open`, `trade.volume`
- `economic_flows` for valued gifts, offer conversion, price history, and contract activity
- `specialization` and `productive_assets`, including asset-adjusted wealth
- `infrastructure.structures_by_type`
- `infrastructure.build_readiness.ready_counts`
- `infrastructure.builds`, `farm_actions`, `store_actions`, `retrieve_actions`
- `invalid_actions.reasons`
- `llm.decision_failures`
- `llm.rate_limit_failures`

## Observatory UI

### World

The World page is a full-screen simulation watch surface:

- animated overhead map with terrain textures, visible resources, structures, claims, item piles, living agents, and deaths
- layer controls, fit/zoom controls, hover surveys, and click-to-open agent, structure, and terrain inspectors
- a World Pulse panel for living population, trade, assets, society, recent warnings, and population/civilization trends
- a searchable and filterable event chronicle
- a replay timeline for the watcher history retained by the running observer
- an intelligence drawer with Economy, Population, Civilization, and Models sections

Economy covers inventories, asset value, gifts, trade conversion, and institutional state. Population covers survival reserves, health distribution, and the roster. Civilization covers buildings, groups, milestones, and longitudinal series. Models covers cohort outcomes, decision reliability, token usage, and Codex-plan simulation credits.

### Run Lab

The Run Lab at `/runs` separates operations from observation:

- Create Expedition builds a mixed population and controls world and harness settings without a terminal command.
- Run Archive searches and filters the derived run catalog, previews reports, opens final worlds when snapshots are local, clones prior configurations, and opens analytics directly.
- Compare holds up to four preserved reports in a side-by-side metric table.

The archive can show compact tracked reports even when heavyweight raw files are not available in the checkout. In that case analytics remain usable but map playback is explicitly marked unavailable. All displayed numbers come from snapshots, public events, manifests, reports, or the run catalog; private agent prompt and response events are never exposed in the browser feed.

## Rate Limits

LLM runs default to one OpenAI request at a time:

```dotenv
OPENAI_MAX_PARALLEL_AGENTS=1
OPENAI_MIN_REQUEST_INTERVAL_SECONDS=0.5
OPENAI_MAX_RETRIES=4
CODEX_MAX_PARALLEL_AGENTS=1
```

Increase concurrency only if the account rate limits can handle it.

For Codex-plan runs, the ordinary per-call `*-usage.jsonl` is the source of truth for run-exclusive consumption. Reports price its uncached input, cached input, and output against the versioned Luna/Terra/Sol Codex rate card and label the result `simulation_credits`. This excludes Codex work performed by the supervising task or another window.

Agent World also queries Codex's local account-limit snapshot at run start and terminal state. It writes `*-plan-usage.json` with those raw checkpoints and a summary of primary, secondary, and credit-balance changes. This is a coarse account-level diagnostic, not run-exclusive accounting: other Codex work during the run can affect it. A 60-tick run now normally takes two snapshots instead of 61. Set `CODEX_PLAN_SNAPSHOT_INTERVAL_TICKS` to a positive interval if you deliberately want extra mid-run diagnostics.
