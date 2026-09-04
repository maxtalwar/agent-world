# Infrastructure upgrade implementation — September 4, 2026

This ledger follows all 30 findings in [the audit](infrastructure-audit-2026-09-04.md). The fixes are on `fix/infrastructure-audit`. Historical benchmark evidence has not been rewritten, and no live provider calls were made.

## Correctness and recovery

| Audit | Implemented change | Validation or remaining scope |
| --- | --- | --- |
| 1 | Trusted failure kinds replace intent-text lifecycle decisions; infrastructure failures freeze resolution; sequential/concurrent exceptions agree. | Incidental failure words, distinct failures, exceptions, and successful concurrent decision salvage have regression coverage. Historical events retain legacy interpretation. |
| 2 | Transactional world tick restores state, RNG, and events; structural action and finite configuration validation occurs before mutation. | Settlement fault injection and malformed agreements pass. This is targeted coverage, not exhaustive injection at every instruction. |
| 3 | Canonical ZCode boundaries and legacy aliases agree through the real factory; unsupported effort fails early. | All seven factories are tested with canonical and historical boundaries, mocking external executables only. |
| 4 | Shared bounded subprocess transport, process-group cleanup, incremental Codex frames, HTTP body watchdog, bounded ACP streams/queues and a single setup/turn deadline. | Real loopback drip, partial frames, noisy stderr, output overflow and inherited pipes pass. Platform DNS/connect setup is still outside the HTTP socket watchdog. POSIX is the managed runtime; Windows-native process-group parity is not claimed. |
| 5 | Content-addressed atomic Codex schemas and explicit per-run schema settings replace shared mutable paths/environment mutation. | Different schema contents retain independent paths. Shared schema/instructions now live in decision_contract.py. |
| 6 | Usage is acknowledged only after fsync; append failures raise; partial records survive rollback; journal write failures do not acknowledge decisions. | Disk-path and injected-write failures covered; appends repair only incomplete trailing JSON and retain complete records. Request-start receipts precede external invocation. Receipts identify possible exposure, not proof a provider charged. |
| 7 | Run/record/logical-decision/physical-attempt identities; distinct agent/tick coverage; committed and attempted spend separate; partial ledgers included and deduplicated. | Duplicate-plus-missing usage fails coverage. Admission count and identity survive restart without usage. Unknown charge exposure is explicit. |
| 8 | Requested model/effort separated from observed fields; every observed model must match; missing identity stays unknown. | Mixed unexpected models block finalization. No unverified alias allowlist or effective-effort inference added; provider evidence remains a prerequisite. |
| 9 | Checkpoints bind to exact ledger bytes/hash, support sibling relocation, and publish generation/digest markers; reports reject mixed generations and ignore uncommitted tail bytes. Failed writers require recovery. | Equal-length corruption, relocation, torn tail and poisoned writer tests pass. A crash between publications requires checkpoint recovery before reporting. Pickles remain trusted-local artifacts. |
| 10 | Pending decisions bind to source, adapter, model, effort, schema and observation; shared validation precedes usage reconciliation; bounded journal reads/writes. | Changed execution identity invalidates cache; changing history policy on resume is rejected. |
| 11 | Quota budget/backoff/resume time survive checkpoints; interruptible wait slices; controller expires overdue quota leases. | Existing quota/controller tests pass. Stop checks occur between wait slices, at most 30 seconds apart. |
| 12 | Controllers/finalizers launch from pinned orchestration source (separately pinned for historical cell code); reused worktrees reject dirty content; executable path/hash and Python identity are saved and checked; core fingerprint covers shared runtime/schema dependencies. | This detects entrypoint changes, not every transitive package file behind a script or remote provider deployment. Historical protocols retain their pinned implementation. |

## Operations and interfaces

| Audit | Implemented change | Validation or remaining scope |
| --- | --- | --- |
| 13 | Provider-ready admission before global worker dispatch; throttle sleeps outside shared locks; stable actor resolution order. | Starvation regression passes. Cross-job/account admission is still independent; aggregate account coordination is a separate deployment feature. |
| 14 | Full-identity session hashes, durable launch intent before spawning, controller recovery after a later-cell failure. | Collision and lifecycle tests cover ownership; a real temporary linked-worktree test checks canonical job lookup. |
| 15 | Model-backed observer launches use managed jobs, unique artifacts, durable selection and pause/resume/stop controls; launch requests serialize. | Restarted client reattaches in tests. Free diagnostic worlds remain in-process. |
| 16 | Detached finalizer, bounded judge process, automatic report retry/backoff, one-shot v6 judge guard, atomic report writes and saved plan-summary preservation. | Finalizer supervision and plan-summary regression pass. No new judge call was made. |
| 17 | Managed dry-run reuses BrainSpec/PopulationSpec and argparse validation; finite/boolean numeric checks; observer uses the same spec and preserves world overrides. | Invalid inputs fail before launch. UI option lists are not completely generated from a new registry; introducing a second registry was avoided. |
| 18 | Shared preparation, static/dynamic serialization, schema, typed outcomes, transport, deadlines, request admission, usage and tool-trace checks extracted. | Provider parsers and flags remain explicit; full decision-method rewrites were unnecessary for the identified defects. |
| 19 | Reject exposed forbidden tool events; preserve provider fences and record executable identity. | Synthetic traces covered. A harness that suppresses traces cannot thereby prove isolation. Vendor/version acceptance canaries remain separate from offline CI. |
| 20 | Added startup/first-byte/completion measurements to establish whether warm transport pooling is worthwhile. | Pooling not adopted: it needs provider-backed setup measurements and fresh-conversation isolation equivalence. Persistent conversations are not a performance-equivalent substitute. |

## Scaling, cost and maintenance

| Audit | Implemented change | Validation or remaining scope |
| --- | --- | --- |
| 21 | Opt-in bounded-v1 observation policy keeps active obligations and defined recent history with omission counts; full-v1 unchanged and required by benchmarks. | 1,000 closed-contract fixture checks pruning and active retention. This changes information exposure and needs separate evaluation before benchmark adoption. Very large active/full histories can still reach vendor argument limits. |
| 22 | Cache stable prompts and dynamic observation serialization; OpenRouter hashes exact transmitted bytes; component-size telemetry retained. | Existing interface byte fixture passes; no token/billing saving inferred from character counts. |
| 23 | Incremental event indexes for feedback/ledger/counts; caches excluded from checkpoints/transaction copies. | Historical behavior tests and synthetic growth probe pass. Full authoritative history remains in memory; archival/streaming storage is not implemented. |
| 24 | Incremental JSONL tails, cached observer projections, retained latest control event, snapshot ring eviction and correct historical tick cutoff. | Repeated unchanged reads improve substantially. Observer history is explicitly sampled, not a durable every-tick archive; cold reads still process history. |
| 25 | Request admission limits for calls/reported tokens/reported cost, bounded output, request receipts and phase timings; budget exhaustion pauses at frozen tick. | Calls are a hard admission limit. Token/cost thresholds may overshoot with in-flight calls and depend on reported usage; unknown fields block further budgeted admission. Detailed parse/journal/report phase tracing is not exhaustive. |
| 26 | Added lifecycle/identity/failure regressions; deterministic frontier terrain replaces skips. | Fast existing tests retained. No mass deletion or assertion-mirroring suite added. |
| 27 | Real local socket/stdio/process tests alongside provider envelope fixtures. | Offline CI does not certify every installed vendor CLI release or remote behavior. Paid canaries remain separate. |
| 28 | Extracted focused modules for contracts, validation, transport, deadlines, request context, projections, observer jobs and artifact export. | Large world/session/report modules remain where splitting would add unrelated churn; no line-count target. |
| 29 | CI rebuilds/compares database projections and tests a built wheel outside checkout; stale architecture/API docs corrected. | Local database integrity/projection checks and installed-wheel smoke pass. Runtime still has no required third-party dependencies. |
| 30 | Artifact inventory and checksum export include reference/liveness information, relative export paths and sensitive-file exclusions. | Export test passes. No automatic deletion policy or portable non-pickle checkpoint format introduced; exported pickles require trusted compatible code. |

## Evidence

Final validation: **528 tests passed, zero skips**, plus compile checks, database regeneration comparison and installed-wheel smoke. Exact environment and source digest are in [validation.json](../reports/infrastructure-upgrade-2026-09-04/validation.json). The suite uses synthetic brains, temporary files, local sockets and short local processes. No benchmark/model result is claimed.

The [timing evidence](../reports/infrastructure-upgrade-2026-09-04/timing.json) repeats the audit probe on the same host. At 100,000 synthetic events, repeated observation construction was 0.096 ms (baseline 5.872), repeated control reads 0.029 ms (240.357), and repeated observer state reads 0.098 ms (542.096). These measure warm derived state and unchanged files, not cold load, provider latency or monetary savings. The 100 ms drip deadline interrupted at 100 ms; the 50 ms partial-frame deadline interrupted at 50 ms.

The installed-wheel smoke checks packaged assets, CLI execution, a two-tick free simulation, reports and checkpoint loading outside the checkout. Temporary database regeneration is compared to the committed database's generated projection; curated leaderboard prose is not mistaken for raw generated output.
