# Versioned experiment recipes

Agent World is a laboratory. A recipe supplies a reproducible starting point;
benchmark intent adds certification requirements. Selecting an older recipe
does not require checking out older code.

| Recipe | Reasoning default | Informal-transfer accounting | Scoring revision |
| --- | --- | --- | --- |
| participant-v6 | medium | Frozen external classifier; agents do not declare transfer kind | 2 |
| participant-v7 | low | Agent-declared gift, payment, or barter | 1 |

Both recipes use the frontier world, ten generalists, fifty ticks, fresh
conversations, and connector-v3. Their score formulas are shared; revision
numbers are local to the protocol. Worker counts are operational settings.

## Select a benchmark

Use the managed interface with a config such as:

```json
{
  "schema_version": 1,
  "run_id": "my-v6-benchmark",
  "kind": "benchmark",
  "protocol": "participant-v6",
  "model": {"brain": "codex", "id": "YOUR_EXACT_MODEL_ID"}
}
```

```bash
agent-world run --config my-run.json --dry-run
agent-world run --config my-run.json
```

V6 defaults to medium; v7 defaults to low. Benchmark seeds default to 11 and
41. Conflicting settings fail validation because they would invalidate the
requested certification. Actual connector capabilities still apply: the
current ZCode connector accepts native Max, so it cannot satisfy either
standard reasoning policy.

## Borrow a recipe for an experiment

```json
{
  "schema_version": 1,
  "run_id": "glm-v6-small-world",
  "kind": "experiment",
  "question": "How does a small GLM society behave in a smaller frontier world?",
  "recipe": "participant-v6",
  "model": {"brain": "zcode", "id": "glm-5.3", "reasoning_effort": "max"},
  "runtime": {"agents": 3, "ticks": 7},
  "world": {"width": 12, "height": 12}
}
```

This uses v6 defaults wherever settings are omitted. Explicit settings win;
seeds default to 11 only. Any integer seed is allowed. Mixed populations,
other world settings, and connector-supported effort levels remain available.
This is an experiment and does not claim benchmark eligibility.

The low-level CLI equivalents are `--recipe participant-v6` for defaults and
`--benchmark-protocol participant-v6` for certification locks. Normal
model-backed launches still use the managed config interface. The independent
world setting `transfer_kind_mode` (`external` or `self_declared`) controls
the transfer affordance; the engine does not depend on benchmark version IDs.
Claude's thinking ceiling is also scoped to the run and saved on resume;
experiments can override it with `harness.claude_thinking_budget_tokens`.

## Provenance, resume, and reports

Manifests, lifecycle events, checkpoints, and benchmark reports retain the
selected recipe and its digest. Benchmark fingerprints include the selected
recipe plus relevant execution/scoring code. Adding another recipe does not
itself change an existing recipe's fingerprint. Shared behavioral code changes
still do.

A new v6 checkpoint can resume on the same code just as a v7 checkpoint can.
Changing recipe or its settings partway through a checkpoint is rejected.
Old checkpoints with different source fingerprints still require their own
launch commit. Selecting v6 today neither rewrites historical ledgers nor
certifies old runs under new code.

Aggregation infers a recipe when all supported input reports agree. A mixed
v6/v7 input requires explicit selection:

```bash
agent-world benchmark --protocol participant-v6 path/to/run-report.json
```

Reports for another recipe are rejected, not pooled. Existing explicitly
audited legacy migrations remain recorded exceptions; they do not grant
automatic equivalence between selectable recipes. Historical leaderboard
archives and the model-results catalog are unchanged by recipe selection.

## GLM branch integration

The reviewed branch `codex/glm53-zcode-v6` ended at `49fc33e`.
Its connector, credential bridge, quota guards, Grok improvements, and
OpenRouter transport/usage improvements were already represented on main,
including newer infrastructure fixes. This integration adds the missing
ZCode cache-read/cache-write aliases and labeled reasoning estimates, and
preserves its dated insights and original study manifests.

Reasoning estimates are restricted to the calibrated GLM-5.3 model family.
A positive provider count takes precedence. Records preserve the original
provider reasoning subtotal separately (including missing versus zero), the
estimate label, visible character count, and calibration identifier.
Completion totals are unchanged, so estimated reasoning is not billed twice.
These estimates are diagnostics, not provider-measured subtotals. Historical
cost reconstruction mentioned in the insights remains a separate evidence
correction; this integration does not reprice or relabel old runs.

The branch's global-v6 switch, ZCode-specific Max exemption, and fixed worker
requirements are superseded by explicit experiment recipes. Its two archived
study manifests and recovery script remain original historical snapshots,
including their launch/recovery status fields and source references. They are
not current managed-job status or launch instructions. Existing run worktrees
and ignored evidence are preserved.
