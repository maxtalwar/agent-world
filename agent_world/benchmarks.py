"""Versioned, deterministic benchmarks for model behavior in Agent World."""

from __future__ import annotations

import ast
import hashlib
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from agent_world.metrics import (
    is_ambiguous_boundary_failure_message,
    is_confirmed_model_contract_failure_message,
    is_decision_failure_message,
    is_harness_failure_message,
    is_model_output_failure_message,
    is_provider_failure_message,
    is_quota_failure_message,
)
from agent_world.rules import ACCOUNTING_VALUES, recipes_for_mode


# Participant v7 keeps v6's frontier world and standardizes every provider on
# the named low reasoning setting. Medium was not portable across harnesses
# (some models do not expose it, and equal labels do not imply equal compute),
# while maximum reasoning would make the field needlessly slow and expensive.
# Provider-native allocation within low remains model behavior and is measured,
# not equalized. V6 stays frozen as the historical medium-effort suite.
from agent_world.protocols import DEFAULT_PROTOCOL_ID, RECIPES, get_recipe, scoring_columns

BENCHMARK_SUITE_ID = get_recipe().suite_id
BENCHMARK_PROTOCOL_ID = DEFAULT_PROTOCOL_ID
BENCHMARK_REASONING_EFFORT = get_recipe().reasoning_effort
# Operational throughput defaults. They are recorded for observability but are
# not part of the behavioral treatment: every agent decides from the same
# frozen tick state regardless of how many decisions are collected in parallel.
BENCHMARK_DEFAULT_MAX_WORKERS = 4
BENCHMARK_PROVIDER_MAX_WORKERS = {
    "openrouter": 4,
    "codex_cli": 40,
    "claude_cli": 20,
    "cursor_cli": 4,
    "devin_cli": 4,
    "grok_cli": 20,
    "zcode_cli": 20,
    "antigravity_cli": 4,
    "muse_cli": 4,
}
# Safety ceiling for Claude adaptive thinking per decision
# (MAX_THINKING_TOKENS). The shared protocol control is effort=low; this cap is
# only a guard against a pathological allocation and is never treated as a
# target spend. Provider-native spend within low is recorded for analysis.
BENCHMARK_CLAUDE_THINKING_BUDGET_TOKENS = 2048
# A rate-limited trial is early, not broken: the run waits for the cap to lift
# and retries the same tick, with the world frozen at a completed-tick
# boundary. Twelve hours covers the weekly and five-hour caps that actually
# interrupt runs. This is a wall-clock policy, not a simulation parameter - it
# cannot change any decision, action, or score.
BENCHMARK_QUOTA_WAIT_HOURS = 12.0
BENCHMARK_SEEDS = frozenset(get_recipe().required_seeds)
BENCHMARK_EXTENDED_SEEDS = frozenset(get_recipe().extended_seeds)
BENCHMARK_ALLOWED_SEEDS = BENCHMARK_SEEDS | BENCHMARK_EXTENDED_SEEDS
BENCHMARK_PROVISIONAL_SEED = get_recipe().provisional_seed
BENCHMARK_DIAGNOSTIC_TICKS = get_recipe().checkpoints
# V7 revision 1. One harness change over v6: agents self-classify transfers.
# The gift action takes kind = gift | payment | barter (default gift), the
# declaration is recorded in the event, and scoring TRUSTS it - payment is
# service income credited to the recipient, barter is a directional goods
# flow, and gift is an unrequited transfer, reported but never scored.
# Organic v7 worlds also include escrowed delivery contracts and the public town ledger.
# Strict liability: misfiling a payment as a gift forfeits the credit, which
# is a scored planning mistake, not a harness problem. V6 closed at its
# scoring revision 2, where a frozen judge artifact
# (gift-classifications.json) classified historical gifts from ledger
# evidence; when such an artifact is present it still takes precedence over
# declarations, so rescored v6 ledgers keep their audited verdicts.
BENCHMARK_SCORING_REVISION = get_recipe().scoring_revision

GIFT_VERDICT_PAYMENT = "payment_for_service"
GIFT_VERDICT_BARTER = "barter_settlement"
GIFT_VERDICT_UNREQUITED = "unrequited_transfer"
GIFT_VERDICT_UNCLASSIFIABLE = "unclassifiable"
GIFT_VERDICTS = frozenset(
    {
        GIFT_VERDICT_PAYMENT,
        GIFT_VERDICT_BARTER,
        GIFT_VERDICT_UNREQUITED,
        GIFT_VERDICT_UNCLASSIFIABLE,
    }
)
# Launch-time fingerprints whose raw-ledger re-derivations stay compliant.
# Each entry is a hand-audited statement that the code change separating that
# fingerprint from the current one cannot alter agent-visible behavior or any
# scored number.
#
# b524845f... is the codex-scoped v6 fingerprint at commit 7bbff8d, under which
# the first four v6 trials ran (sol seed 11; mini seeds 11+41; spark seed 11)
# and the spark seed-41 checkpoint was written. The only benchmark-file change
# since is the cli.py checkpoint-resume guard fix: the guard previously
# compared a checkpoint's provider-scoped fingerprint against the UNSCOPED
# hash, so every benchmark resume was wrongly rejected. The fix replaces that
# comparison (extracted into _check_resume_fingerprint) and is only reachable
# from the resume branch of _run; no agent-facing code, no scoring code, and
# no launch path changed.
#
# 7dff4cec... is the claude-scoped v6 fingerprint at commit a86d06f, under
# which the Fable 5 checkpoints were written. The compatibility branch keeps
# that protocol and world byte-for-byte and changes only provider-failure
# handling: a quota refusal now freezes the completed-tick boundary instead of
# fabricating wait actions. This entry permits the recovered tick-32 checkpoint
# to resume without changing any successful decision or world transition.
#
# The seven fingerprints beginning 2a84dcfb through a79bd51c are the unscoped
# and provider-scoped v7 fingerprints at commit 427010a, immediately before the
# terminology-only boundary migration. That migration renamed connector
# profiles and conversation modes, canonicalizes their historical aliases, and
# does not change prompts, observations, provider arguments, world transitions,
# or scoring. Retaining them keeps existing v7 reports and checkpoints valid.
#
# The first two entries are v6 fingerprints and do not promote anything into
# v7. A
# resume is refused outright when the checkpoint's protocol is not the current
# one (see _check_resume_fingerprint), so a v6 checkpoint cannot be finished
# under the v7 world, and _trial_flags only consults this set for trials that
# already declare the current protocol. Resume those checkpoints from a
# worktree pinned to their own v6 launch commit, which is where these entries
# do their work.
#
# The eight fingerprints beginning 4614df04 through 6481fec9 are the unscoped
# and provider-scoped v7 fingerprints at commit a2bc95b, immediately before
# worker concurrency was correctly reclassified as operational metadata. The
# change preserves simultaneous world resolution and every prompt, action, and
# score; it only stops launch validation and report admission from treating the
# number of parallel decision subprocesses as a behavioral setting.
BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS: frozenset[str] = frozenset(
    {
        "b524845fcd574c17abc82bcaaefaca36cc326e31fb399641f9e05014389a7ec4",
        "7dff4cecc0b56951c1a5bf504a1dfc5f0446ef8d6e7cefc6dbddcebdbe2addb6",
        "2a84dcfba2c57b46a4732bcdaa7c378ab6a5b71b1e0104597d618e5a294e55a0",
        "5084bd7dd939e279b0cffe1100a9f21e316f5e8652c71fa99c2d8408a4b2380c",
        "bf0bc346f5a4b1cc61ba84935b5b6998581e8c0055e45fb2cf37cd65d73f21b4",
        "0dc4ca55a5cc8a0473d226c73da8c886e08814869f7a145b668cbde64e9ba42b",
        "9e43a228691bebe86c8863e7b5d64c6307d84afff690e0950b2c9dcbd699872d",
        "3d59a78e55fa86466815dbaa03d4f7abe00c3c1f9a12bf4dc1395bbc7241b22d",
        "a79bd51cd3e2e0acc34ad4ac9006b74fae4987e40ed2dfc9a3f97cf7714d4788",
        "4614df041e86a0ba105f4d7b9fe2260f022de8b7dd853d3ece4d66c8ce5f852d",
        "addb8123c677b9735496fafe7855c1237344f5bc919f287167399ac2af56ec7b",
        "9f2da58f4f6efd3a0dcd1afc98d92f948569ca1ad2f96fd9d64dc2461751a95f",
        "136aad06576fd430964ba62157ef9dd55ac67f23e45793887d42c012a5ffd2aa",
        "655fc30e9e0c01379ff48ebcc144392c3d76d8e870459498bad609e3c22cd673",
        "eedbb068ccf091b58a683f9bb03bdbdb13aa020fba1ab78995b8ebc110dc5379",
        "c21751e71eda1b73dc19a20608fb1f514960958b11ee593660026058f0effd28",
        "6481fec990a8a063ccc8d898370e91101a7c0d38d66e8045f9a65e5907a8556c",
    }
)

# Same-suite reports whose stored fingerprint predates a code change that
# cannot change their numbers. Membership is the audit: an entry is only added
# after checking the intervening diff against the scoring path. Same entry and
# rationale as BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS above.
BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS: frozenset[str] = frozenset()

# Scored reports from an EARLIER SUITE accepted as current-suite evidence
# after an audit showing the suite change cannot touch their numbers. Keyed by
# (suite_id, stored report fingerprint) with a provider restriction. EMPTY for
# v6 by construction: v6 changed the world itself (frontier variant), so every
# prior trial - codex and claude alike - ran a different simulation and nothing
# can carry over. The v5 registry entries that carried the v4 codex pairs are
# preserved in git history, and the v4/v5 leaderboards remain historical
# artifacts.
BENCHMARK_ACCEPTED_PRIOR_SUITE_REPORTS: dict[tuple[str, str], dict[str, Any]] = {}

# Trials run under an earlier protocol that are accepted as v4 evidence after
# an audited review of every behavioral difference. This is deliberately a
# named allowlist rather than a rule: each entry records the exact deviation
# so it appears in every artifact rather than being silently absorbed. An
# entry is only justified when the surviving differences have been checked
# against the actual ledgers and shown not to bind.
BENCHMARK_ACCEPTED_PRIOR_TRIALS: dict[str, dict[str, str]] = {
    "3b4d69526653673e094ff4e08ca72929f3d13d7b5ba269993f58649572beaede": {
        "protocol": "participant-v3",
        "deviation": (
            "static_context_mechanics_text: ore was described as a "
            "'high-value raw material' rather than as smeltable into an "
            "ingot. One line of a 6,430-character static context."
        ),
        "audited": (
            "The other two differences introduced with v4 were checked "
            "against these ledgers and do not bind. No structure in any run "
            "had more than one contributor, so the construction "
            "contributor-share change is inert. Engine-declared trade values "
            "never reached agents: market history was already filtered to "
            "give/receive bundles and event rendering never exposed event "
            "data. Trial settings, horizon, integrity, and usage coverage "
            "all match v4 exactly."
        ),
    },
    "a79d5045623351a9d29b7ff90e0b7fc5630db139e659e7b86edc42a1f0625948": {
        "protocol": "participant-v3",
        "deviation": (
            "static_context_mechanics_text: ore was described as a "
            "'high-value raw material' rather than as smeltable into an "
            "ingot. Same one-line static-context difference accepted for the "
            "GPT-5.4 pair. See also the attribution override recorded in "
            "BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES for this trial."
        ),
        "audited": (
            "Every difference from commit 60c4143 to v4 was examined. The "
            "run built zero structures, so the contributor-share change never "
            "fired. Engine trade values never reached agents, verified at "
            "60c4143 itself. The ACCOUNTING_VALUES rename changed no value. "
            "The models.py and cli.py edits are a comment and seed-validation "
            "text. The decision-contract validator does not alter the prompt, "
            "so the model faced the same world; it alters failure attribution "
            "only, which is covered by the separate attribution override."
        ),
    },
}

# Cohorts whose model-output attribution cannot be independently reverified,
# accepted anyway by explicit owner decision. This is the one place the suite
# trades a bright-line integrity check for a judgment call, so the bar is
# deliberately awkward: every field must match exactly, including the failure
# count. A rescore that yields a different count stops matching and the flag
# returns, which is the point - the entry cannot quietly widen to cover
# failures nobody looked at.
#
# What is being accepted, stated plainly: if these failures were adapter
# rejections of contract-valid output rather than malformed model output, the
# harness misbehaved during the trial and the run should have been void. That
# possibility is not excluded by evidence - it is judged immaterial given the
# measured sensitivity. Every artifact carries this text.
BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES: tuple[dict[str, Any], ...] = (
    {
        "model": "gpt-5.3-codex-spark",
        "seed": 11,
        "source_fingerprint": (
            "a79d5045623351a9d29b7ff90e0b7fc5630db139e659e7b86edc42a1f0625948"
        ),
        "unverified_model_output_failures": 2,
        "deviation": (
            "unverified_model_output_attribution: two decision failures at "
            "ticks 7 and 28 record only the production adapter's parse error. "
            "The trial predates the independent contract validator and no "
            "response payload was retained, so malformed model output cannot "
            "be distinguished from adapter rejection of valid output."
        ),
        "sensitivity": (
            "Scoring both failures against the model gives effective "
            "execution 71.46; excluding them entirely gives 71.54. The "
            "disputed span is 0.08 points over 1,331 submitted actions."
        ),
        "accepted_because": (
            "Owner decision, 2026-07-26: Spark inference is usage "
            "constrained, and a 0.08-point gap does not justify spending a "
            "full 50-tick trial to resolve it."
        ),
    },
)

# These are mechanics-anchored "excellent" targets, not population percentiles.
# Versioning the suite freezes them so later runs remain directly comparable.
# Participant v4 anchors are intentionally close to demonstrated strong-model
# behavior instead of preserving v3's unreachable scale. Five initiatives per
# 100 agent-ticks is just above the 4.25 rate in the clean GPT-5.4 v2 reference.
INITIATIVE_TARGET_PER_100_AGENT_TICKS = 5.0
NET_VALUE_CREATION_TARGET_PER_100_AGENT_TICKS = 20.0
# Enterprise supply on the preserved clean ledgers is 0.6 per 100 agent-ticks
# for the collapsing Spark cohort and 9.4-10.8 for GPT-5.4. Those GPT-5.4
# figures are almost entirely own-capital output with roughly 5 units of
# actual commerce, so anchoring at the demonstrated rate would call a
# near-tradeless economy excellent. Anchoring at 20 places the best observed
# cohort mid-scale and leaves headroom for one that both builds capital and
# supplies customers. The scale is uncapped, so there is no ceiling risk.
ENTERPRISE_SUPPLY_TARGET_PER_100_AGENT_TICKS = 20.0
TERMINAL_ENDOWMENT_MULTIPLE_TARGET = 3.0

_VALUE_EPSILON = 1e-9

VENTURE_INITIATIVE_EVENTS = frozenset(
    {"offer_trade", "build_started", "create_contract", "set_access_fee"}
)
# Coin is the cohort's medium of exchange, not a produced good. Paying for
# goods must not read as supplying them, so coin flows are excluded from
# enterprise supply. Coin still counts as wealth in terminal value.
ENTERPRISE_SUPPLY_EXCLUDED_GOODS = frozenset({"coin"})
PURPOSEFUL_ACTION_EVENTS = frozenset(
    {
        "move",
        "gather",
        "chop",
        "mine",
        "harvest",
        "fish",
        "farm",
        "craft",
        "repair",
        "pick_up",
        "claimed_item_taken",
        "drop",
        "claim_item",
        "consume",
        "equip",
        "store",
        "retrieve",
        "offer_trade",
        "accept_trade",
        "create_contract",
        "accept_contract",
        "repay_contract",
        "fulfill_contract",
        "gift",
        "claim_tile",
        "contest_claim",
        "build",
        "build_started",
        "contribute",
        "claim_dividend",
        "maintain_structure",
    }
)
# Purposeful activity must cost something or move something. These actions are
# zero-action-point bookkeeping with no material consequence, so counting them
# would replace v3's all-`wait` exploit with an equally free all-`publish_rule`
# one. Zero-cost actions that do move goods (accept_trade, repay_contract,
# claim_dividend) stay in the set above.
NON_MATERIAL_FREE_ACTION_EVENTS = frozenset(
    {
        "grant_access",
        "revoke_access",
        "create_group",
        "invite_member",
        "join_group",
        "leave_group",
        "publish_rule",
        "record_agreement",
        "reject_trade",
        "set_access_fee",
    }
)
# Sources every trial depends on regardless of which provider ran it: the world
# and its rules, the agent-facing interface, the tick loop, the decision
# plumbing, and the scoring itself.
BENCHMARK_CORE_FINGERPRINT_FILES = (
    "action_contract.py",
    "decision_deadline.py",
    "decision_contract.py",
    "managed_observer.py",
    "observation_policy.py",
    "request_context.py",
    "tool_boundary.py",
    "brain_factory.py",
    "host_profile.py",
    "decision_outcome.py",
    "event_index.py",
    "io.py",
    "jsonl_tail.py",
    "persistence.py",
    "process_transport.py",
    "provider_limits.py",
    "provider_telemetry.py",
    "usage.py",
    "benchmarks.py",
    "protocols.py",
    "brain_boundary.py",
    "brain_runtime.py",
    "cli.py",
    "decision_failure.py",
    "interface.py",
    "maps.py",
    "models.py",
    "rules.py",
    "run_report.py",
    "runner.py",
    "session.py",
    "world.py",
)

# Provider adapters are scoped to the run that actually invoked them. A Codex
# trial cannot be changed by editing - or renaming - the Claude or OpenRouter
# adapter, because that code never executes in it. Hashing every adapter into
# every fingerprint made unrelated provider work invalidate finished, unrelated
# trials, which is a false alarm rather than a safeguard. Anything an adapter
# shares with others lives in the core list above, so a change with real reach
# still moves every fingerprint.
BENCHMARK_PROVIDER_FINGERPRINT_FILES: dict[str, tuple[str, ...]] = {
    "claude_cli": ("claude_brain.py",),
    "codex_cli": ("codex_brain.py",),
    "cursor_cli": ("cursor_brain.py",),
    "devin_cli": ("devin_brain.py",),
    "grok_cli": ("grok_brain.py",),
    "zcode_cli": ("zcode_brain.py",),
    "antigravity_cli": ("antigravity_brain.py", "headless_brain.py"),
    "muse_cli": ("muse_brain.py", "headless_brain.py"),
    "openrouter": ("openrouter_brain.py",),
    "openai_compatible": ("openrouter_brain.py",),
}

BENCHMARK_FINGERPRINT_FILES = tuple(
    sorted(
        set(BENCHMARK_CORE_FINGERPRINT_FILES)
        | {name for names in BENCHMARK_PROVIDER_FINGERPRINT_FILES.values() for name in names}
    )
)


def _recipe_consistent_accounting_values(economy_mode: str) -> dict[str, float]:
    """Raise book values until every single-output recipe preserves input value.

    The output unit value is the exact input total divided by the output
    quantity. Rounding the unit value up instead would multiply the rounding
    error by the output quantity, so a multi-output recipe such as minting
    eight coins from one ingot would manufacture accounting value on every
    cycle. Units are analysis quantities, never prices shown to agents, so
    they are free to be fractional.
    """

    values = {str(item): float(value) for item, value in ACCOUNTING_VALUES.items()}
    recipes = recipes_for_mode(economy_mode)
    for _ in range(max(1, len(recipes) + 1)):
        changed = False
        for recipe in recipes.values():
            outputs = {
                str(item): max(0, int(quantity or 0))
                for item, quantity in recipe.outputs.items()
                if int(quantity or 0) > 0
            }
            if len(outputs) != 1:
                continue
            output_item, output_quantity = next(iter(outputs.items()))
            input_value = sum(
                values.get(str(item), 1.0) * max(0, int(quantity or 0))
                for item, quantity in recipe.inputs.items()
            )
            minimum_unit_value = input_value / output_quantity
            if minimum_unit_value > values.get(output_item, 1.0) + _VALUE_EPSILON:
                values[output_item] = minimum_unit_value
                changed = True
        if not changed:
            break
    return values


BENCHMARK_ACCOUNTING_VALUES = _recipe_consistent_accounting_values("organic")


def accepted_prior_trial(
    declared_protocol: Any,
    source_fingerprint: Any,
) -> dict[str, str] | None:
    """Return the audited deviation record for an accepted earlier trial.

    Returns None unless this exact fingerprint was explicitly allowlisted and
    its declared protocol matches the one recorded for it, so a fingerprint
    can never be promoted under a protocol it was not audited against.
    """

    entry = BENCHMARK_ACCEPTED_PRIOR_TRIALS.get(str(source_fingerprint))
    if entry is None or entry["protocol"] != str(declared_protocol):
        return None
    return entry


def accepted_attribution_override(
    *,
    model: Any,
    seed: Any,
    source_fingerprint: Any,
    unverified_failures: int,
) -> dict[str, Any] | None:
    """Return an explicit override for unverifiable model-output attribution.

    Every field must match exactly, the failure count included. A cohort that
    develops a third unattributable failure stops matching and is flagged
    again, so an override can never silently widen past what was audited.
    """

    for entry in BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES:
        if (
            str(entry["model"]) == str(model)
            and _as_int(seed) == entry["seed"]
            and str(entry["source_fingerprint"]) == str(source_fingerprint)
            and entry["unverified_model_output_failures"] == unverified_failures
        ):
            return entry
    return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=64)
def _behavior_source_cached(path_text: str, mtime_ns: int, size: int) -> bytes:
    return _behavior_source_uncached(Path(path_text))


def _behavior_source(path: Path) -> bytes:
    """Cache by path identity and mtime so repeated scoring does not reparse."""

    stat = path.stat()
    return _behavior_source_cached(str(path), stat.st_mtime_ns, stat.st_size)


# Historical acceptance registries are excluded from the behavior hash. They
# record which OLD reports remain valid; they cannot change any new trial's
# behavior or any report's numbers. Hashing them created a treadmill: accepting
# one old report edited this file, which moved every current fingerprint, which
# orphaned every report recorded since - each acceptance manufacturing the next
# round of false mismatches.
FINGERPRINT_EXEMPT_REGISTRIES = frozenset(
    {
        "BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS",
        "BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS",
        "BENCHMARK_ACCEPTED_PRIOR_SUITE_REPORTS",
        "BENCHMARK_ACCEPTED_PRIOR_TRIALS",
        "BENCHMARK_ACCEPTED_ATTRIBUTION_OVERRIDES",
    }
)


def _registry_assignment_name(node: ast.stmt) -> str | None:
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _behavior_source_uncached(path: Path) -> bytes:
    """Return a source form that ignores text which cannot change behavior.

    Comments and docstrings are stripped and formatting is normalized by parsing
    to a syntax tree. Module-level assignments to the historical acceptance
    registries are dropped for the reason on FINGERPRINT_EXEMPT_REGISTRIES.
    Every other executable construct survives - names, constants, control flow,
    and the prompt and rule strings agents actually receive - so a real change
    still moves the fingerprint. Falls back to raw bytes if a file cannot be
    parsed, which fails closed.
    """

    raw = path.read_bytes()
    try:
        tree = ast.parse(raw)
    except SyntaxError:
        return raw
    # Recipe data is hashed through the selected recipe's canonical digest.
    # Adding an unrelated recipe must not invalidate an existing one.
    ignored = FINGERPRINT_EXEMPT_REGISTRIES
    if path.name == "protocols.py":
        ignored = ignored | {"RECIPES", "DEFAULT_PROTOCOL_ID"}
    tree.body = [
        node
        for node in tree.body
        if _registry_assignment_name(node) not in ignored
    ]
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree).encode("utf-8")


def benchmark_code_fingerprint(providers: Iterable[str] | None = None, protocol_id: str | None = None) -> str:
    """Hash benchmark formulas, world sources, and the adapters a trial used.

    ``providers`` scopes which adapters are included. Passing ``None`` covers
    every adapter, which is the right default when declaring the protocol or
    launching a run before its population is resolved. Scoring a finished report
    passes that report's providers so unrelated adapters cannot invalidate it.
    """

    package_dir = Path(__file__).resolve().parent
    if providers is None:
        names = BENCHMARK_FINGERPRINT_FILES
    else:
        scoped: set[str] = set()
        for provider in providers:
            scoped.update(BENCHMARK_PROVIDER_FINGERPRINT_FILES.get(provider, ()))
        names = tuple(sorted(set(BENCHMARK_CORE_FINGERPRINT_FILES) | scoped))
    if get_recipe(protocol_id).scoring_policy == "outcome-production":
        names = tuple(sorted(set(names) | {"outcome_scoring.py", "production_scoring.py"}))
    digest = hashlib.sha256(get_recipe(protocol_id).digest.encode())
    for name in names:
        digest.update(name.encode("utf-8"))
        digest.update(_behavior_source(package_dir / name))
    return digest.hexdigest()


def benchmark_protocol(protocol_id: str | None = None) -> dict[str, Any]:
    """Return a selected frozen participant recipe and scoring specification."""

    recipe = get_recipe(protocol_id)

    protocol = {
        "id": recipe.id,
        "scoring_revision": recipe.scoring_revision,
        "recipe_fingerprint_sha256": recipe.digest,
        "transfer_accounting": recipe.transfer_accounting,
        "scoring_policy": recipe.scoring_policy,
        "scoring_parameters": recipe.scoring_parameters(),
        "suite_id": recipe.suite_id,
        "code_fingerprint_sha256": benchmark_code_fingerprint(protocol_id=recipe.id),
        "replications": {
            "required_seeds": list(recipe.required_seeds),
            "minimum": len(recipe.required_seeds),
            "provisional_seed": recipe.provisional_seed,
            "provisional_minimum": 1,
            "optional_extended_seeds": list(recipe.extended_seeds),
            "policy": (
                f"Seed {recipe.provisional_seed} can stand as provisional evidence. "
                f"Required seeds {list(recipe.required_seeds)} certify a replicated benchmark; "
                f"extended seeds {list(recipe.extended_seeds)} are optional."
            ),
        },
        "execution_defaults": {
            "global_max_workers": BENCHMARK_DEFAULT_MAX_WORKERS,
            "provider_max_workers": dict(
                sorted(BENCHMARK_PROVIDER_MAX_WORKERS.items())
            ),
            "worker_count_is_protocol_setting": False,
            "policy": (
                "Worker counts only control how quickly independent decisions "
                "from one frozen tick are collected. Runs record the actual "
                "counts, but differing counts do not affect protocol compliance."
            ),
        },
        "trial": {
            **recipe.defaults(),
            "diagnostic_score_ticks": list(recipe.checkpoints),
            "official_score_tick": recipe.defaults()["ticks"],
            "season_length_ticks": recipe.defaults().get("season_length_ticks", 12),
            "deliberation_policy": (
                f"Request the named {recipe.reasoning_effort} reasoning setting from every connector; "
                "provider-native spend is measured and reported, "
                "never equalized. Connectors must not silently promote an "
                "unsupported request to another effort."
            ),
            "population": "one uniform model cohort",
            "turn_resolution": "simultaneous",
            "agent_io_log": True,
            "model_output_failure_policy": (
                "Independently validate each extracted decision against the "
                "declared contract. Count confirmed output-contract violations "
                "as invalid proposals; invalidate adapter, ambiguous-boundary, "
                "provider, quota, and harness failures."
            ),
        },
        "score_scale": {
            "minimum": 0.0,
            "maximum": None,
            "higher_is_better": True,
            "metric_specific": True,
            "details": "See score_scales for per-benchmark bounds.",
        },
        "score_scales": {
            "effective_execution": {
                "minimum": 0.0,
                "maximum": 100.0,
                "higher_is_better": True,
            },
            "sustained_competence": {
                "minimum": 0.0,
                "maximum": 100.0,
                "higher_is_better": True,
            },
            "entrepreneurial_agency": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
            },
            "economic_productivity": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
                "diagnostic": True,
            },
        },
        "targets": {
            "terminal_endowment_multiple": recipe.scoring_parameters().get("material_endowment_multiple"),
            "enterprise_supply_per_100_agent_ticks": recipe.scoring_parameters().get("enterprise_supply_per_100_agent_ticks"),
            "net_value_created_per_100_agent_ticks": recipe.scoring_parameters().get("value_creation_per_100_agent_ticks"),
            "venture_initiatives_per_100_agent_ticks": recipe.scoring_parameters().get("initiative_per_100_agent_ticks"),
        },
        "accounting_values": {
            "method": (
                "Start from the world book-value table and raise each "
                "single-output recipe's output to exactly its input total "
                "divided by the output quantity. Values are fractional so no "
                "recipe can manufacture accounting value through rounding."
            ),
            "values": {
                item: round(value, 6)
                for item, value in sorted(BENCHMARK_ACCOUNTING_VALUES.items())
            },
        },
        "aggregation": (
            "For a provisional result, apply the frozen formulas to the clean "
            f"seed-{recipe.provisional_seed} raw counts. For replicated certification, pool raw numerators "
            f"and denominators across required seeds {list(recipe.required_seeds)} before scoring. "
            "Optional extended seeds are reported separately and do not change the "
            "official certified score. Report individual seed scores plus their "
            "range and absolute difference; do not claim a confidence interval. "
            f"Checkpoints {list(recipe.checkpoints[:-1])} are diagnostic; "
            f"tick {recipe.defaults()['ticks']} is official."
        ),
    }

    if recipe.scoring_policy == "outcome-production":
        protocol["score_scales"] = {
            key: {"minimum": 0.0, "maximum": None if key == "production" else 100.0,
                  "higher_is_better": True}
            for key, _ in scoring_columns(recipe.scoring_policy)
        }
        protocol["targets"] = recipe.scoring_parameters()
        protocol["score_columns"] = list(scoring_columns(recipe.scoring_policy))
        protocol["production_accounting"] = (
            "Gross value added at fixed accounting values per 100 original-population "
            "agent-ticks. Count extracted goods and net craft output; no trade, gift, "
            "unused construction, survival-consumption deduction, or terminal-wealth gate."
        )
    return protocol


def build_benchmark_results(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    """Score every model cohort in a run and audit protocol compliance."""

    population = report.get("population") or {}
    cohorts = population.get("cohorts") or {}
    run = report.get("run") or {}
    config = report.get("config") or {}
    started = _latest_lifecycle_event(events)
    start_data = (started or {}).get("data") or {}
    declared_recipe = start_data.get("benchmark_protocol") or start_data.get("recipe")
    if declared_recipe and start_data.get("recipe_fingerprint_sha256"):
        get_recipe(declared_recipe)  # Never relabel a missing JSON recipe as the default.
    recipe = get_recipe(declared_recipe if declared_recipe in RECIPES else None)
    trial_flags = _trial_flags(report, start_data, cohorts, recipe.id)
    trial_protocol = start_data.get("benchmark_protocol")
    classification = report.get("gift_classifications") or {}
    gift_verdicts = {
        int(entry.get("gift_index")): str(entry.get("verdict") or "")
        for entry in classification.get("classifications") or []
        if str(entry.get("verdict") or "") in GIFT_VERDICTS
    }
    total_gifts = sum(1 for event in events if event.get("type") == "gift")
    if total_gifts and not gift_verdicts:
        # Not a compliance failure: unclassified gifts are simply unscored.
        # The flagless default keeps ledgers without commerce unaffected.
        pass

    scored: dict[str, Any] = {}
    for cohort_id, cohort in cohorts.items():
        member_ids = [str(value) for value in cohort.get("agents") or []]
        member_set = set(member_ids)
        raw = _cohort_raw_metrics(
            events=events,
            snapshot=snapshot,
            config=config,
            member_ids=member_ids,
            final_tick=int(run.get("final_tick") or 0),
            target_ticks=int(run.get("target_ticks") or 0),
            gift_verdicts=gift_verdicts,
            transfer_accounting=recipe.transfer_accounting,
        )
        cohort_flags = list(trial_flags)
        if recipe.scoring_policy == "outcome-production":
            from agent_world.outcome_scoring import derive_outcome_counts, ScoringEvidenceError
            from agent_world.production_scoring import derive_production_counts
            try:
                horizon = int(run.get("final_tick") or 0)
                raw.update(derive_outcome_counts(
                    events, snapshot, member_ids=member_ids, target_ticks=horizon,
                    tail_ticks=min(recipe.scoring_parameters()["capability_tail_ticks"], horizon),
                    require_completed=bool(run.get("completed")),
                    execution_unit=recipe.scoring_parameters().get("execution_unit", "decision"),
                ))
                raw.update(derive_production_counts(
                    events, member_ids=member_ids, target_ticks=horizon,
                    economy_mode=config.get("economy_mode", "organic"),
                    accounting_values=BENCHMARK_ACCOUNTING_VALUES,
                ))
            except (ScoringEvidenceError, ValueError) as exc:
                cohort_flags.append("scoring_evidence_unavailable")
                raw["scoring_evidence_error"] = str(exc)
        if recipe.scoring_policy == "participant" and raw["submitted_actions_excluding_contention"] <= 0:
            cohort_flags.append("insufficient_action_sample")
        if raw["possible_agent_ticks"] <= 0:
            cohort_flags.append("insufficient_agent_tick_sample")
        confirmed_contract_failures = sum(
            is_confirmed_model_contract_failure_message(
                event.get("type"),
                event.get("message"),
            )
            for event in events
            if event.get("actor_id") in member_set
        )
        unverified_failures = (
            raw["model_output_failures"] - confirmed_contract_failures
        )
        attribution_override = None
        if unverified_failures > 0:
            attribution_override = accepted_attribution_override(
                model=cohort.get("model"),
                seed=config.get("seed"),
                source_fingerprint=start_data.get("benchmark_code_fingerprint"),
                unverified_failures=unverified_failures,
            )
            if attribution_override is None:
                cohort_flags.append("unverified_model_output_attribution")
        scores = score_benchmark_counts(raw, recipe.id)
        scored[str(cohort_id)] = {
            "attribution_override": attribution_override,
            "brain": cohort.get("brain"),
            "model": cohort.get("model"),
            "reasoning_effort": cohort.get("reasoning_effort"),
            "provider": cohort.get("provider"),
            "agents": member_ids,
            "protocol_compliant": not cohort_flags,
            "quality_flags": sorted(set(cohort_flags)),
            "raw": raw,
            "scores": scores,
            "diagnostics": _cohort_diagnostics(events, set(member_ids), raw),
        }

    # Record the fingerprint scoped to the adapters these cohorts ran on, so the
    # report is compared against the code that could actually have affected it.
    report_providers = {
        str(cohort.get("provider"))
        for cohort in cohorts.values()
        if cohort.get("provider")
    }
    protocol = benchmark_protocol(recipe.id)
    protocol["code_fingerprint_sha256"] = benchmark_code_fingerprint(
        report_providers or None, recipe.id
    )

    return {
        "suite_id": recipe.suite_id,
        "protocol": protocol,
        "trial": {
            "declared_protocol": trial_protocol,
            "code_fingerprint_sha256": start_data.get(
                "benchmark_code_fingerprint"
            ),
            "source_fingerprint_compatible": (
                recipe.id == DEFAULT_PROTOCOL_ID
                and start_data.get("benchmark_code_fingerprint")
                in BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS
            ),
            "protocol_compliant": not trial_flags,
            "quality_flags": sorted(set(trial_flags)),
            "accepted_prior_trial": accepted_prior_trial(
                trial_protocol,
                start_data.get("benchmark_code_fingerprint"),
            ),
            "seed": config.get("seed"),
            "completed": bool(run.get("completed")),
            "final_tick": run.get("final_tick"),
            "target_ticks": run.get("target_ticks"),
            "gift_classification": {
                "total_gifts": total_gifts,
                "classified_gifts": len(gift_verdicts),
                "artifact_sha256": classification.get("artifact_sha256"),
                "judge": classification.get("judge"),
                "policy": (
                    "Frozen artifact judged from ledger evidence; unclassified gifts are unscored."
                    if recipe.transfer_accounting == "frozen_classifier"
                    else "Transfers use the sender-declared gift, payment, or barter kind."
                ),
            },
            "certification": (
                "eligible_replication"
                if not trial_flags
                else "diagnostic_only"
            ),
        },
        "cohorts": scored,
        "trajectory": _benchmark_trajectory(events, recipe.id),
    }


def score_benchmark_counts(raw: dict[str, Any], protocol_id: str | None = None) -> dict[str, Any]:
    """Apply the frozen participant-v4 formulas to pooled or per-run counts."""

    recipe = get_recipe(protocol_id)
    if recipe.scoring_policy == "outcome-production":
        from agent_world.outcome_scoring import ScoringEvidenceError
        from agent_world.production_scoring import score_outcome_production_counts
        try:
            if raw.get("scoring_evidence_error"):
                raise ScoringEvidenceError(raw["scoring_evidence_error"])
            return score_outcome_production_counts(
                raw,
                execution_unit=recipe.scoring_parameters().get("execution_unit", "decision"),
                capability_aggregation=recipe.scoring_parameters().get("capability_aggregation", "full_tail_geometric"),
            )
        except ScoringEvidenceError as exc:
            return {key: {"score": None, "unavailable_reason": str(exc)}
                    for key, _ in scoring_columns(recipe.scoring_policy)}
    parameters = recipe.scoring_parameters()
    feasibility_denominator = float(
        raw.get("submitted_actions_excluding_contention") or 0
    )
    invalid = float(raw.get("invalid_proposals") or 0)
    action_feasibility = (
        _clamp_score(
            100.0
            * (feasibility_denominator - invalid)
            / feasibility_denominator
        )
        if feasibility_denominator > 0
        else None
    )
    decisions = float(raw.get("decisions") or 0)
    purposeful_agent_ticks = float(raw.get("purposeful_agent_ticks") or 0)
    purposeful_agent_tick_pct = (
        _clamp_score(100.0 * purposeful_agent_ticks / decisions)
        if decisions > 0
        else None
    )
    effective_execution = _geometric_mean(
        (action_feasibility, purposeful_agent_tick_pct)
    )

    possible_ticks = float(raw.get("possible_agent_ticks") or 0)
    survival_exposure = (
        _clamp_score(100.0 * decisions / possible_ticks)
        if possible_ticks > 0
        else None
    )
    endpoint_health_capacity = float(raw.get("endpoint_health_capacity") or 0)
    endpoint_population_health = (
        _clamp_score(
            100.0
            * float(raw.get("endpoint_health_points") or 0)
            / endpoint_health_capacity
        )
        if endpoint_health_capacity > 0
        else None
    )
    survival_continuity = _geometric_mean(
        (survival_exposure, endpoint_population_health)
    )
    initial_endowment = float(raw.get("initial_endowment_value") or 0)
    living_terminal_value = float(
        raw.get("living_terminal_economic_value") or 0
    )
    material_target = initial_endowment * parameters["material_endowment_multiple"]
    material = (
        _clamp_score(100.0 * living_terminal_value / material_target)
        if material_target > 0
        else None
    )
    competence = _geometric_mean(
        (effective_execution, survival_continuity, material)
    )

    initiative_rate = (
        100.0 * float(raw.get("venture_initiatives") or 0) / possible_ticks
        if possible_ticks > 0
        else None
    )
    net_value_created = max(
        0.0,
        living_terminal_value - initial_endowment,
    )
    net_value_creation_rate = (
        100.0 * net_value_created / possible_ticks
        if possible_ticks > 0
        else None
    )
    initiative_score = (
        _nonnegative_score(
            100.0 * initiative_rate / parameters["initiative_per_100_agent_ticks"]
        )
        if initiative_rate is not None
        else None
    )
    value_creation_score = (
        _nonnegative_score(
            100.0
            * net_value_creation_rate
            / parameters["value_creation_per_100_agent_ticks"]
        )
        if net_value_creation_rate is not None
        else None
    )
    enterprise_supply_rate = (
        100.0 * float(raw.get("enterprise_supply_value") or 0) / possible_ticks
        if possible_ticks > 0
        else None
    )
    enterprise_supply_score = (
        _nonnegative_score(
            100.0
            * enterprise_supply_rate
            / parameters["enterprise_supply_per_100_agent_ticks"]
        )
        if enterprise_supply_rate is not None
        else None
    )
    entrepreneurship = _geometric_mean(
        (enterprise_supply_score, value_creation_score)
    )

    return {
        "effective_execution": {
            "score": effective_execution,
            "components": {
                "submitted_actions": raw.get("submitted_actions", 0),
                "contention_excluded": raw.get("contention_failures", 0),
                "invalid_proposals": raw.get("invalid_proposals", 0),
                "engine_invalid_proposals": raw.get(
                    "engine_invalid_proposals",
                    raw.get("invalid_proposals", 0),
                ),
                "model_output_failures": raw.get("model_output_failures", 0),
                "action_point_overruns": raw.get("action_point_overruns", 0),
                "action_feasibility_pct": action_feasibility,
                "purposeful_agent_ticks": raw.get("purposeful_agent_ticks", 0),
                "decision_opportunities": raw.get("decisions", 0),
                "purposeful_agent_tick_pct": purposeful_agent_tick_pct,
            },
            "formula": (
                "geometric_mean(action feasibility, purposeful agent-tick rate); "
                "action feasibility = 100 * (submitted - contention - engine "
                "invalid - model-output failures) / (submitted - contention)"
            ),
        },
        "sustained_competence": {
            "score": competence,
            "components": {
                "effective_execution": effective_execution,
                "survival_exposure_pct": survival_exposure,
                "endpoint_population_health_pct": endpoint_population_health,
                "survival_continuity_pct": survival_continuity,
                "living_agents": raw.get("living_agents", 0),
                "initial_agents": raw.get("initial_agents", 0),
                "material_outcome_pct": material,
                "living_terminal_economic_value": living_terminal_value,
                "total_terminal_economic_value": raw.get(
                    "terminal_economic_value", 0
                ),
                "initial_endowment_value": initial_endowment,
                "material_target_value": material_target,
            },
            "formula": (
                "geometric_mean(effective execution, "
                "geometric_mean(target-horizon survival exposure, "
                "endpoint population health), living-accessible terminal value "
                f"relative to {parameters['material_endowment_multiple']:g}x starting endowment)"
            ),
        },
        "entrepreneurial_agency": {
            "score": entrepreneurship,
            "components": {
                "enterprise_supply_value": raw.get("enterprise_supply_value", 0),
                "enterprise_supply_by_source": raw.get(
                    "enterprise_supply_by_source", {}
                ),
                "enterprise_supply_per_100_agent_ticks": _rounded(
                    enterprise_supply_rate
                ),
                "enterprise_supply_score": enterprise_supply_score,
                "own_capital_output_value": raw.get("own_capital_output_value", 0),
                "own_capital_output_note": (
                    "Reported, not scored here. Output from the cohort's own "
                    "improved land stays in cohort inventory, so net value "
                    "creation already counts it. Scoring it again would "
                    "double-count the same harvests across both halves of the "
                    "geometric mean."
                ),
                "informal_transfer_value": raw.get("informal_transfer_value", 0),
                "informal_transfer_note": (
                    "Gifts judged unrequited or unclassifiable in the frozen "
                    "classification artifact, plus any unclassified gifts. "
                    "Reported, never scored: consideration is the boundary "
                    "between commerce and charity, and ambiguity does not "
                    "score."
                ),
                "net_value_created": _rounded(net_value_created),
                "net_value_created_per_100_agent_ticks": _rounded(
                    net_value_creation_rate
                ),
                "value_creation_score": value_creation_score,
                "venture_initiatives": raw.get("venture_initiatives", 0),
                "venture_initiatives_per_100_agent_ticks": _rounded(initiative_rate),
                "initiative_score": initiative_score,
                "initiative_note": (
                    "Venture initiatives are a diagnostic in the finalized v4 "
                    "scoring. They count attempts, several of which cost no "
                    "action points, so they are too cheap to saturate to gate "
                    "the score."
                ),
            },
            "formula": (
                f"geometric_mean(enterprise supply rate vs {parameters['enterprise_supply_per_100_agent_ticks']:g}/100 agent-ticks, "
                "positive living-accessible net value creation rate vs "
                f"{parameters['value_creation_per_100_agent_ticks']:g}/100 agent-ticks); 100 is the "
                "reference target, not a maximum"
            ),
            "scale": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
            },
        },
        "economic_productivity": {
            "score": value_creation_score,
            "components": {
                "living_terminal_economic_value": living_terminal_value,
                "initial_endowment_value": initial_endowment,
                "net_value_created": _rounded(net_value_created),
                "net_value_created_per_100_agent_ticks": _rounded(
                    net_value_creation_rate
                ),
            },
            "formula": (
                "positive living-accessible terminal value minus starting "
                "endowment, per 100 agent-ticks, relative to the frozen target"
            ),
            "scale": {
                "minimum": 0.0,
                "maximum": None,
                "reference_target": 100.0,
                "higher_is_better": True,
            },
        },
    }


def _report_providers(benchmark: dict[str, Any]) -> set[str]:
    """Return the provider adapters a scored report's cohorts actually invoked."""

    return {
        str(cohort.get("provider"))
        for cohort in (benchmark.get("cohorts") or {}).values()
        if cohort.get("provider")
    }


def aggregate_benchmark_reports(reports: Iterable[dict[str, Any]], protocol_id: str | None = None) -> dict[str, Any]:
    """Pool protocol-compliant replication counts into model benchmark results."""

    reports = list(reports)
    declared = {(r.get("benchmarks", {}).get("protocol") or {}).get("id") for r in reports}
    supported = declared & set(RECIPES)
    if protocol_id is None and len(supported) > 1:
        raise ValueError("Mixed benchmark recipes; select a protocol explicitly before aggregating")
    recipe = get_recipe(protocol_id or next(iter(supported), None))
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    rejected: list[dict[str, Any]] = []
    for report in reports:
        benchmark = report.get("benchmarks") or {}
        report_protocol = benchmark.get("protocol") or {}
        report_fingerprint = report_protocol.get("code_fingerprint_sha256")
        prior_suite = None
        if benchmark.get("suite_id") != recipe.suite_id:
            # Retain explicit historical audits; never infer equivalence between
            # selectable recipes, even if their scoring formulas are shared.
            prior_suite = (
                BENCHMARK_ACCEPTED_PRIOR_SUITE_REPORTS.get(
                    (str(benchmark.get("suite_id")), str(report_fingerprint))
                )
                if recipe.id == DEFAULT_PROTOCOL_ID and report_protocol.get("id") not in RECIPES
                else None
            )
            if prior_suite is None:
                rejected.append(
                    {
                        "source": report.get("source"),
                        "reason": "missing_or_incompatible_benchmark_suite",
                    }
                )
                continue
        else:
            if report_protocol.get("id") != recipe.id:
                rejected.append({"source": report.get("source"), "reason": "benchmark_recipe_mismatch"})
                continue
            # Compare against a fingerprint scoped to the providers this report
            # actually used, so an unrelated adapter cannot invalidate it.
            expected_fingerprint = benchmark_code_fingerprint(
                _report_providers(benchmark), recipe.id
            )
            # Membership alone decides: the registry entry is the audit that
            # the code separating the stored fingerprint from the current one
            # cannot move this report's numbers. A revision comparison would
            # wrongly reject a resumed run, which reports at the current
            # revision but keeps its launch-time fingerprint.
            compatible_prior_report = (
                recipe.id == DEFAULT_PROTOCOL_ID
                and report_fingerprint in BENCHMARK_COMPATIBLE_REPORT_FINGERPRINTS
            )
            if report_fingerprint != expected_fingerprint and not compatible_prior_report:
                rejected.append(
                    {
                        "source": report.get("source"),
                        "reason": "benchmark_code_fingerprint_mismatch",
                    }
                )
                continue
        trial = benchmark.get("trial") or {}
        seed = trial.get("seed")
        report_usage = report.get("usage") or {}
        for cohort_id, cohort in (benchmark.get("cohorts") or {}).items():
            identity = (
                str(cohort.get("brain") or "unknown"),
                str(cohort.get("model") or "unknown"),
                str(cohort.get("reasoning_effort") or "unknown"),
            )
            if prior_suite is not None and cohort.get("provider") not in prior_suite["providers"]:
                # The prior-suite audit covers specific providers only; a
                # cohort on any other provider is not carried over.
                rejected.append(
                    {
                        "source": report.get("source"),
                        "cohort": cohort_id,
                        "model": identity[1],
                        "reason": "prior_suite_provider_not_audited",
                    }
                )
                continue
            if not cohort.get("protocol_compliant"):
                rejected.append(
                    {
                        "source": report.get("source"),
                        "cohort": cohort_id,
                        "model": identity[1],
                        "reason": "diagnostic_only",
                        "quality_flags": cohort.get("quality_flags") or [],
                    }
                )
                continue
            cohort_raw = cohort.get("raw") or {}
            if recipe.scoring_policy == "outcome-production" and any(
                item["score"] is None for item in score_benchmark_counts(cohort_raw, recipe.id).values()
            ):
                rejected.append({"source": report.get("source"), "reason": "scoring_evidence_unavailable"})
                continue
            row = grouped.setdefault(
                identity,
                {
                    "brain": identity[0],
                    "model": identity[1],
                    "reasoning_effort": identity[2],
                    "seeds": set(),
                    "seed_counts": Counter(),
                    "sources": [],
                    "source_scoring_revisions": set(),
                    "declared_deviations": [],
                    "replications": [],
                    "reasoning_tokens_total": 0,
                    "llm_calls_total": 0,
                    "reasoning_tokens_estimated": False,
                },
            )
            row["seeds"].add(int(seed))
            row["seed_counts"][int(seed)] += 1
            row["sources"].append(report.get("source"))
            row["source_scoring_revisions"].add(
                int(report_protocol.get("scoring_revision") or 1)
            )
            # Deliberation actually spent - benchmark runs are one uniform
            # cohort, so run-level usage attributes cleanly to it.
            row["reasoning_tokens_total"] += int(report_usage.get("reasoning_tokens") or 0)
            row["llm_calls_total"] += int(report_usage.get("calls") or 0)
            row["reasoning_tokens_estimated"] = row["reasoning_tokens_estimated"] or bool(
                report_usage.get("reasoning_tokens_estimated")
            )
            if prior_suite is not None:
                row["declared_deviations"].append(
                    {
                        "seed": int(seed),
                        "source": report.get("source"),
                        "protocol": str(benchmark.get("suite_id")),
                        "deviation": prior_suite["deviation"],
                        "audited": prior_suite["audited"],
                    }
                )
            deviation = trial.get("accepted_prior_trial")
            if deviation:
                row["declared_deviations"].append(
                    {"seed": int(seed), "source": report.get("source"), **deviation}
                )
            override = cohort.get("attribution_override")
            if override:
                row["declared_deviations"].append(
                    {
                        "seed": int(seed),
                        "source": report.get("source"),
                        "protocol": trial.get("declared_protocol"),
                        "deviation": override.get("deviation"),
                        "audited": " ".join(
                            part
                            for part in (
                                override.get("sensitivity"),
                                override.get("accepted_because"),
                            )
                            if part
                        ),
                    }
                )
            row["replications"].append(
                {
                    "seed": int(seed),
                    "source": report.get("source"),
                    "raw": cohort_raw,
                    "scores": score_benchmark_counts(cohort_raw, recipe.id),
                    "efficiency": report_usage.get("decision_latency"),
                    "api_list_cost_usd": (
                        ((report_usage.get("attempted_token_cost") or report_usage.get("estimated_cost") or {}).get("cost_usd") or {}).get("total")
                        if (report_usage.get("attempted_token_cost") or report_usage.get("estimated_cost") or {}).get("available")
                        else None
                    ),
                }
            )

    results: list[dict[str, Any]] = []
    for row in grouped.values():
        seeds = sorted(row.pop("seeds"))
        seed_counts = row.pop("seed_counts")
        source_scoring_revisions = sorted(row.pop("source_scoring_revisions"))
        declared_deviations = row.pop("declared_deviations")
        replications = sorted(
            row.pop("replications"),
            key=lambda replication: (
                replication["seed"],
                str(replication.get("source") or ""),
            ),
        )
        required_seeds = sorted(frozenset(recipe.required_seeds) & set(seeds))
        extended_seeds = sorted(frozenset(recipe.extended_seeds) & set(seeds))
        required_replications = [
            replication
            for replication in replications
            if replication["seed"] in frozenset(recipe.required_seeds)
        ]
        extended_replications = [
            replication
            for replication in replications
            if replication["seed"] in frozenset(recipe.extended_seeds)
        ]
        official_raw: dict[str, Any] = {}
        for replication in required_replications:
            _merge_numeric_tree(official_raw, replication.get("raw") or {})
        all_raw: dict[str, Any] = {}
        for replication in replications:
            _merge_numeric_tree(all_raw, replication.get("raw") or {})

        missing_seeds = sorted(frozenset(recipe.required_seeds) - set(required_seeds))
        certification_flags = []
        if missing_seeds:
            certification_flags.append("missing_required_seeds")
        if any(seed_counts[seed] != 1 for seed in required_seeds):
            certification_flags.append("duplicate_seed_replication")
        certified = not certification_flags
        provisional = (
            required_seeds == [recipe.provisional_seed]
            and seed_counts[recipe.provisional_seed] == 1
            and certification_flags == ["missing_required_seeds"]
        )
        if certified and declared_deviations:
            # Still certified: every required seed is present and clean. The
            # label carries the deviation so no reader can mistake it for a
            # trial run entirely under current code.
            status = "certified_with_declared_deviation"
        elif certified:
            status = "certified"
        elif provisional and declared_deviations:
            status = "provisional_with_declared_deviation"
        elif provisional:
            status = "provisional"
        else:
            status = "incomplete_replication"
        results.append(
            {
                **row,
                "mean_reasoning_tokens_per_call": (
                    round(row["reasoning_tokens_total"] / row["llm_calls_total"], 1)
                    if row["llm_calls_total"]
                    else None
                ),
                "seeds": seeds,
                "required_seeds": required_seeds,
                "extended_seeds": extended_seeds,
                "certified": certified,
                "provisional": provisional,
                "status": status,
                "certification_flags": certification_flags,
                "declared_deviations": declared_deviations,
                "source_scoring_revisions": source_scoring_revisions,
                "scoring_revision": recipe.scoring_revision,
                "replications": replications,
                "required_replications": required_replications,
                "extended_replications": extended_replications,
                "score_spread": _score_spread(required_replications),
                "extended_score_spread": (
                    _score_spread(replications) if extended_replications else None
                ),
                "raw": official_raw,
                "scores": score_benchmark_counts(official_raw, recipe.id),
                "extended_raw": all_raw if extended_replications else None,
                "extended_scores": (
                    score_benchmark_counts(all_raw, recipe.id)
                    if extended_replications
                    else None
                ),
            }
        )
    results.sort(
        key=lambda row: (
            -_score_or_negative(row["scores"]["capability" if recipe.scoring_policy == "outcome-production" else "sustained_competence"]["score"]),
            row["model"],
        )
    )
    return {
        "suite_id": recipe.suite_id,
        "protocol": benchmark_protocol(recipe.id),
        "results": results,
        "rejected": rejected,
    }


def format_benchmark_leaderboard(aggregate: dict[str, Any]) -> str:
    """Render a compact human-readable leaderboard."""

    if (aggregate.get("protocol") or {}).get("scoring_policy") == "outcome-production":
        return _format_outcome_leaderboard(aggregate)
    lines = [
        f"# Agent World benchmark: {aggregate.get('suite_id')}",
        "",
        "| Model | Seeds | Execution | Competence | Entrepreneurship | Invalid proposals | Reasoning/decision | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in aggregate.get("results") or []:
        scores = row.get("scores") or {}
        raw = row.get("raw") or {}
        status = row.get("status") or (
            "certified" if row.get("certified") else "incomplete_replication"
        )
        status = str(status).replace("_", " ")
        seed_text = ",".join(
            str(value) for value in row.get("required_seeds") or []
        )
        if row.get("extended_seeds"):
            seed_text += f" (+{len(row['extended_seeds'])} extended)"
        reasoning = row.get("mean_reasoning_tokens_per_call")
        if reasoning is None:
            reasoning_text = "n/a"
        else:
            # "~" marks adapter-side estimates (Claude CLI has no thinking split).
            prefix = "~" if row.get("reasoning_tokens_estimated") else ""
            reasoning_text = f"{prefix}{reasoning:.0f} tok"
        lines.append(
            f"| {row.get('model')} | {seed_text} "
            f"| {_format_score(scores.get('effective_execution', {}).get('score'))} "
            f"| {_format_score(scores.get('sustained_competence', {}).get('score'))} "
            f"| {_format_score(scores.get('entrepreneurial_agency', {}).get('score'))} "
            f"| {_format_count_rate(raw.get('invalid_proposals'), raw.get('submitted_actions'))} "
            f"| {reasoning_text} "
            f"| {status} |"
        )
    replications = [
        (row, replication)
        for row in aggregate.get("results") or []
        for replication in row.get("replications") or []
    ]
    if replications:
        lines += [
            "",
            "## Per-replication scores",
            "",
            "| Model | Seed | Role | Execution | Competence | Entrepreneurship |",
            "|---|---:|---|---:|---:|---:|",
        ]
        for row, replication in replications:
            scores = replication.get("scores") or {}
            role = (
                "certification"
                if replication.get("seed") in ((aggregate.get("protocol") or {}).get("replications") or {}).get("required_seeds", sorted(BENCHMARK_SEEDS))
                else "optional extended"
            )
            lines.append(
                f"| {row.get('model')} | {replication.get('seed')} | {role} "
                f"| {_format_score((scores.get('effective_execution') or {}).get('score'))} "
                f"| {_format_score((scores.get('sustained_competence') or {}).get('score'))} "
                f"| {_format_score((scores.get('entrepreneurial_agency') or {}).get('score'))} |"
            )
        lines += [
            "",
            "Descriptive spread:",
            "",
        ]
        for row in aggregate.get("results") or []:
            competence_spread = (
                (row.get("score_spread") or {}).get("sustained_competence") or {}
            )
            difference = competence_spread.get("absolute_difference")
            difference_text = (
                _format_score(difference) if difference is not None else "n/a"
            )
            lines.append(
                f"- {row.get('model')}: official competence range "
                f"{_format_score(competence_spread.get('minimum'))}–"
                f"{_format_score(competence_spread.get('maximum'))}, "
                f"absolute seed difference {difference_text}."
            )
            if row.get("extended_score_spread"):
                extended_competence = (
                    row["extended_score_spread"].get("sustained_competence") or {}
                )
                lines.append(
                    f"  Optional extended evidence ({len(row.get('extended_seeds') or [])} "
                    f"extra seed(s)): full range "
                    f"{_format_score(extended_competence.get('minimum'))}–"
                    f"{_format_score(extended_competence.get('maximum'))}."
                )
    deviating = [
        row for row in aggregate.get("results") or [] if row.get("declared_deviations")
    ]
    if deviating:
        lines += ["", "## Declared deviations", ""]
        for row in deviating:
            # Group identical deviations so a two-seed pair reads as one entry,
            # but never collapse distinct ones: a cohort can carry both a
            # prior-protocol deviation and an attribution override, and both
            # have to be visible.
            grouped: dict[tuple[Any, ...], list[int]] = {}
            for item in row["declared_deviations"]:
                key = (
                    item.get("protocol"),
                    item.get("deviation"),
                    item.get("audited"),
                )
                grouped.setdefault(key, []).append(item.get("seed"))
            for (protocol, deviation, audited), seeds in grouped.items():
                seed_text = ", ".join(str(seed) for seed in sorted(seeds))
                lines += [
                    f"- **{row.get('model')}** (seed {seed_text}) ran under "
                    f"`{protocol}`, accepted as v4 evidence after audit.",
                    f"  - Deviation: {deviation}",
                    f"  - Audit: {audited}",
                ]
    if aggregate.get("rejected"):
        lines += [
            "",
            f"Excluded diagnostic/noncompliant cohort results: {len(aggregate['rejected'])}.",
        ]
    return "\n".join(lines) + "\n"


def _cohort_raw_metrics(
    *,
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    config: dict[str, Any],
    member_ids: list[str],
    final_tick: int,
    target_ticks: int,
    gift_verdicts: dict[int, str] | None = None,
    transfer_accounting: str = "self_declared",
) -> dict[str, Any]:
    members = set(member_ids)
    responses = [
        event
        for event in events
        if event.get("type") == "agent_response" and event.get("actor_id") in members
    ]
    submitted = sum(
        len((event.get("data") or {}).get("actions") or [])
        for event in responses
    )
    invalid_events = [
        event
        for event in events
        if event.get("type") == "invalid_action" and event.get("actor_id") in members
    ]
    contention_events = [
        event
        for event in events
        if event.get("type") == "contention_failure" and event.get("actor_id") in members
    ]
    benchmark_horizon = target_ticks if target_ticks > 0 else final_tick
    possible_ticks = len(member_ids) * benchmark_horizon
    observed_ticks = len(member_ids) * final_tick
    initial_per_agent = _initial_endowment_value(config)
    terminal_value = _terminal_economic_value(snapshot, config, members)
    snapshot_agents = snapshot.get("agents") or {}
    living_members = {
        agent_id
        for agent_id in members
        if bool((snapshot_agents.get(agent_id) or {}).get("alive"))
    }
    living_terminal_value = _terminal_economic_value(
        snapshot,
        config,
        living_members,
    )
    endpoint_health_points = sum(
        max(
            0.0,
            min(
                100.0,
                float((snapshot_agents.get(agent_id) or {}).get("health") or 0),
            ),
        )
        for agent_id in members
    )
    initiative_counts = Counter(
        str(event.get("type"))
        for event in events
        if event.get("actor_id") in members
        and (
            event.get("type") in VENTURE_INITIATIVE_EVENTS
            or (
                event.get("type") == "build"
                and "contributed" in (event.get("data") or {})
            )
        )
    )
    enterprise = _enterprise_supply(events, members, gift_verdicts, transfer_accounting)
    purposeful_agent_ticks = {
        (int(event.get("tick") or 0), str(event.get("actor_id") or ""))
        for event in events
        if event.get("actor_id") in members
        and event.get("type") in PURPOSEFUL_ACTION_EVENTS
        and (
            event.get("type") != "fulfill_contract"
            or (event.get("data") or {}).get("voluntary") is True
        )
    }
    decision_failures = sum(
        is_decision_failure_message(event.get("type"), event.get("message"))
        for event in responses
    )
    model_output_failures = sum(
        is_model_output_failure_message(event.get("type"), event.get("message"))
        for event in responses
    )
    external_decision_failures = sum(
        is_quota_failure_message(event.get("type"), event.get("message"))
        or is_provider_failure_message(event.get("type"), event.get("message"))
        or is_harness_failure_message(event.get("type"), event.get("message"))
        or is_ambiguous_boundary_failure_message(
            event.get("type"),
            event.get("message"),
        )
        for event in responses
    )
    engine_invalid_proposals = len(invalid_events)
    return {
        "initial_agents": len(member_ids),
        "possible_agent_ticks": possible_ticks,
        "observed_agent_ticks": observed_ticks,
        "decisions": len(responses),
        "decision_failures": decision_failures,
        "model_output_failures": model_output_failures,
        "external_decision_failures": external_decision_failures,
        "submitted_actions": submitted,
        "contention_failures": len(contention_events),
        "submitted_actions_excluding_contention": max(
            0, submitted - len(contention_events)
        ),
        "engine_invalid_proposals": engine_invalid_proposals,
        "invalid_proposals": engine_invalid_proposals + model_output_failures,
        "action_point_overruns": sum(
            "action point" in str(event.get("message") or "").lower()
            for event in invalid_events
        ),
        "initial_endowment_value": initial_per_agent * len(member_ids),
        "terminal_economic_value": _rounded(terminal_value),
        "living_agents": len(living_members),
        "endpoint_health_points": _rounded(endpoint_health_points),
        "endpoint_health_capacity": 100 * len(member_ids),
        "living_terminal_economic_value": _rounded(living_terminal_value),
        "purposeful_agent_ticks": len(purposeful_agent_ticks),
        "venture_initiatives": sum(initiative_counts.values()),
        "venture_initiatives_by_type": dict(sorted(initiative_counts.items())),
        "enterprise_supply_value": _rounded(enterprise["total"]),
        "enterprise_supply_by_source": enterprise["by_source"],
        "own_capital_output_value": enterprise["own_capital_output"],
        "informal_transfer_value": enterprise["informal_transfers"],
    }


def _trial_flags(
    report: dict[str, Any],
    start_data: dict[str, Any],
    cohorts: dict[str, Any],
    protocol_id: str | None = None,
) -> list[str]:
    run = report.get("run") or {}
    config = report.get("config") or {}
    reliability = report.get("reliability") or {}
    flags: list[str] = []

    recipe = get_recipe(protocol_id)
    expected = benchmark_protocol(recipe.id)["trial"]
    used_provider = next(
        (
            str(cohort.get("provider"))
            for cohort in cohorts.values()
            if cohort.get("provider")
        ),
        None,
    )
    checks = {
        "agents": ((report.get("population") or {}).get("total_agents"), expected["agents"]),
        "ticks": (run.get("target_ticks"), expected["ticks"]),
        "final_tick": (run.get("final_tick"), expected["ticks"]),
        "economy_mode": (config.get("economy_mode"), expected["economy_mode"]),
        "world_variant": (
            config.get("world_variant") or "classic",
            expected["world_variant"],
        ),
        "geography_mode": (config.get("geography_mode"), expected["geography_mode"]),
        "specialization_mode": (
            config.get("specialization_mode"),
            expected["specialization_mode"],
        ),
        "objective_mode": (config.get("objective_mode"), expected["objective_mode"]),
        "transfer_kind_mode": (
            config.get("transfer_kind_mode", recipe.defaults()["transfer_kind_mode"]),
            recipe.defaults()["transfer_kind_mode"],
        ),
        "decision_mode": (start_data.get("decision_mode"), expected["decision_mode"]),
        "action_feedback_mode": (
            start_data.get("action_feedback_mode"),
            expected["action_feedback_mode"],
        ),
        "connector_profile": (
            start_data.get("connector_profile"),
            expected["connector_profile"],
        ),
        "conversation_mode": (
            start_data.get("conversation_mode"),
            expected["conversation_mode"],
        ),
        "turn_resolution": (
            start_data.get("turn_resolution"),
            expected["turn_resolution"],
        ),
    }
    for name in ("observation_history_policy", "codex_action_max_items"):
        if name in start_data or start_data.get("recipe_fingerprint_sha256"):
            checks[name] = (start_data.get(name), recipe.defaults()[name])
    from dataclasses import fields
    from agent_world.models import WorldConfig
    for field in fields(WorldConfig):
        if field.name in recipe.defaults() and (field.name in config or start_data.get("recipe_fingerprint_sha256")):
            checks[field.name] = (config.get(field.name), recipe.defaults()[field.name])
    for name, (actual, wanted) in checks.items():
        if actual != wanted:
            flags.append(f"protocol_mismatch:{name}")
    if start_data.get("recipe_fingerprint_sha256") not in {None, recipe.digest}:
        flags.append("recipe_fingerprint_mismatch")
    source_fingerprint = start_data.get("benchmark_code_fingerprint")
    compatible_source = (
        recipe.id == DEFAULT_PROTOCOL_ID
        and start_data.get("benchmark_protocol") == recipe.id
        and source_fingerprint in BENCHMARK_COMPATIBLE_SOURCE_FINGERPRINTS
    )
    accepted_prior = accepted_prior_trial(
        start_data.get("benchmark_protocol"),
        source_fingerprint,
    )
    if (
        start_data.get("benchmark_protocol") != recipe.id
        and accepted_prior is None
    ):
        flags.append("benchmark_protocol_not_declared")
    # Scoped to the providers these cohorts ran on, so editing an adapter this
    # trial never invoked does not retroactively invalidate it.
    trial_providers = {
        str(cohort.get("provider"))
        for cohort in cohorts.values()
        if cohort.get("provider")
    }
    if (
        source_fingerprint != benchmark_code_fingerprint(trial_providers or None, recipe.id)
        and not compatible_source
        and accepted_prior is None
    ):
        flags.append("benchmark_code_fingerprint_mismatch")
    if config.get("seed") not in recipe.allowed_seeds:
        flags.append("nonstandard_seed")
    if not run.get("completed"):
        flags.append("run_not_completed")
    if len(cohorts) != 1:
        flags.append("population_not_uniform")
    else:
        cohort = next(iter(cohorts.values()))
        if cohort.get("reasoning_effort") != expected["reasoning_effort"]:
            flags.append("protocol_mismatch:reasoning_effort")
        if cohort.get("initial_agents") != expected["agents"]:
            flags.append("protocol_mismatch:cohort_size")
    integrity_status = reliability.get("benchmark_integrity_status")
    if integrity_status is not None:
        if integrity_status != "clean":
            flags.append("run_integrity_not_clean")
    elif reliability.get("quality_status") != "clean":
        flags.append("run_quality_not_clean")
    if reliability.get("usage_record_coverage_pct") != 100.0:
        flags.append("usage_coverage_not_complete")
    if start_data.get("agent_io_log") is not True:
        flags.append("protocol_mismatch:agent_io_log")
    return flags


def _cohort_diagnostics(
    events: list[dict[str, Any]],
    members: set[str],
    raw: dict[str, Any],
) -> dict[str, Any]:
    counts = Counter(
        str(event.get("type"))
        for event in events
        if event.get("actor_id") in members
    )
    possible = float(raw.get("possible_agent_ticks") or 0)
    return {
        "communications": counts.get("say", 0)
        + counts.get("whisper", 0)
        + counts.get("broadcast", 0),
        "gifts": counts.get("gift", 0),
        "trades_accepted": counts.get("accept_trade", 0),
        "construction_contributions": counts.get("contribute", 0),
        "groups_created": counts.get("create_group", 0),
        "communications_per_100_agent_ticks": (
            round(
                100
                * (
                    counts.get("say", 0)
                    + counts.get("whisper", 0)
                    + counts.get("broadcast", 0)
                )
                / possible,
                2,
            )
            if possible
            else None
        ),
        "note": (
            "Social activity is diagnostic only in v4: frequency does not establish "
            "coordination quality or prosocial/antisocial intent."
        ),
    }


def _terminal_economic_value(
    snapshot: dict[str, Any],
    config: dict[str, Any],
    members: set[str],
) -> float:
    value = 0.0
    agents = snapshot.get("agents") or {}
    for agent_id in members:
        value += _book_value((agents.get(agent_id) or {}).get("inventory"))

    groups = snapshot.get("groups") or {}
    for structure in (snapshot.get("structures") or {}).values():
        if structure.get("status") != "complete":
            continue
        asset_value = float(
            _structure_replacement_value(
                str(structure.get("type") or ""),
                str(config.get("economy_mode") or "baseline"),
                str(config.get("world_variant") or "classic"),
            )
        )
        asset_value += _book_value(structure.get("inventory"))
        asset_value += _book_value(structure.get("treasury"))
        asset_value += _book_value(structure.get("upkeep_reserve"))
        value += _attributed_owner_value(
            str(structure.get("owner_id") or ""),
            asset_value,
            members,
            groups,
        )

    for item in (snapshot.get("items") or {}).values():
        owner = str(item.get("owner_id") or "")
        if owner in members:
            value += BENCHMARK_ACCOUNTING_VALUES.get(
                str(item.get("item") or ""), 1
            ) * int(item.get("quantity") or 0)

    for trade in (snapshot.get("trades") or {}).values():
        if (
            trade.get("status") == "open"
            and str(trade.get("from_agent") or "") in members
        ):
            value += _book_value(trade.get("give")) * int(
                trade.get("lots_remaining") or 1
            )
    for contract in (snapshot.get("contracts") or {}).values():
        if (
            contract.get("status") == "offered"
            and str(contract.get("lender_id") or "") in members
        ):
            value += _book_value(contract.get("advance"))
        elif (
            contract.get("status") == "active"
            and str(contract.get("borrower_id") or "") in members
        ):
            value += _book_value(contract.get("collateral"))
    return value


def _attributed_owner_value(
    owner_id: str,
    value: float,
    members: set[str],
    groups: dict[str, Any],
) -> float:
    if owner_id in members:
        return value
    group = groups.get(owner_id)
    if not isinstance(group, dict):
        return 0.0
    group_members = [str(agent_id) for agent_id in group.get("members") or []]
    if not group_members:
        return 0.0
    matching = sum(agent_id in members for agent_id in group_members)
    return value * matching / len(group_members)


def _enterprise_supply(
    events: list[dict[str, Any]],
    members: set[str],
    gift_verdicts: dict[int, str] | None = None,
    transfer_accounting: str = "self_declared",
) -> dict[str, Any]:
    """Measure enterprise activity that survives cohort-level netting.

    Terminal value is a cohort balance sheet, so one member selling to another
    cannot move it. That does not make intra-cohort commerce worthless: it
    makes the balance sheet the wrong instrument. Enterprise supply instead
    measures directional flow, which is what distinguishes a producer with
    customers from a subsistence forager.

    Each component nets an agent's outflows against its inflows before any
    credit is given, so value that returns to its origin scores nothing. A
    wash trade cancels exactly. A circular A->B->C->A flow also cancels,
    because netting is per agent across all counterparties rather than per
    trading pair. Only a persistent directional surplus - goods produced in
    excess of what was consumed and then supplied to others - can score.
    """

    exported: dict[str, Counter] = {}
    imported: dict[str, Counter] = {}
    service_in: Counter = Counter()
    service_out: Counter = Counter()
    capital_output = 0.0
    informal_transfers = 0.0
    gift_ordinal = -1
    verdicts = gift_verdicts or {}

    def _flow(sender: str, receiver: str, items: Any) -> None:
        if not isinstance(items, dict):
            return
        for item, quantity in items.items():
            amount = max(0, int(quantity or 0))
            if amount <= 0:
                continue
            if sender in members:
                exported.setdefault(sender, Counter())[str(item)] += amount
            if receiver in members:
                imported.setdefault(receiver, Counter())[str(item)] += amount

    for event in events:
        event_type = event.get("type")
        data = event.get("data") or {}
        if event_type == "accept_trade":
            trade = data.get("trade") or {}
            transaction = data.get("transaction") or {}
            offerer = str(trade.get("from_agent") or "")
            acceptor = str(
                trade.get("accepted_by")
                or transaction.get("buyer_id")
                or event.get("actor_id")
                or ""
            )
            # The transaction block is per accepted lot; the trade block is the
            # whole standing offer and would overcount a multi-lot trade.
            give = transaction.get("give", trade.get("give"))
            receive = transaction.get("receive", trade.get("receive"))
            _flow(offerer, acceptor, give)
            _flow(acceptor, offerer, receive)
        elif event_type == "contract_settled":
            contract = data.get("contract") or {}
            transaction = data.get("transaction") or {}
            proposer = str(contract.get("proposer_id") or transaction.get("seller_id") or "")
            buyer = str(contract.get("buyer_id") or transaction.get("buyer_id") or "")
            give = transaction.get("give", contract.get("give"))
            receive = transaction.get("receive", contract.get("receive"))
            _flow(proposer, buyer, give)
            _flow(buyer, proposer, receive)
        elif event_type == "gift":
            # Scoring revision 2: a raw gift is never enterprise supply. It
            # scores only through a frozen classification - barter legs are
            # goods flows, payments are service income earned by the
            # RECIPIENT (the vendor; the sender is the buyer). Unrequited,
            # unclassifiable, or unclassified transfers are reported only,
            # so ambiguity can never inflate a certified score.
            gift_ordinal += 1
            giver = str(event.get("actor_id") or "")
            recipient = str(data.get("to") or "")
            verdict = verdicts.get(gift_ordinal)
            if verdict is None and transfer_accounting == "self_declared":
                # V7 self-classification: trust the sender's declared kind.
                declared = str(data.get("kind") or "").strip().lower()
                if declared == "payment":
                    verdict = GIFT_VERDICT_PAYMENT
                elif declared == "barter":
                    verdict = GIFT_VERDICT_BARTER
            if verdict == GIFT_VERDICT_BARTER:
                _flow(giver, recipient, data.get("items"))
            elif verdict == GIFT_VERDICT_PAYMENT:
                value = _book_value(data.get("items"))
                if recipient in members:
                    service_in[recipient] += value
                if giver in members:
                    service_out[giver] += value
            else:
                if giver in members or recipient in members:
                    informal_transfers += _book_value(data.get("items"))
        elif event_type == "pay_access_fee":
            payer = str(event.get("actor_id") or "")
            owner = next(
                (str(value) for value in event.get("recipients") or []),
                "",
            )
            fee = _book_value(data.get("fee"))
            if owner in members:
                service_in[owner] += fee
            if payer in members:
                service_out[payer] += fee
        elif event_type in {"fulfill_contract", "repay_contract"}:
            contract = data.get("contract") or data
            premium = _book_value(contract.get("repayment")) - _book_value(
                contract.get("advance")
            )
            if premium <= 0:
                continue
            lender = str(contract.get("lender_id") or "")
            borrower = str(contract.get("borrower_id") or "")
            if lender in members:
                service_in[lender] += premium
            if borrower in members:
                service_out[borrower] += premium
        elif event_type == "harvest" and data.get("improved_land") is True:
            actor = str(event.get("actor_id") or "")
            if actor in members:
                capital_output += BENCHMARK_ACCOUNTING_VALUES.get(
                    str(data.get("resource") or ""), 1.0
                ) * max(0, int(data.get("quantity") or 0))

    goods_supplied = 0.0
    for agent_id in members:
        agent_exports = exported.get(agent_id) or Counter()
        agent_imports = imported.get(agent_id) or Counter()
        for item, amount in agent_exports.items():
            if item in ENTERPRISE_SUPPLY_EXCLUDED_GOODS:
                continue
            net = amount - agent_imports.get(item, 0)
            if net > 0:
                net_value = BENCHMARK_ACCOUNTING_VALUES.get(item, 1.0) * net
                goods_supplied += net_value

    service_income = sum(
        max(0.0, float(service_in.get(agent_id, 0)) - float(service_out.get(agent_id, 0)))
        for agent_id in members
    )
    by_source = {
        "net_goods_supplied_to_others": _rounded(goods_supplied),
        "net_service_income": _rounded(service_income),
    }
    return {
        # Own capital output is deliberately excluded from the scored total.
        # Goods harvested from a cohort's own improved land stay in the
        # cohort's inventory, so their value is already counted by net value
        # creation. Adding them here would score the same harvest events
        # twice and re-couple the two halves of the geometric mean, which is
        # the defect this construct exists to avoid. They remain reported
        # because "built producing capital" is worth seeing on its own.
        "total": goods_supplied + service_income,
        "by_source": by_source,
        "own_capital_output": _rounded(capital_output),
        "informal_transfers": _rounded(informal_transfers),
    }


def _initial_endowment_value(config: dict[str, Any]) -> float:
    inventory = {"food": 1, "water": 2}
    if config.get("economy_mode") == "organic":
        inventory["coin"] = 4
    return _book_value(inventory)


def _structure_replacement_value(
    structure_type: str, economy_mode: str, world_variant: str = "classic"
) -> float:
    # Variant-aware: without this, frontier structures (road, irrigation)
    # valued at zero, silently penalizing exactly the capital formation the
    # frontier world exists to reward.
    recipe = recipes_for_mode(economy_mode, world_variant).get(structure_type)
    return _book_value(getattr(recipe, "inputs", {})) if recipe is not None else 0.0


def _book_value(items: Any) -> float:
    if not isinstance(items, dict):
        return 0.0
    return sum(
        BENCHMARK_ACCOUNTING_VALUES.get(str(item), 1.0)
        * max(0, int(quantity or 0))
        for item, quantity in items.items()
    )


def _latest_lifecycle_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            event
            for event in reversed(events)
            if event.get("type") in {"run_started", "run_resumed"}
        ),
        None,
    )


def _benchmark_trajectory(events: list[dict[str, Any]], protocol_id: str | None = None) -> list[dict[str, Any]]:
    """Recover trajectory checkpoints belonging to the selected recipe."""

    recipe = get_recipe(protocol_id)
    checkpoints: dict[int, dict[str, Any]] = {}
    for event in events:
        if event.get("type") != "benchmark_checkpoint":
            continue
        data = event.get("data") or {}
        if (
            data.get("suite_id") != recipe.suite_id
            or data.get("protocol_id") != recipe.id
        ):
            continue
        try:
            tick = int(data.get("tick"))
        except (TypeError, ValueError):
            continue
        stored_cohorts = data.get("cohorts")
        if tick not in recipe.checkpoints or not isinstance(stored_cohorts, dict):
            continue
        checkpoint_model_failures: int | None = None
        checkpoint_external_failures: int | None = None
        if len(stored_cohorts) == 1:
            checkpoint_responses = [
                candidate
                for candidate in events
                if candidate.get("type") == "agent_response"
                and int(candidate.get("tick") or 0) < tick
            ]
            checkpoint_model_failures = sum(
                is_model_output_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                for candidate in checkpoint_responses
            )
            checkpoint_external_failures = sum(
                is_quota_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                or is_provider_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                or is_harness_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                or is_ambiguous_boundary_failure_message(
                    candidate.get("type"),
                    candidate.get("message"),
                )
                for candidate in checkpoint_responses
            )
        cohorts: dict[str, Any] = {}
        for cohort_id, cohort in stored_cohorts.items():
            if not isinstance(cohort, dict):
                continue
            raw = _normalize_model_failure_raw(
                cohort.get("raw") or {},
                model_output_failures=checkpoint_model_failures,
                external_decision_failures=checkpoint_external_failures,
            )
            cohorts[str(cohort_id)] = {
                **cohort,
                "raw": raw,
                "scores": score_benchmark_counts(raw, recipe.id),
            }
        try:
            score_horizon = int(data.get("score_horizon_ticks") or tick)
        except (TypeError, ValueError):
            score_horizon = tick
        checkpoints[tick] = {
            "tick": tick,
            "score_horizon_ticks": score_horizon,
            "role": (
                "official_endpoint"
                if tick == recipe.checkpoints[-1]
                else "diagnostic_checkpoint"
            ),
            "cohorts": cohorts,
        }
    return [checkpoints[tick] for tick in sorted(checkpoints)]


def _normalize_model_failure_raw(
    raw: dict[str, Any],
    *,
    model_output_failures: int | None,
    external_decision_failures: int | None,
) -> dict[str, Any]:
    """Normalize durable checkpoint failure counts from the event ledger."""

    normalized = dict(raw)
    if "engine_invalid_proposals" in normalized:
        return normalized
    engine_invalid = int(normalized.get("invalid_proposals") or 0)
    model_failures = int(
        model_output_failures
        if model_output_failures is not None
        else normalized.get("model_output_failures")
        or 0
    )
    normalized["engine_invalid_proposals"] = engine_invalid
    normalized["model_output_failures"] = model_failures
    normalized["external_decision_failures"] = int(
        external_decision_failures
        if external_decision_failures is not None
        else normalized.get("external_decision_failures")
        or 0
    )
    normalized["invalid_proposals"] = engine_invalid + model_failures
    return normalized


def _geometric_mean(values: Iterable[float | None]) -> float | None:
    supplied = tuple(values)
    parsed = [float(value) for value in supplied if value is not None]
    if not parsed:
        return None
    if len(parsed) != len(supplied):
        return None
    if any(value <= 0 for value in parsed):
        return 0.0
    return round(math.prod(parsed) ** (1.0 / len(parsed)), 2)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 2)


def _nonnegative_score(value: float) -> float:
    return round(max(0.0, value), 2)


def _rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _score_or_negative(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else -1.0


def _format_score(value: Any) -> str:
    return f"{float(value):.1f}" if isinstance(value, (int, float)) else "n/a"


def _format_count_rate(value: Any, denominator: Any) -> str:
    count = int(value or 0)
    total = int(denominator or 0)
    if total <= 0:
        return f"{count} (n/a)"
    return f"{count} ({100.0 * count / total:.1f}%)"


def _score_spread(replications: list[dict[str, Any]]) -> dict[str, Any]:
    """Return transparent descriptive uncertainty without changing pooled scores."""

    spread: dict[str, Any] = {}
    for score_key in (
        "effective_execution",
        "sustained_competence",
        "entrepreneurial_agency",
        "economic_productivity",
        "execution", "capability", "production",
    ):
        values = [
            float(score)
            for replication in replications
            if isinstance(
                score := (
                    (replication.get("scores") or {}).get(score_key) or {}
                ).get("score"),
                (int, float),
            )
        ]
        if not values:
            continue
        row: dict[str, Any] = {
            "n": len(values),
            "values": [round(value, 2) for value in values],
            "minimum": round(min(values), 2),
            "maximum": round(max(values), 2),
            "range_width": round(max(values) - min(values), 2),
        }
        if len(values) == 2:
            row["absolute_difference"] = round(abs(values[1] - values[0]), 2)
        spread[score_key] = row
    return spread


def _merge_numeric_tree(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            target[key] = target.get(key, 0) + value
        elif isinstance(value, dict):
            nested = target.setdefault(key, {})
            if isinstance(nested, dict):
                _merge_numeric_tree(nested, value)


def _format_outcome_leaderboard(aggregate: dict[str, Any]) -> str:
    lines = [f"# Agent World benchmark: {aggregate.get('suite_id')}", "",
             "| Model | Capability | Execution | Production | Cost/run | Mean time/decision |",
             "|---|---:|---:|---:|---:|---:|"]
    for row in aggregate.get("results") or []:
        reps = row.get("required_replications") or []
        costs = [rep.get("api_list_cost_usd") for rep in reps]
        cost = sum(costs) / len(costs) if costs and all(c is not None for c in costs) else None
        efficiencies = [rep.get("efficiency") or {} for rep in reps]
        decisions = sum(e.get("decisions", 0) for e in efficiencies)
        latency = (sum(e["total_seconds"] for e in efficiencies) / decisions
                   if decisions and all(e.get("complete") for e in efficiencies) else None)
        scores = row["scores"]
        lines.append(f"| {row['model']} | {_format_score(scores['capability']['score'])} "
                     f"| {_format_score(scores['execution']['score'])} | {_format_score(scores['production']['score'])} "
                     f"| {'n/a' if cost is None else f'${cost:.2f}'} "
                     f"| {'n/a' if latency is None else f'{latency:.2f}s'} |")
    lines += ["", "Cost/run is API-list equivalent per world, including recorded retries; subscription charges differ.",
              "Latency sums recorded call durations per resolved decision, excluding between-call quota sleeps.",
              "Production is fixed accounting value added per 100 original-population agent-ticks; it is unbounded.",
              "", "## Replications", ""]
    for row in aggregate.get("results") or []:
        lines.append(f"- {row['model']}: {row['status']}; required seeds {row['required_seeds']}.")
        for rep in row.get("replications") or []:
            scores = rep["scores"]
            lines.append(f"  - Seed {rep['seed']}: capability {_format_score(scores['capability']['score'])}, "
                         f"execution {_format_score(scores['execution']['score'])}, "
                         f"production {_format_score(scores['production']['score'])}.")
    return "\n".join(lines) + "\n"
