#!/usr/bin/env python3
"""Build a curated mid-run mock snapshot with native simulation dataclasses.

This is staged illustration data, not a recorded run or benchmark evidence.
No model calls, simulation jobs, or changes to real run artifacts are made.
"""
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_world.models import Position, Structure, WorldConfig
from agent_world.world import WorldEngine

def build_demo():
    engine = WorldEngine.create(
        config=WorldConfig(seed=11),
        agent_names=["Ada", "Finn", "Mira", "Theo", "June", "Kit", "Sage", "Leo", "Nora", "Ash"],
    )
    engine.state.tick = 48
    positions = [(5, 10), (7, 11), (8, 8), (5, 7), (10, 10),
                 (8, 12), (3, 5), (10, 4), (3, 10), (10, 12)]
    for index, agent in enumerate(engine.state.agents.values()):
        agent.position = Position(*positions[index])
        agent.health = 92 + index % 9
        agent.needs.food, agent.needs.water, agent.needs.energy = 14, 16, 22
        agent.inventory = Counter(food=2, water=2)
    agents = list(engine.state.agents)
    # Native structure types, actual map coordinates, valid one-tile footprints.
    sites = [
        ("farm_plot", 5, 9), ("farm_plot", 6, 9), ("farm_plot", 5, 10),
        ("farm_plot", 6, 10), ("farm_plot", 5, 11), ("farm_plot", 6, 11),
        ("house", 7, 7), ("house", 5, 7), ("house", 7, 12),
        ("shelter", 4, 8), ("shelter", 11, 11),
        ("workshop", 8, 10), ("storage", 7, 10), ("storage", 8, 11),
        ("well", 8, 8), ("house", 10, 12),
    ]
    for index, (kind, x, y) in enumerate(sites):
        sid = f"structure-{index + 1}"
        structure = Structure(id=sid, type=kind, position=Position(x, y),
                              owner_id=agents[index % len(agents)],
                              public_access=True)
        if kind == "storage":
            structure.inventory = Counter(wood=10, stone=6, fiber=5, food=12)
        if index == len(sites) - 1:
            structure.status = "under_construction"
            structure.remaining_inputs = Counter(wood=4, fiber=1)
        engine.state.structures[sid] = structure
        tile = engine.state.tiles[y][x]
        tile.structure_ids.append(sid)
        if kind == "farm_plot":
            tile.resources["food"] = (10, 17, 23, 14, 20, 8)[index]
    return {
        "world": {"run_id": "demo", "cell_id": "seed-11", "title": "Willowbank",
                  "seed": 11, "target_ticks": 120, "state": "demo", "demo": True,
                  "description": "A growing settlement in the standard world. Curated demo snapshot."},
        "snapshot": engine.snapshot(), "refresh_seconds": 30,
    }

if __name__ == "__main__":
    target = Path(__file__).resolve().parents[1] / "agent_world/static/world-demo.json"
    target.write_text(json.dumps(build_demo(), separators=(",", ":")) + "\n", encoding="utf-8")
