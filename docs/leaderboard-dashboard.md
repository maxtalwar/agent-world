# Private leaderboard dashboard

Open **http://desktop-lbmut2i.tailb88da4.ts.net:8091/** from a device connected to
the same Tailscale network. The host must be awake and signed in to Windows.
The dashboard refreshes every 30 seconds while its tab is visible.

## What it shows

- Canonical model rankings from `data/model-benchmarks.sqlite`, including
  explicitly labeled controlled reasoning variants.
- Managed benchmark studies discovered in `runs/jobs/*/job.json`.
- Separate boards for each recipe ID and recipe fingerprint, including recipes
  retained only in their original run worktrees.
- Replicated scores, cost per run, reasoning per decision, and individual seed
  scores where available. Select a model to inspect its evidence.
- Controller progress, quota/attention states, and stale-heartbeat warnings.
  A heartbeat older than two minutes cannot present a nonterminal run as live.

The dashboard can start standard benchmarks through the managed interface and
assign Astra supervision. It does not change certification policy or write
results into the canonical database. New managed
studies appear without a dashboard deployment. Admission to an established
canonical pool still requires the normal source-catalog maintenance workflow.

Only final reports enter the existing `aggregate_benchmark_reports` function.
It executes in the study's retained scoring checkout, verifies recipe identity,
and applies the original source-fingerprint and replication rules. Raw counts
are pooled by that scorer; the dashboard never averages rounded seed scores.
Incomplete, duplicate-seed, and rejected results remain outside replicated
rankings. Different study jobs are never pooled together. A repeated model may
therefore have multiple independently labeled study rows.

The original run worktrees must remain available for uncataloged recipes.
Unavailable or incompatible scoring source is reported as an evidence warning.
The application does not guess replacement formulas.

## Run locally

No extra Python dependencies or JavaScript build step are required:

```sh
python3 -m agent_world.leaderboard --root /path/to/agent-world --port 8091
```

The server binds to loopback by default. The server exposes bundled assets, `/healthz`, read-only leaderboard data,
and protected benchmark review/start/supervisor-reconnection endpoints.
Inter is served locally, with its OFL license in `agent_world/static/inter-OFL.txt`.

## Windows / WSL installation

`scripts/install-leaderboard.ps1` installs this host's persistent deployment.
It accepts `-Distribution` and `-Repository` arguments. Run the trusted installer
from PowerShell; a UNC checkout may require copying the installer to a local
Windows path first under the host's script execution policy.

The installer:

1. Copies an app release to `.local/leaderboard-app`, independent of Git branch
   switches. Evidence remains live in the canonical repository.
2. Registers the **Agent World Leaderboard** Windows scheduled task. It starts
   at Windows sign-in, restarts on failure, runs hidden, and keeps the WSL server
   attached to a durable task instead of a Codex command session.
3. Configures Tailscale Serve on HTTP port **8091**, accessible only in the
   tailnet. Existing routes on other ports are preserved.

Re-run the installer to deploy code updates. Live data needs no redeployment.
Logs are in `.local/leaderboard.log`; the launcher rotates logs over 10 MB on
restart. Stop/start the app with `Stop-ScheduledTask` /
`Start-ScheduledTask -TaskName 'Agent World Leaderboard'`.
Disable its Tailscale route with `tailscale serve --http=8091 off`.

## Validation

```sh
python3 -m unittest discover -s tests -p test_leaderboard.py -v
node --check agent_world/static/leaderboard.js
```

The tests cover canonical score parity, controlled variants, absent costs,
partial/duplicate evidence, recipe separation, stale status, terminal-state
precedence, refresh caching, path containment, and HTTP route restrictions.


## Starting a benchmark from the page

Choose **Start benchmark**, select the recipe and connector, and choose or enter
the exact model ID. **Review benchmark** runs the existing managed CLI's
`--dry-run` validation. The review shows the fixed population, horizon, required
seeds, reasoning effort, and **GPT-6 Astra · Low** supervisor. Only the final
**Start benchmark** action authorizes model-backed execution.

The initial review itself makes no model calls. Connector authentication and
target model callability are checked by the existing managed startup gate;
unknown IDs are never silently mapped to similarly named models.

Launch controls require the configured Tailscale/loopback hostname, a matching
Origin, JSON content type, and a same-origin request token. No cross-origin
launch API is exposed. The installer enables this feature in the machine-local
`.local/leaderboard-settings.json` and records the Windows Codex binary that
advertises Astra at low effort. If Astra is unavailable, launching is blocked.

### Source and execution ownership

The source chooser finds clean retained recipe checkouts. Review prepares an
independent local source clone at `.local/leaderboard-sources/COMMIT`. Its
`runs/jobs` and `runs/managed` paths point to the shared run registry; its local
`.env` link uses the host's existing credentials without copying or publishing
them. Historical managers derive their controller commit from their repository
HEAD, so this clone pins both the launcher and controller to the reviewed
commit even while another task changes the main checkout. All simulation cell
worktrees and detached controllers still come from the normal managed launcher.
The dry-run plan must confirm both exact commits.

A transactional SQLite request queue under `.local/leaderboard-launches`
persists each reviewed configuration and its hash. Reviews expire after ten
minutes. Repeating the final submission returns the same request/run ID.
Unfinished studies of the same model/connector/recipe prevent duplicate launches.

A durable tmux worker assigns a persistent Astra task before invoking
`python3 -m agent_world.cli run --config CONFIG`. It persists the supervisor
task ID before launch and requires a successful low-effort Astra assignment
turn before any benchmark model calls. Retries and app restarts inspect the existing job and
resume the same supervisor; they do not issue another launch for that job.

Astra runs through the local Codex App Server with explicit
`model=gpt-6-astra`, `effort=low`, workspace-write sandboxing, and automatic
approval review. The app never silently approves an unresolved client-side
approval request. The deterministic run controller retains responsibility for
healthy polling, startup gating, quota waits, checkpoint recovery, and
finalization. The Astra task is awakened only for lifecycle changes, completion,
or attention events—not changing ticks. Its notes and blockers appear under
**Your benchmark runs**. **Reconnect supervisor** reattaches supervision to
an existing run; it does not launch another study.

General experiments and custom world configurations remain outside this form.
Run interpretation and canonical catalog admission still follow the reporting
workflow after the analysis-readiness gate.

### Launch validation

```sh
python3 -m unittest discover -s tests -p 'test_leaderboard*.py' -v
node --check agent_world/static/leaderboard-launch.js
```

Tests simulate the paid boundaries and verify fixed configurations,
source/configuration tamper detection, repeated submissions, duplicate studies,
CSRF/Origin checks, exact Astra settings, assignment-before-launch ordering,
and recovery without relaunch. Deployment smoke checks use real recipe dry runs
and the real Codex model catalog without starting a paid benchmark.

Codex integration follows the [official App Server interface](https://developers.openai.com/codex/app-server/).
