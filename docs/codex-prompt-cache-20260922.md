# Native Codex rulebook caching, 2026-09-22

## Finding

The native Codex CLI can reuse Agent World's rulebook cache through ephemeral
forks of a static-only template. Codex 0.154.0 assigned a new cache key to each
fresh call and each fork. Official release 0.156.0 includes shared cache
affinity for ephemeral root-thread forks. Local-only request capture confirmed
the fresh-call key changes; the released implementation is in
`codex-rs/core/src/session/session.rs` and `core/src/client.rs` at upstream
`rust-v0.156.0`. A relay is not needed and was not used.

On `gpt-5.6-luna`, low effort, seed-11 observations, three fresh 0.154 calls
each used 11,033 input tokens and zero cache reads. Moving the static rulebook
to `model_instructions_file` reduced input to 7,480 but still produced no
cache reads. This changes the coding preamble, so it is a separate treatment.

With 0.156 native forks, two of three decisions read 11,008 cached tokens out
of 11,760 new input tokens (93.6%); the third missed. The static template cost
11,319 input and 41 output tokens once. Cache reuse is best-effort, not a
guarantee. These are small harness diagnostics, not benchmark replications or
measurements of subscription quota. No full-run saving has been established.

The managed integration run `codex-shared-prefix-smoke-20260922` then completed
one frontier tick with three agents on seed 11, launch source `239e1f1`, low
effort and one worker. All three decisions read 11,008 cached tokens out of
12,329 / 12,369 / 12,374 new input tokens (about 89%). They have distinct native
session IDs and the same static template ID. The ledger has exactly four rows:
one 11,896-input / 25-output template creation and three fork deltas. The
startup health gate passed, with zero invalid action proposals. This establishes
end-to-end operation, not long-run or parallel-worker cache reliability.
See [the retained measurement summary](codex-cache-measurements-20260922.json).

Raw diagnostic evidence is retained locally in
`.local/codex-cache-layout-20260922/`,
`.local/codex-cache-native-fork-20260922/`,
`.local/codex-cache-native-fork-0156-20260922/`, and
`.local/codex-cache-resume-20260922/`. Their original `usage` fields are raw CLI
cumulative totals. The checked-in probe now preserves `raw_cli_usage` separately
and computes fork deltas in `usage`.

## Accounting and isolation

`codex exec` emits cumulative conversation totals as `turn.completed.usage`.
For example, the new fork's 23,079 input tokens include its template's 11,319:
the actual new request used 11,760. Charging both the template and the fork's
raw total would bill initialization twice. The new mode records one explicit
`usage_kind=cache_template` row, with no agent or tick, then subtracts all five
inherited token counters from each fork. Template identity and original usage
are retained in the decision metadata. Older persistent-conversation ledgers
require their own cumulative-usage audit before cost comparisons; this change
does not rewrite them.

The template contains the shared instructions, rulebook, a fixed initialization
request, and exactly one fixed `ready` response. It contains no agent observation
or decision. Every observation goes to a fresh ephemeral fork of that template,
never a sibling decision. The template is scoped by run runtime, model, effort,
CLI, schema, and exact static text. Its native rollout digest is checked before
and after each fork; changed history fails closed. A resumed process creates a
new template and accounts for its creation again.

## Using the opt-in mode

Use Codex CLI 0.156.0 or newer and set these managed experiment fields:

```json
"harness": {
  "connector_profile": "connector-v3",
  "conversation_mode": "shared-prefix-fork-v1"
}
```

The smoke configuration is
`configs/run-configs/codex-shared-prefix-smoke-20260922.json`: one world, seed 11,
three agents, one tick, one worker, low-effort Luna. Launch through
`python3 -m agent_world run --config CONFIG --dry-run`, then the same command
without `--dry-run`. An isolated official CLI installation can be selected by
putting its `node_modules/.bin` directory first in the launcher's PATH.

This is a new conversation treatment, not a transparent change to published
benchmarks. A fixed initialization exchange is additional model-visible
context. Future recipes can explicitly select it; existing recipes, historical
scores, and pinned runs retain their old conversation boundaries. Compare
realized token-derived cost including template creation and cache misses.
Equal cache-hit rates across providers are not guaranteed by equal prompts.

## Compatibility review

The implementation branches only on the new opt-in mode. Existing fresh and
persistent prompt construction and commands are unchanged. All published
recipe JSON, world mechanics, observations, and scoring are unchanged. The full
suite, including historical replay and prompt-hash fixtures, passed apart from
the expected execution-lock hash mismatch before regeneration. Execution locks
are regenerated for this additive capability after that review; no published
recipe selects it and no historical evidence is relabeled.

Official references:
[prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching),
[Codex 0.156 source](https://github.com/openai/codex/tree/rust-v0.156.0).
