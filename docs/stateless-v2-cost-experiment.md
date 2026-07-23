# Stateless v2 cost experiment

This paired experiment isolates connector-profile overhead for Codex and Cursor agents.

Experiment root:

`runs/experiments/stateless-v1-v2-cost-30a-50t-seed41-20260723-041213`

Both cells use world seed 41, stratified assignment seed 117, the `organic-generalists` preset, medium reasoning effort, baseline action feedback, raw decisions, and 50 target ticks. Each civilization contains seven Sol, seven Terra, eight Luna, and eight Grok 4.5 agents. The control uses `stateless-v1` plus `stateless`; the treatment uses `stateless-v2` plus `stateless`. `bounded-session-v1` is excluded.

The only intended treatment differences are the stable empty workspaces used by Codex and Cursor and the disabled irrelevant Codex skills in `stateless-v2`. Both profiles use the same newest installed Codex CLI so model availability and CLI version are not confounds.

Primary Codex outcomes are exact simulation credits, prompt tokens, cached tokens, output and reasoning tokens, successful decision coverage, and credits per successful call. Normalize total run cost for deaths and provider failures before interpreting it. Cursor does not expose comparable plan-window consumption; the user reported approximately 34% of the weekly Cursor limit used before launch preparation, followed by three bounded Cursor smoke calls. Cursor analysis should therefore emphasize successful calls, provider token telemetry, cache behavior, latency when available, and the user's post-run usage reading.

Both cells retain the automatic tick-5 model-health gate. Any partial tick discarded for provider or quota failure belongs only in its separate partial-usage audit ledger.

## Corrected stateless-v3 follow-up

The original `stateless-v2` implementation disabled only five bundled Codex
skills and used a workspace path that was stable only within one Python process.
It did not disable plugin, plugin-sharing, remote-plugin, skill-search,
skill-dependency-installation, or the second multi-agent feature. Preserve that
profile for reproduction; the corrected implementation is `stateless-v3`.

Before making model calls, `codex debug prompt-input` measured the rendered CLI
scaffolding at 14,913 JSON characters for `stateless-v1`, 12,489 for
`stateless-v2`, and 6,977 for `stateless-v3`. The corrected profile also uses
deterministic provider-specific workspace paths across processes.

Follow-up root:

`runs/experiments/stateless-v1-v3-cost-30a-10t-seed41-20260723-145447`

The follow-up repeats the same seed, assignment, 30-agent population, medium
effort, baseline feedback, raw decisions, concurrency, and stateless
conversation boundary for 10 ticks. Both cells completed tick 10, both tick-5
health gates passed, all 600 decisions succeeded, and usage coverage was 100%.

### Connector results

| Metric | Standard v1 | Corrected v3 | Change |
|---|---:|---:|---:|
| Codex prompt tokens/call | 14,185 | 13,439 | -5.3% |
| Codex uncached input/call | 6,731 | 6,115 | -9.2% |
| Codex cached share | 52.5% | 54.5% | +2.0 pp |
| Codex output tokens/call | 344.1 | 342.1 | -0.6% |
| Codex reasoning tokens/call | 259.4 | 256.4 | -1.2% |
| Codex simulation credits/call | 0.7185 | 0.6835 | -4.9% |
| Codex mean decision latency | 10.42 s | 10.45 s | +0.2% |
| Cursor prompt tokens/call | 21,034 | 21,269 | +1.1% |
| Cursor cached share | 17.34% | 17.38% | +0.05 pp |
| Cursor output tokens/call | 1,805 | 1,657 | -8.2% |
| Cursor mean decision latency | 37.00 s | 30.87 s | -16.6% |

All 30 tick-zero Agent World request hashes matched across cells. On those
identical inputs, Codex prompt tokens/call fell 3.5% for Sol, 6.4% for Terra,
and 6.7% for Luna. Cursor changed by only 0.05%. This is the cleanest evidence
that v3 removes real Codex input overhead while the Cursor subscription CLI
does not expose an equivalent harness control.

Full-run Codex credits fell 8.4% for Sol and 20.4% for Luna, but rose 19.0% for
Terra because Terra's cached share fell 11.4 percentage points and its output
grew 17.1%. The aggregate 4.9% credit reduction is promising, but model output
and cache allocation remain stochastic even when the initial supplied inputs
are identical. Use captured-input replay rather than an evolving civilization
to estimate the infrastructure effect more precisely.

### Ten-tick world smoke test

Both civilizations retained all 30 agents and had two survival-damage events.
Invalid-action rates were close (11.6% v1 versus 12.1% v3), as were contention
rates (1.1% versus 1.3%). The v3 world completed three agent-owned farm plots,
including one cross-cohort cooperative build, while v1 completed none. V3 ended
with wealth 535 and Gini 0.1088 versus wealth 524 and Gini 0.1122 in v1.
Conversely, v1 produced more speech (56 versus 25), trade offers (6 versus 4),
and gifts (2 versus 1); neither world accepted a trade.

These world differences are not evidence that the hidden connector scaffolding
caused a behavioral change. The treatment leaves the Agent World rulebook,
schema, observation, feedback, and memory unchanged, and a single 10-tick pair
diverges rapidly through stochastic outputs and simultaneous world resolution.
Treat the civilization result only as evidence that v3 remains functional and
does not obviously degrade survival or action validity.
