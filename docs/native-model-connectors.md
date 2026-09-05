# Antigravity and Muse Code connectors

Agent World supports the official native CLIs through `AntigravityBrain`
(`antigravity_cli`) and `MuseBrain` (`muse_cli`). These are laboratory
connectors; benchmark certification remains the responsibility of the selected
versioned recipe. No model-backed runs are launched by installation or setup. Explicitly authorized
live serial and four-worker tests subsequently passed; see the
[readiness evidence](native-connector-validation-2026-09-05.md).

## Installation and accounts

Install in the same Linux/WSL account that runs Agent World. Official installers:

- [Google Antigravity installation](https://www.antigravity.google/docs/cli/install/)
- [Meta Muse Code](https://dev.meta.ai/), installer at
  [dev.meta.ai/install.sh](https://dev.meta.ai/install.sh)

The setup implementation was checked with Antigravity CLI **1.1.26** and
Muse Code **1.0.3 (1.0.3-R2198.1)** on Linux/WSL. Installers place binaries under
`~/.local/bin`; start a new login shell or add that directory to PATH.

```bash
export PATH="$HOME/.local/bin:$PATH"
agy                    # Google OAuth, onboarding, account eligibility
agy models             # exact model slugs; no inference
muse login             # Meta device authorization
python3 -m agent_world.cli setup --write-profile
```

Google can accept OAuth while rejecting the account's Antigravity eligibility.
In the setup check, the native TUI requested a personal Google account after
rejecting a university account; `agy models` still returned a catalog.
Finish onboarding and check the TUI's eligibility result. Antigravity preflight
requires a valid `agy --print /usage` account-status table, which does not call
a model. CLI 1.1.26 returns empty stdout from both `agy agents` and
`agy --print /agents`, even though the interactive `/agents` panel correctly
discovers the workspace definition. That empty output is not an authentication
or discovery failure. The isolated definition was verified in that panel with
a Google AI Pro account. The subsequent live smoke tests passed.

Muse preflight checks binary version and the presence of account credentials.
It does **not** prove that a saved token is valid, that a plan has quota, or that
a particular model is entitled. Complete native sign-in, then perform an
explicitly authorized smoke test before a long benchmark. Credentials and the
host profile remain outside Git. Do not paste account tokens into run configs.

Antigravity removes API-key overrides and refuses CLI settings that select an
API provider or enable credit overages. Its billing label is `google_ai_plan`.
Muse removes API-key and endpoint overrides and reads native account
authentication. Its label is `meta_account`: the adapter does not establish
whether that account has a subscription or paid usage entitlement. Neither
adapter invents a zero-dollar cost when the CLI does not report one.

## Models, effort, and managed runs

The authenticated Google catalog on 2026-09-04 included
`gemini-3.7-flash-low`, `gemini-3.7-flash-medium`, and
`gemini-3.7-flash-high`. Use the exact slug and matching effort. The connector
does not silently replace unavailable models or change effort. Muse defaults
to `muse-spark-1.3`; live calls with the configured account passed the readiness tests.

Example ordinary experiment config, to save and launch **after account setup
and authorization to spend model quota**:

```json
{
  "schema_version": 1,
  "run_id": "gemini-37-native-smoke",
  "kind": "experiment",
  "question": "Does the native connector return valid decisions with usable telemetry?",
  "model": {
    "brain": "antigravity",
    "id": "gemini-3.7-flash-low",
    "reasoning_effort": "low"
  },
  "seeds": [11],
  "runtime": {"ticks": 2, "agents": 1, "max_workers": 1},
  "harness": {"connector_profile": "connector-v3"}
}
```

For Muse, use brain `muse`, model `muse-spark-1.3`, and a distinct run ID.
Launch with `agent-world run --config CONFIG.json`; the manager owns detached
execution, quota pauses, resume, and finalization. This example makes no
benchmark claim. See [run configuration](run-quickstart.md) for recipes and
benchmark configs. Population shorthand infers these native connectors from
bare `gemini-*` and `muse-*` names; use an explicit provider for other routes.

Both connectors implement **fresh-conversation only**, including when the
caller selects connector-v2 or connector-v3. Each decision gets a new temporary
workspace. Persistent conversation mode is rejected. Machine-local defaults
start each provider at four workers, clamped by the population and global cap.
Use `runtime.provider_max_workers` keys `antigravity` and `muse` to override.

## Decision boundary and telemetry

Antigravity selects a workspace-local custom main agent with empty tool, MCP,
skill, and plugin lists, plus sandboxing and structured JSON output.
See Google's [custom agent specification](https://www.antigravity.google/docs/subagents)
and [headless protocol](https://www.antigravity.google/docs/cli/headless/).
Muse uses isolated config/data directories, disabled shell/write/web execution,
untrusted approval mode, no approval-judge calls, and one model step. Native
reminder capabilities are disabled to avoid background model calls.

Muse's disable flags do **not** remove every tool definition from the model's
schema. The adapter audits emitted tool/delegation activity and treats an
attempt as a harness failure. It does not claim an OS security sandbox. Empty
workspaces and isolated native memory reduce cross-agent context exposure;
the CLI remains trusted local software.

Both adapters require one unambiguous terminal envelope. Invalid decision JSON
is attributed to model output; malformed CLI envelopes, tool attempts, and
identity conflicts are harness failures. Trusted quota/authentication
diagnostics pause the provider through the shared runtime. Model-written words
such as "quota exhausted" cannot trigger a provider pause.

Muse JSONL stdout omits token usage. The adapter reads the matching session and
root-run records from its temporary retained trace, counts `model_completed`
once, and ignores mirrored goal-attribution records. Unknown counters remain
null. The native trace hash is recorded; temporary transcripts are removed when
the call ends, while normalized usage and provenance remain in Agent World's
ledger. Full native transcripts are not retained as benchmark evidence.

Crucially, Muse 1.0.3's `model_completed.model` repeats the **request model**,
even when a synthetic provider response names a different model. It is saved
as `native_configured_model`, never `response_model`. Model and effort
provenance remain `requested_only`. Antigravity also remains requested-only
unless its result explicitly reports those facts. These limitations must remain
visible during certification; do not relabel configured identity as observed.

Provider cost and equivalent API pricing may remain unavailable until a
verified rate card is added. Missing telemetry or pricing is not a free call.

## Local validation without quota

```bash
python3 -m unittest discover -s tests -q
AGENT_WORLD_TEST_MUSE_NATIVE=1 python3 -m unittest discover -s tests -p test_muse_native_offline.py -v
```

The opt-in test invokes the installed Muse binary against a loopback fake API
with synthetic credentials. It checks exactly one request per decision, low
effort, recovery of 100 input / 20 output / 50 cached / 8 reasoning tokens, and
the configured-versus-observed identity distinction. It sends no provider
inference request and cannot establish live account/model readiness.
