# Native connector readiness — 2026-09-05 UTC

**Antigravity and Muse Code passed live serial and four-worker tests.** Both
are operational for managed Agent World experiments at their configured low
effort. These are diagnostic checks, not leaderboard results or certification.

All four runs used seed **11**, the **frontier-generalists** preset,
connector-v3, fresh conversations, and a two-tick horizon. A one-agent run
checked basic transport; a four-agent run exercised each default worker pool
twice. No additional seeds or economy analyses were requested.
Transfer accounting is **not_required** for this question.

| Connector / model | Workers | Agents | Completed ticks | Valid decisions | Distinct sessions | Failures / tool attempts |
|---|---:|---:|---:|---:|---:|---:|
| Antigravity / gemini-3.7-flash-low | 1 | 1 | 2/2 | 2/2 | 2 | 0 / 0 |
| Antigravity / gemini-3.7-flash-low | 4 | 4 | 2/2 | 8/8 | 8 | 0 / 0 |
| Muse Code / muse-spark-1.3 | 1 | 1 | 2/2 | 2/2 | 2 | 0 / 0 |
| Muse Code / muse-spark-1.3 | 4 | 4 | 2/2 | 8/8 | 8 | 0 / 0 |

All twenty decisions returned valid contract JSON and input/output token
counts. No model-output, provider, authentication, quota, or harness failures
occurred. Every call used a separate native session. This verifies the tested
fresh-session boundary; it is not a claim of OS-level isolation.

## Usage and limits

| Connector, both tests combined | Input tokens | Cached input subset | Output tokens | Reasoning output subset |
|---|---:|---:|---:|---:|
| Antigravity | 218,318 | 163,531 | 10,439 | 7,835 |
| Muse Code | 263,515 | 0 | 7,122 | 5,839 |

Cached input is included in input; reasoning is included in output. Neither
CLI reported a monetary charge. Provider cost is **unavailable**, not zero.
Equivalent API pricing is also unavailable in the current rate card.
Subscriptions and provider quota are separate from token-derived API costs.

Model and effort provenance remain **requested_only**. The native CLIs do not
attest the provider's returned identity in the evidence consumed here. Muse's
completion model field was separately proven to repeat the configured request
in the offline fake-API test. No stronger provenance claim is made, and future
benchmark certification must evaluate the selected recipe's evidence rules.

## Recovery and validation

Both four-agent live checkpoints were loaded through the trusted checkpoint
reader at completed tick 2. All four brains restored their exact model, effort,
connector profile, conversation mode, and CLI version. The brain factory
verified executable hashes against the saved execution environment. Both
restored configurations passed native preflight, with **zero additional model
calls**. This tested reconstruction of completed checkpoints; it did not
deliberately kill an in-flight paid request.

The full **587-test suite passed**, including the installed Muse binary against
a loopback fake API. Existing tests cover quota/authentication freezing, strict
JSON attribution, tool-attempt rejection, ambiguous terminal streams, usage
deduplication, and checkpoint incompatibility rejection.

Live runs were pinned to clean commit
`e76bebc4b6cff43abe4b532e217bcece0998f85f`, using Antigravity **1.1.26** and
Muse Code **1.0.3 (1.0.3-R2198.1)**. The only subsequent runtime-facing
correction was shared cost reporting: unknown provider charges now remain null
instead of appearing as zero. The original reports were preserved before
regeneration; simulation events, ledgers, manifests, and checkpoints are
unchanged.

## Evidence

Local hashed audit and checkpoint verification:
`runs/diagnostics/native-connectors-20260905/validation.json`.

Each managed cohort has the same ID as its run plus `-seed-11`:

- `antigravity-native-smoke-20260905-a`
- `antigravity-native-concurrency-20260905-a`
- `muse-native-smoke-20260905-a`
- `muse-native-concurrency-20260905-a`

Artifacts are under `runs/managed/RUN_ID/seed-11/`: `run.jsonl`,
`run-usage.jsonl`, `run-manifest.json`, `run-checkpoint.pkl`, and
`run-report.{json,md}`. Job configs, source cohorts, and detached-supervisor
evidence are under `runs/jobs/RUN_ID/`. Raw run data and credentials stay local.

For installation and managed launch syntax, see
[native model connectors](native-model-connectors.md).
