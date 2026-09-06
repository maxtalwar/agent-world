"""Gross productive value added; exchanges and inventory movements are not output."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from agent_world.outcome_scoring import ScoringEvidenceError, score_outcome_counts
from agent_world.rules import recipes_for_mode

EXTRACTION_EVENTS = frozenset({"gather", "chop", "mine", "harvest", "fish"})


def derive_production_counts(events: list[dict[str, Any]], *, member_ids: list[str],
                             target_ticks: int, economy_mode: str,
                             accounting_values: dict[str, float]) -> dict[str, Any]:
    """Credit goods entering inventory once, with craft inputs netted out.

    Farm tending and passive regrowth change the tile's resource pool. They are
    intermediate output: credit arrives at extraction/harvest, never twice.
    Capital formation has no standalone bonus; its subsequent output counts.
    """
    if target_ticks <= 0 or not member_ids or len(set(member_ids)) != len(member_ids):
        raise ScoringEvidenceError("Production requires a positive horizon and unique original population")
    members = set(member_ids)
    recipes = recipes_for_mode(economy_mode)
    output = inputs = improved = 0.0
    by_source = defaultdict(float)

    def value(items):
        if not isinstance(items, dict):
            raise ScoringEvidenceError("Missing production quantities")
        total = 0.0
        for item, quantity in items.items():
            if (item not in accounting_values or isinstance(quantity, bool)
                    or not isinstance(quantity, (int, float))
                    or not math.isfinite(quantity) or quantity < 0):
                raise ScoringEvidenceError("Unknown resource or invalid production quantity")
            total += accounting_values[item] * quantity
        return total

    for event in events:
        if event.get("actor_id") not in members or not 0 <= event.get("tick", -1) < target_ticks:
            continue
        kind, data = event.get("type"), event.get("data") or {}
        if kind in EXTRACTION_EVENTS:
            amount = value({data.get("resource"): data.get("quantity")})
            output += amount
            by_source[kind] += amount
            if data.get("improved_land") or data.get("source") == "well":
                improved += amount
        elif kind == "craft":
            recipe = recipes.get(data.get("recipe"))
            if recipe is None or not recipe.outputs or data.get("outputs") != dict(recipe.outputs):
                raise ScoringEvidenceError("Craft output does not match the source recipe")
            produced, consumed = value(data["outputs"]), value(dict(recipe.inputs))
            output += produced
            inputs += consumed
            by_source["craft_value_added"] += produced - consumed
    return {
        "production_output_value": output,
        "production_intermediate_input_value": inputs,
        "production_value_added": output - inputs,
        "production_possible_agent_ticks": len(members) * target_ticks,
        "production_by_source": dict(by_source),
        "productive_capital_extraction_value": improved,
    }


def score_production_counts(raw: dict[str, Any]) -> dict[str, Any]:
    required = ("production_output_value", "production_intermediate_input_value",
                "production_value_added", "production_possible_agent_ticks")
    try:
        output, inputs, added, capacity = (float(raw[key]) for key in required)
    except (KeyError, ValueError, TypeError) as exc:
        raise ScoringEvidenceError("Missing production counts") from exc
    if (not all(math.isfinite(v) for v in (output, inputs, added, capacity))
            or min(output, inputs) < 0 or capacity <= 0
            or not math.isclose(output - inputs, added, abs_tol=1e-7)):
        raise ScoringEvidenceError("Invalid production counts")
    return {
        "score": round(100 * max(0, added) / capacity, 2),
        "formula": "100 * max(0, output value - intermediate input value) / original-population agent-ticks",
        "unit": "fixed accounting units per 100 original-population agent-ticks",
        "components": {"output_value": output, "intermediate_input_value": inputs,
                       "value_added": added, "possible_agent_ticks": capacity},
    }


def score_outcome_production_counts(raw: dict[str, Any]) -> dict[str, Any]:
    return {**score_outcome_counts(raw), "production": score_production_counts(raw)}
