# Leaderboard model discovery

Model identities come from current connectors, never historical runs. Results
and activity only determine the recipe-specific "To benchmark next" shortlist.

Claude SDK initialization returns a short recommended menu. Other live connector
catalogs supply additional explicit Claude version candidates. Each candidate
must pass Claude Code's built-in `/model EXACT_ID` command with an exact-version
selection and zero model turns in a disposable, nonpersistent session. Checks
are cached for ten minutes, keyed by executable version. This verifies selection,
not inference or remaining quota; normal runtime identity guards still apply.

ZCode reads the same `provider.zai.models` or `providers.zai.models` catalog as
benchmark preflight, respecting `ZCODE_CONFIG_PATH` and otherwise using
`~/.zcode/cli/config.json`. Only IDs and names are returned, never credentials.

Native connectors win equivalent-model deduplication. The default browse view
shows native models without results or studies in the selected recipe. All models
and search retain access to the full catalog. Lab filters apply to both views.

## Decision-model eligibility

Discovery is not sufficient for inclusion. OpenRouter models must explicitly
advertise text input and exclusively text output. Image/audio/video inputs are
allowed; generated image/audio/video outputs are not. Missing modality metadata
is excluded rather than assumed compatible. Across all connectors, explicitly
named image generators, speech generators/transcribers, embedding and reranking
endpoints are excluded, including when a connector supplies no modality metadata.
This filters the benchmark picker; it does not restrict general laboratory runs.

## Muse tiers and study identity

Standard and Contributor use the same version identity for shortlist history and
active-launch duplicate checks. Their exact execution IDs remain unchanged in
requests and run evidence. Active Muse versions are omitted from all picker views,
including searches, and the server rejects duplicate tier launches from stale pages.

As checked on 2026-09-06, Meta's authenticated Muse Code subscription documentation
(<https://dev.meta.ai/docs/muse-code/subscriptions>) describes plan usage separately
from per-token API pricing. It does not establish a Contributor multiplier for
subscription allowance. Lower API pricing alone is insufficient to switch the
benchmark default or hide the tier's distinct data-use terms. Standard remains
unchanged pending documented subscription savings.

The picker exposes only Standard Muse Spark entries, one per version. Contributor
entries are omitted, including when Standard is unavailable, so hiding the tier
label never silently opts a launch into different data-use terms. Existing run
metadata and historical execution IDs are retained.

ZCode advertises only native `max` reasoning, matching BrainSpec validation. Its
models are omitted from fixed recipes requiring any other effort. General
experiments and genuinely max-effort recipes remain supported.

## Monitoring handoff inbox

The detached launcher never acquires the desktop monitoring task's writer.
Confirmed page requests are the durable SQLite inbox. Run Monitoring discovers
pending requests through `monitor-list`, accepts the exact IDs in one call to
`monitor-accept --requests ID ... --thread CONFIGURED_THREAD_ID`, then leaves
initial launch to the dispatcher. A local event watcher performs discovery without model calls. A short-lived
Astra low-effort worker accepts the batch; the fixed agent heartbeat is disabled.
Until that event is handled the page says the request is queued for acknowledgment.

Acceptance validates the entire batch before committing ownership. It is
idempotent and does not remove studies from the monitoring worklist. The
separate `monitor-ack` remains reserved for verified completion or an explicit
external/evidence blocker. After ownership is recorded, the dispatcher launches
only the reviewed configuration through the managed CLI. Existing job records
prevent relaunch after dispatcher recovery. No second app-server connection,
per-model agent task, or repeated handoff prompt is required.

The Codex catalog client still uses the persistent WSL init interop socket when
available. Local process diagnostics remain in
`.local/leaderboard-launches/supervisor-diagnostics.log`.

## Event-driven monitoring and quota use

`leaderboard_event_monitor.py` runs within the durable dispatcher's cheap local
30-second loop. Healthy progress and quota waits create no agent event, including
when all cells share a future reset. Controllers continue to own quota resumption.
New page launches, actionable attention and terminal outcomes are fingerprinted
and batched. Each fingerprint is reserved durably before one detached ephemeral
GPT-6 Astra low-effort worker starts. No recurring Codex agent heartbeat is used.
A blocked provenance review is handled once; repeated timestamps and unchanged
blockers do not create new agent calls. New evidence or an explicit reopening is
required to re-review an acknowledged evidence dependency.

Workers use `codex exec --ephemeral --approve-for-me` against the shared worklist,
not a second writer on the desktop task. They do not create persistent monitoring
tasks or poll/sleep. Event records, JSONL output and final notes are retained in
`.local/leaderboard-launches/events/`; the final notes also appear on each request.
Failed or interrupted workers are surfaced for attention rather than automatically
replayed and charged again. The Run Monitoring task remains available for human
follow-up; its old 15-minute automation must remain paused. The installer enables
the local watcher through `event_monitor_enabled`.
