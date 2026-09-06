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

The dashboard does not run simulations, resume jobs, classify transfers, change
certification policy, or write results into the canonical database. New managed
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

The server binds to loopback by default. The only routes are the dashboard's
bundled assets, `/healthz`, and the read-only `/api/leaderboards` endpoint.
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
