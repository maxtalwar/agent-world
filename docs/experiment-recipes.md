# Versioned experiment recipes

Agent World is a laboratory. A recipe supplies a reproducible starting point;
benchmark intent adds certification requirements. Selecting an older recipe
does not require checking out older code.

| Recipe | Reasoning default | Informal-transfer accounting | Scoring revision |
| --- | --- | --- | --- |
| participant-v6 | medium | Frozen external classifier; agents do not declare transfer kind | 2 |
| participant-v7 | low | Agent-declared gift, payment, or barter | 1 |
| participant-v8 | medium | Agent-declared gift, payment, or barter; diagnostic commerce | 1 |\n| participant-v8-action-review | medium | Same as v8; review recipe with per-action Execution | 1 |

All four recipes use the frontier world, ten generalists, fresh conversations,
and connector-v3. V6/v7 retain fifty ticks and their shared historical formulas.
V8 uses sixty ticks, no board, and outcome-production scoring. Revision numbers
are local to each protocol. Worker counts are operational settings.

## Add a benchmark without editing Python

Recipes are standalone JSON documents in `agent_world/recipes/ID.json`.
Every file in that directory is automatically registered and packaged with the
installed application. V6 and v7 use this same mechanism; neither has a special
launch or finalization path.

Start with [small-society.json](../configs/recipe-examples/small-society.json),
an unregistered example with three agents, six ticks, a 32×32 world, seeds
5 and 9, bounded observation history, and custom scoring targets:

```bash
agent-world recipes --validate configs/recipe-examples/small-society.json
cp configs/recipe-examples/small-society.json agent_world/recipes/small-society.json
agent-world recipes small-society
```

Edit its values and keep the filename equal to its `id`. For a different
name, rename both. `agent-world recipes` validates and lists every registered
recipe. Commit and push the definition before launching: the detached source
checkout must contain exactly the definition selected at planning time. An
explicit `source.commit` is checked for that same JSON definition before
launch; pre-JSON historical studies use their original checkout/interface.

Then choose `"protocol": "small-society"` in a managed benchmark config, or
`"recipe": "small-society"` in an experiment config. No Python registry edit
or version-specific launcher, scorer, or finalizer is needed. The example is
not registered by default and does not change either established benchmark.

### JSON data model

| Field | Meaning |
| --- | --- |
| `schema_version` | Recipe document format; currently 1. |
| `id` | Unique lowercase name with digits/hyphens; must equal the filename stem. |
| `defaults` | Frozen world, population, horizon, and harness settings. Experiments may override them. |
| `replications.required_seeds` | Nonempty, unique integer seeds required for certification. |
| `replications.extended_seeds` | Optional evidence, disjoint from required seeds. |
| `replications.provisional_seed` | A required seed that can stand alone provisionally. |
| `checkpoints` | Positive scoring checkpoints; the last must equal `defaults.ticks`. |
| `transfer_accounting` | `self_declared` or `frozen_classifier`; selects finalization behavior. |
| `scoring.policy` | Implemented scoring method; `participant` or `outcome-production`. |
| `scoring.revision` | Positive revision label within this recipe. |
| `scoring.parameters` | Policy-specific parameters: four legacy reference targets for participant, or integer capability_tail_ticks for outcome-production, plus optional execution_unit (decision or action). |

The supplied files spell out every required default. Additional
`WorldConfig` fields may be included in `defaults`, including reserve,
resource, memory, and seasonal settings; `seed` belongs in the replication
policy instead. The loader checks field names, primitive types, modes, actual
world construction, accounting consistency, and seed/checkpoint relationships.
The current handcrafted maps support 16×16 or 32×32 worlds; 32×32 requires
dispersed geography. JSON configures supported world mechanics rather than
creating new map generators.

Harness settings include connector/conversation modes, reasoning effort,
session length, action limits, observation-history policy, Claude's thinking
ceiling, and the startup health gate. Worker counts remain operational run
settings. Certification still requires a uniform model cohort, simultaneous
decisions, clean execution, and private I/O evidence under the implemented
participant scoring method.

The `participant` scoring method uses the existing formulas with the recipe's
four configured reference targets. Changing a target changes the calculation
and its reported formula. A genuinely new scoring algorithm or world mechanic
requires an implementation; unsupported policy names fail validation rather
than falling back to another algorithm.

### Immutable identity

There is no inheritance from a moving default recipe. A published recipe ID
should keep its behavior: use a new ID/file for a changed experiment design.
Whitespace and key ordering do not affect its digest. World settings, seeds,
checkpoints, transfer policy, and scoring parameters do. Editing another
recipe does not invalidate the selected recipe.

Reports, trajectories, finalization readiness, and catalog aggregation use the
selected definition. A catalog model result must pool one recipe; use separate
catalog entries for separate recipes. Legacy reports without recipe digests
retain their explicitly declared trial identity even when their old renderer
printed a different current-protocol header. New recipe-aware reports with
conflicting identities or digests are rejected.

The outcome-production policy implements independently scored capability,
execution, and productive value added. See [v8 production](v8-production.md).
Its tail must be a positive integer no longer than the recipe horizon.
The optional execution_unit defaults to decision, preserving published v8.
The action setting requires per-proposal outcome telemetry and scores each
submitted action or message independently. See [the action review](v8-action-review.md).
The review recipe is not a replacement for the published leaderboard, and its
Capability formula remains unchanged while that design is under discussion.

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
  "question": "How does a small GLM society behave in a larger frontier world?",
  "recipe": "participant-v6",
  "model": {"brain": "zcode", "id": "glm-5.3", "reasoning_effort": "max"},
  "runtime": {"agents": 3, "ticks": 7},
  "world": {"width": 32, "height": 32}
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
