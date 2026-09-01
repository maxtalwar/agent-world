# Agent connector and conversation boundaries

Agent World versions two independent pieces of the model boundary:

- `connector_profile` controls provider-invocation infrastructure.
- `conversation_mode` controls whether an agent keeps provider conversation history.

Keeping these axes separate makes token-efficiency and behavioral experiments interpretable.

Canonical names describe only their own axis. Historical names remain accepted when
reading CLI input, manifests, and checkpoints, but new output always uses the canonical
name:

| Historical alias | Canonical name |
| --- | --- |
| `stateless-v1`, `stateless-v2`, `stateless-v3` | `connector-v1`, `connector-v2`, `connector-v3` |
| `stateless` | `fresh-conversation` |
| `bounded-session-v1` | `persistent-conversation-v1` |

## Connector profiles

### `connector-v1`

This is the historical control. Every decision starts a fresh provider conversation.
Codex and Cursor use a newly named empty workspace for each decision. Codex selects
the numerically newest local executable, including prerelease builds.

### `connector-v2`

This preserves the first lean-connector experiment. It keeps the agent experience
stateless while:

- Codex and Cursor reuse a stable empty workspace, improving the chance that
  provider prompt caches see a stable prefix within one Agent World process.
- Codex uses the newest installed CLI, matching the control so model support and
  CLI version do not confound the connector-profile comparison.
- Codex explicitly disables bundled skills that are irrelevant to simulation decisions.
- Usage records identify the connector profile and whether full context was sent.
- Claude keeps its existing lean path: its coding system prompt is already replaced,
  tools and settings are disabled, and its empty workspace is already stable.

`connector-v2` does not change the rulebook, observation, schema, or agent memory.
Its workspace path is randomly created at process start, and it does not disable
the CLI's plugin and skill-discovery features. Keep this profile available only
to reproduce the original experiment.

### `connector-v3`

This is the corrected lean stateless connector:

- Codex, Cursor, and ZCode use deterministic provider-specific workspaces that remain the
  same across Agent World processes and checkpoint resumes.
- Codex disables multi-agent, shell, app, plugin, remote-plugin, plugin-sharing,
  skill-search, and skill-dependency-installation features that are irrelevant
  to a simulation decision.
- ZCode runs in plan mode with its coding, browsing, delegation, and skill tools
  explicitly disallowed. It receives one combined, JSON-only prompt because the
  current headless CLI exposes neither a system-prompt override nor a structured
  output schema flag.
- Bundled Codex skills remain explicitly disabled.
- The rulebook, observation, output schema, action feedback, and agent memory are
  unchanged. The static rulebook is still supplied on every stateless request so
  a fresh model invocation has the rules, but its byte-stable prefix can qualify
  for provider prompt caching.

## Conversation modes

### `fresh-conversation`

Every decision receives the full static rulebook plus current private observation in
a fresh provider conversation.

### `persistent-conversation-v1`

Each simulated agent gets its own private provider conversation. The first turn receives
the full rulebook and observation. Later turns resume the same provider session and send
only the new dynamic observation. After `session_max_turns` successful decisions, the
conversation rotates and the next turn starts fresh from the current Agent World state.

The simulation remains the canonical memory owner. Existing `memory_updates`, current
world state, and action feedback seed every fresh or rotated conversation.

Provider conversations mutate outside Agent World's transaction boundary. A process can
therefore fail after a provider recorded a turn but before the world committed that tick.
For clean completed-tick recovery, checkpoints retain provider-session provenance but
intentionally start fresh provider conversations when resumed. Runs also abandon all
active sessions before checkpointing a tick discarded for provider or quota failure.

Usage records include the connector and conversation versions, generation, turn,
resume/full-context flags, rotation limit, and provider session ID where available.

## Recommended comparisons

Behavioral effect of provider conversation memory:

- Control: `connector-v3` + `fresh-conversation`
- Treatment: `connector-v3` + `persistent-conversation-v1`

Infrastructure token effect:

- Control: `connector-v1` + `fresh-conversation`
- Treatment: `connector-v3` + `fresh-conversation`

Use only matched Codex and Cursor cohorts for the infrastructure comparison. Claude is
intentionally unchanged by the connector-v3 optimization and would dilute the treatment.
Compare successful decision coverage, prompt and cached tokens, plan drawdown, latency,
and provider failures before comparing world outcomes.

## CLI examples

Lean stateless run:

```bash
python3 -m agent_world.cli run \
  --brain codex --model gpt-5.6-luna \
  --connector-profile connector-v3 \
  --conversation-mode fresh-conversation \
  --ticks 20 --agents 5
```

The same connector with bounded conversation memory:

```bash
python3 -m agent_world.cli run \
  --brain codex --model gpt-5.6-luna \
  --connector-profile connector-v3 \
  --conversation-mode persistent-conversation-v1 \
  --session-max-turns 10 \
  --ticks 20 --agents 5
```
