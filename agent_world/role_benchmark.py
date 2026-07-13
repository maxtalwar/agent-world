"""Scripted baseline for checking whether specialist starting packages are viable."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean, median
from typing import Any, Iterable

from agent_world.agents import SurvivalBrain
from agent_world.models import WorldConfig
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


def run_role_viability_benchmark(seeds: Iterable[int], ticks: int = 50) -> dict[str, Any]:
    """Run one non-social scripted agent per specialist role for each seed.

    This is a diagnostic floor, not a model comparison: the scripted brain does
    not trade, gift, communicate, or exploit specialist production strategies.
    """

    seed_list = [int(seed) for seed in seeds]
    if ticks <= 0:
        raise ValueError("ticks must be positive")
    if not seed_list:
        raise ValueError("at least one seed is required")
    records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for seed in seed_list:
        engine = WorldEngine.create(
            WorldConfig(
                seed=seed,
                economy_mode="organic",
                geography_mode="dispersed",
                specialization_mode="specialists",
                objective_mode="neutral",
            ),
            agent_names=["Farmer", "Forester", "Miner", "Fisher", "Artisan"],
        )
        runner = SimulationRunner(
            engine,
            {agent_id: SurvivalBrain() for agent_id in engine.state.agents},
            log_agent_io=False,
        )
        while engine.state.tick < ticks and any(agent.alive for agent in engine.state.agents.values()):
            runner.step()
        death_ticks = {
            event.actor_id: event.tick for event in engine.state.events if event.type == "death"
        }
        for agent in engine.state.agents.values():
            records[agent.specialty or "generalist"].append(
                {
                    "seed": seed,
                    "agent_id": agent.id,
                    "alive": agent.alive,
                    "lifespan_ticks": ticks if agent.alive else int(death_ticks.get(agent.id, engine.state.tick)),
                    "health": agent.health,
                }
            )
    return {
        "schema_version": 1,
        "description": "Non-social scripted survival floor for experimental specialist packages.",
        "seeds": seed_list,
        "ticks": ticks,
        "roles": {
            role: {
                "runs": len(role_records),
                "survived": sum(record["alive"] for record in role_records),
                "survival_pct": round(100 * sum(record["alive"] for record in role_records) / len(role_records), 1),
                "mean_lifespan_ticks": round(mean(record["lifespan_ticks"] for record in role_records), 2),
                "median_lifespan_ticks": median(record["lifespan_ticks"] for record in role_records),
                "records": role_records,
            }
            for role, role_records in sorted(records.items())
        },
    }
