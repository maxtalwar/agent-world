"""Single-variable ablation sweeps for diagnosing what suppresses investment.

Each variant changes exactly one thing relative to the baseline so the effect can
be attributed. Run the same seed/agents across variants and diff the metrics.

Survival-pressure signals (median_lifespan, spare capacity) are model-independent
and meaningful even with the deterministic ``survival`` brain. The investment
signals (builds, ever_buildable) require agents that actually try to build, so use
``--brain openrouter`` for those columns.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Callable

from agent_world.agents import SurvivalBrain
from agent_world.metrics import compute_metrics, is_quota_failure_message
from agent_world.models import WorldConfig
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


# Each variant: optional WorldConfig field overrides plus an optional tick multiplier.
DEFAULT_VARIANTS: dict[str, dict[str, Any]] = {
    "baseline": {},
    "carry_capacity_30": {"config": {"default_carry_capacity": 30}},
    "energy_max_50": {"config": {"energy_reserve_start": 40, "energy_reserve_max": 50}},
    "water_decay_1": {"config": {"survival_water_decay": 1}},
    "wild_food_0.70": {"config": {"wild_food_density": 0.70}},
    "horizon_3x": {"ticks_multiplier": 3},
}

# Columns extracted from each run's metrics, in display order.
ROW_FIELDS = ["ticks", "alive", "med_life", "builds", "sites", "coop", "structures", "trades", "invalid", "spare_ap", "energy"]


def run_ablation(
    *,
    agents: int,
    ticks: int,
    seed: int,
    brain_factory: Callable[[str], Any],
    variants: dict[str, dict[str, Any]] | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Run the baseline and each variant, returning (name, summary-row) pairs."""
    variants = variants or DEFAULT_VARIANTS
    results: list[tuple[str, dict[str, Any]]] = []
    for name, variant in variants.items():
        config_overrides = dict(variant.get("config", {}))
        run_ticks = int(ticks * variant.get("ticks_multiplier", 1))
        metrics = _run_one(
            agents=agents,
            ticks=run_ticks,
            seed=seed,
            brain_factory=brain_factory,
            config_overrides=config_overrides,
        )
        results.append((name, _summary_row(metrics)))
    return results


def _run_one(
    *,
    agents: int,
    ticks: int,
    seed: int,
    brain_factory: Callable[[str], Any],
    config_overrides: dict[str, Any],
) -> dict[str, Any]:
    config = replace(WorldConfig(width=16, height=16, seed=seed), **config_overrides)
    names = [f"Agent {index + 1}" for index in range(agents)]
    engine = WorldEngine.create(config=config, agent_names=names)
    brains = {agent_id: brain_factory(agent_id) for agent_id in engine.state.agents}
    runner = SimulationRunner(engine, brains, log_agent_io=False, concurrent_decisions=False, max_workers=1)
    for _ in range(ticks):
        events = runner.step()
        if any(is_quota_failure_message(getattr(e, "type", None), getattr(e, "message", None)) for e in events):
            break
    return compute_metrics(engine.state)


def _summary_row(metrics: dict[str, Any]) -> dict[str, Any]:
    agents = metrics.get("agents", {})
    infra = metrics.get("infrastructure", {})
    construction = metrics.get("construction", {})
    capacity = metrics.get("capacity", {})
    trade = metrics.get("trade", {})
    structures = sum(infra.get("structures_by_type", {}).values())
    return {
        "ticks": metrics.get("tick", 0),
        "alive": f"{agents.get('living', 0)}/{agents.get('total', 0)}",
        "med_life": agents.get("median_lifespan", 0),
        "builds": infra.get("builds", 0),
        "sites": construction.get("sites_in_progress", 0),
        "coop": construction.get("cooperative_sites", 0),
        "structures": structures,
        "trades": trade.get("accepted", 0),
        "invalid": metrics.get("invalid_actions", {}).get("total", 0),
        "spare_ap": capacity.get("median_spare_action_points", 0),
        "energy": capacity.get("median_energy", 0),
    }


def format_table(results: list[tuple[str, dict[str, Any]]]) -> str:
    headers = ["variant", *ROW_FIELDS]
    rows = [[name, *[str(row.get(field, "")) for field in ROW_FIELDS]] for name, row in results]
    widths = [max(len(headers[col]), *(len(row[col]) for row in rows)) for col in range(len(headers))]
    line = "  ".join(header.ljust(widths[col]) for col, header in enumerate(headers))
    sep = "  ".join("-" * widths[col] for col in range(len(headers)))
    body = "\n".join("  ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) for row in rows)
    return "\n".join([line, sep, body])


def survival_brain_factory(_agent_id: str) -> SurvivalBrain:
    return SurvivalBrain()
