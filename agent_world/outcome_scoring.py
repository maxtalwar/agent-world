"""Outcome, execution, and production scoring independent of recipe identity."""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from agent_world.metrics import (
    is_ambiguous_boundary_failure_message,
    is_harness_failure_message,
    is_model_output_failure_message,
    is_provider_failure_message,
    is_quota_failure_message,
)

SCORING_COMPONENT_VERSION = "outcome-execution-v1"


class ScoringEvidenceError(ValueError):
    """Required evidence is missing, contradictory, or externally compromised."""


def derive_outcome_counts(
    events: list[dict[str, Any]],
    snapshot: dict[str, Any],
    *,
    member_ids: list[str],
    target_ticks: int,
    tail_ticks: int,
    require_completed: bool = True,
    execution_unit: str = "decision",
) -> dict[str, float]:
    """Derive additive counts from completed, original-population evidence.

    Health at observation tick t is the state after t completed world ticks.
    Use observations 1..T-1 and the terminal snapshot at T, excluding the
    unearned initial health at tick zero. Proven deaths contribute zero.
    Live diagnostic checkpoints may omit run_completed only when explicitly
    requested; benchmark certification independently requires completed evidence.
    """
    if target_ticks < 1 or not 1 <= tail_ticks <= target_ticks:
        raise ValueError("Require target_ticks >= tail_ticks >= 1")
    if not member_ids or len(set(member_ids)) != len(member_ids):
        raise ValueError("Require a nonempty unique original population")
    if snapshot.get("tick") != target_ticks or (require_completed and not any(
        e.get("type") == "run_completed" and e.get("tick") == target_ticks
        for e in events
    )):
        raise ScoringEvidenceError("A complete target-horizon run is required")
    members = set(member_ids)
    health: dict[tuple[int, str], float] = {}
    deaths: dict[str, int] = {}
    responses: dict[tuple[int, str], dict] = {}
    invalid: Counter = Counter()
    external_checks = (
        is_ambiguous_boundary_failure_message, is_harness_failure_message,
        is_provider_failure_message, is_quota_failure_message,
    )
    for event in events:
        actor = event.get("actor_id")
        if actor not in members:
            continue
        tick = int(event.get("tick", 0))
        kind = event.get("type")
        data = event.get("data") or {}
        key = (tick, actor)
        if kind == "death":
            deaths[actor] = min(tick, deaths.get(actor, tick))
        elif kind == "agent_observation" and 0 <= tick < target_ticks:
            observation = data.get("observation") or {}
            agent = observation.get("self") or {}
            if "health" not in agent:
                raise ScoringEvidenceError(f"Missing health observation at {key}")
            value = _health(agent["health"])
            if key in health and health[key] != value:
                raise ScoringEvidenceError(f"Conflicting health observations at {key}")
            health[key] = value
        elif kind == "agent_response" and 0 <= tick < target_ticks:
            if key in responses:
                raise ScoringEvidenceError(f"Duplicate resolved decision at {key}")
            if any(check(kind, event.get("message")) for check in external_checks):
                raise ScoringEvidenceError(f"External failure is not agent behavior at {key}")
            responses[key] = event
        elif kind == "invalid_action" and 0 <= tick < target_ticks:
            invalid[key] += 1

    agents = snapshot.get("agents") or {}
    full_sum = tail_sum = endpoint = 0.0
    for tick in range(target_ticks + 1):
        for actor in members:
            dead = actor in deaths and deaths[actor] < tick
            key = (tick, actor)
            if tick == target_ticks:
                agent = agents.get(actor)
                if not isinstance(agent, dict) or "alive" not in agent or "health" not in agent:
                    raise ScoringEvidenceError(f"Missing terminal agent {actor}")
                if bool(agent["alive"]) == dead:
                    raise ScoringEvidenceError(f"Death ledger disagrees with snapshot for {actor}")
                value = _health(agent["health"]) if agent["alive"] else 0.0
                endpoint += value
            else:
                if dead:
                    if key in responses or (key in health and health[key] != 0):
                        raise ScoringEvidenceError(f"Decision or positive health after death at {key}")
                    value = 0.0
                else:
                    if key not in health or key not in responses:
                        raise ScoringEvidenceError(f"Missing living-agent evidence at {key}")
                    value = health[key]
            if tick > 0:
                full_sum += value
                if tick > target_ticks - tail_ticks:
                    tail_sum += value

    if set(invalid) - set(responses):
        raise ScoringEvidenceError("Invalid-action events lack corresponding decisions")
    valid = sum(
        not invalid[key]
        and not is_model_output_failure_message(event.get("type"), event.get("message"))
        for key, event in responses.items()
    )
    action_counts = derive_action_execution_counts(responses) if execution_unit == "action" else {}
    if execution_unit not in {"decision", "action"}:
        raise ValueError("Unknown execution unit")
    return {
        **action_counts,
        "execution_valid_decisions": float(valid),
        "execution_decisions": float(len(responses)),
        "health_point_ticks": full_sum,
        "health_point_tick_capacity": float(100 * len(members) * target_ticks),
        "tail_health_point_ticks": tail_sum,
        "tail_health_point_tick_capacity": float(100 * len(members) * tail_ticks),
        "endpoint_health_points": endpoint,
        "endpoint_health_capacity": float(100 * len(members)),
    }



def derive_action_execution_counts(responses: dict) -> dict[str, float]:
    """Require exact per-proposal outcomes; never infer success from silence."""
    counts = Counter()
    for key, event in responses.items():
        if is_model_output_failure_message(event.get("type"), event.get("message")):
            # A malformed whole response supplies no attributable actions.
            # Retain it as one failed proposal, never a fabricated valid wait.
            counts["invalid"] += 1
            continue
        data = event.get("data") or {}
        execution = data.get("execution") or {}
        if execution.get("schema_version") != 1:
            raise ScoringEvidenceError(f"Missing per-action execution evidence at {key}")
        for lane in ("actions", "messages"):
            statuses = execution.get(lane)
            expected = len(data.get(lane) or [])
            if lane == "actions":
                expected = max(1, expected)  # Engine's implicit rest action.
            if not isinstance(statuses, list) or len(statuses) != expected:
                raise ScoringEvidenceError(f"Incomplete {lane} outcomes at {key}")
            if any(not isinstance(x, str) or x not in {"success", "invalid", "contention", "unexecuted"} for x in statuses):
                raise ScoringEvidenceError(f"Unknown action outcome at {key}")
            counts.update(statuses)
    return {
        "execution_valid_actions": float(counts["success"]),
        "execution_actions": float(counts["success"] + counts["invalid"] + counts["unexecuted"]),
        "execution_contention_actions": float(counts["contention"]),
        "execution_unexecuted_actions": float(counts["unexecuted"]),
    }

def _health(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ScoringEvidenceError("Health must be a finite number from 0 to 100")
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 100:
        raise ScoringEvidenceError("Health must be a finite number from 0 to 100")
    return value


def score_outcome_counts(raw: dict[str, float], *, execution_unit: str = "decision") -> dict[str, Any]:
    """Score pooled additive counts; never average rounded run scores."""
    def percent(numerator: str, denominator: str) -> float:
        try:
            n, d = float(raw[numerator]), float(raw[denominator])
        except (KeyError, TypeError, ValueError) as exc:
            raise ScoringEvidenceError(f"Missing numeric counts: {numerator}/{denominator}") from exc
        if not math.isfinite(n) or not math.isfinite(d) or d <= 0 or not 0 <= n <= d:
            raise ScoringEvidenceError(f"Invalid counts: {numerator}/{denominator}")
        return 100 * n / d

    if execution_unit == "action":
        execution = percent("execution_valid_actions", "execution_actions")
        execution_formula = "100 * successful actions / submitted non-contention actions"
        execution_components = {"valid_actions": raw["execution_valid_actions"],
                                "actions": raw["execution_actions"]}
    elif execution_unit == "decision":
        execution = percent("execution_valid_decisions", "execution_decisions")
        execution_formula = "100 * fully executable decisions / resolved decisions"
        execution_components = {"valid_decisions": raw["execution_valid_decisions"],
                                "decisions": raw["execution_decisions"]}
    else:
        raise ValueError("Unknown execution unit")
    full = percent("health_point_ticks", "health_point_tick_capacity")
    tail = percent("tail_health_point_ticks", "tail_health_point_tick_capacity")
    return {
        "execution": {
            "score": round(execution, 2),
            "formula": execution_formula,
            "components": execution_components,
        },
        "capability": {
            "score": round(math.sqrt(full * tail), 2),
            "formula": "geometric_mean(full-horizon population health %, final-window population health %)",
            "components": {"full_horizon_health_pct": round(full, 4),
                           "final_window_health_pct": round(tail, 4)},
        },
    }
