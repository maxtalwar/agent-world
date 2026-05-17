"""Agent brain interfaces and deterministic non-LLM brains for testing."""

from __future__ import annotations

from typing import Any, Protocol

from agent_world.models import AgentDecision


class AgentBrain(Protocol):
    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        """Return an AgentDecision for a single tick."""


class NullBrain:
    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        return AgentDecision(intent="Wait and observe.", actions=[{"type": "wait"}])


class SurvivalBrain:
    """Small deterministic brain used for testing rails, not for emergence claims."""

    def decide(self, observation: dict[str, Any]) -> AgentDecision:
        self_state = observation["self"]
        needs = self_state["needs"]
        inventory = self_state["inventory"]
        position = self_state["position"]

        actions: list[dict[str, Any]] = []
        memory_updates: list[str] = []

        if needs["water"] < 55 and inventory.get("water", 0) > 0:
            actions.append({"type": "consume", "item": "water"})
        if needs["food"] < 60 and inventory.get("food", 0) > 0:
            actions.append({"type": "consume", "item": "food"})

        current_tile = _tile_at(observation, position["x"], position["y"])
        if len(actions) < 3 and current_tile:
            if inventory.get("water", 0) < 2 and current_tile["resources"].get("water", 0) > 0:
                actions.append({"type": "gather", "resource": "water"})
            elif inventory.get("food", 0) < 3 and current_tile["resources"].get("food", 0) > 0:
                actions.append({"type": "gather", "resource": "food"})
            elif inventory.get("wood", 0) < 3 and current_tile["resources"].get("wood", 0) > 0:
                actions.append({"type": "chop"})
            elif inventory.get("stone", 0) < 2 and current_tile["resources"].get("stone", 0) > 0:
                actions.append({"type": "mine", "resource": "stone"})

        if len(actions) < 3 and _can_craft_tool(inventory):
            actions.append({"type": "craft", "recipe": "tool"})

        if not actions or len(actions) < 2:
            move = _move_toward_resource(observation, needed_resources=["water", "food", "wood", "stone"])
            actions.append(move or {"type": "wait"})

        if current_tile:
            memory_updates.append(
                f"At ({position['x']}, {position['y']}) terrain is {current_tile['terrain']} with resources {current_tile['resources']}."
            )

        return AgentDecision(
            intent="Maintain basic needs using locally visible resources.",
            actions=actions[:3],
            messages=[],
            memory_updates=memory_updates[:1],
        )


def _tile_at(observation: dict[str, Any], x: int, y: int) -> dict[str, Any] | None:
    for tile in observation["local_map"]:
        if tile["x"] == x and tile["y"] == y:
            return tile
    return None


def _can_craft_tool(inventory: dict[str, int]) -> bool:
    return inventory.get("wood", 0) >= 1 and inventory.get("stone", 0) >= 1 and inventory.get("fiber", 0) >= 1


def _move_toward_resource(observation: dict[str, Any], needed_resources: list[str]) -> dict[str, str] | None:
    current = observation["self"]["position"]
    best_tile: dict[str, Any] | None = None
    best_score: tuple[int, int] | None = None
    for tile in observation["local_map"]:
        if tile["x"] == current["x"] and tile["y"] == current["y"]:
            continue
        resource_score = sum(tile["resources"].get(resource, 0) for resource in needed_resources)
        if resource_score <= 0:
            continue
        distance = abs(tile["x"] - current["x"]) + abs(tile["y"] - current["y"])
        score = (-resource_score, distance)
        if best_score is None or score < best_score:
            best_score = score
            best_tile = tile
    if best_tile is None:
        return None
    dx = best_tile["x"] - current["x"]
    dy = best_tile["y"] - current["y"]
    if abs(dx) >= abs(dy) and dx != 0:
        return {"type": "move", "direction": "east" if dx > 0 else "west"}
    if dy != 0:
        return {"type": "move", "direction": "south" if dy > 0 else "north"}
    return None
