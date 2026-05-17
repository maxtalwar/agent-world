"""Simulation runner that connects brains to the world engine."""

from __future__ import annotations

from typing import Any

from agent_world.agents import AgentBrain
from agent_world.interface import build_agent_prompt, build_observation, parse_agent_response
from agent_world.models import AgentDecision
from agent_world.world import WorldEngine


class SimulationRunner:
    """Orchestrates observe -> decide -> validate ticks.

    The runner logs observations and prompts as private events so a run can be
    audited without exposing one agent's private context to another agent.
    """

    def __init__(
        self,
        engine: WorldEngine,
        brains: dict[str, AgentBrain],
        log_agent_io: bool = True,
    ):
        self.engine = engine
        self.brains = brains
        self.log_agent_io = log_agent_io

    def step(self) -> list[Any]:
        decisions: dict[str, AgentDecision] = {}
        for agent_id in sorted(self.engine.state.agents):
            agent = self.engine.state.agents[agent_id]
            if not agent.alive:
                continue
            brain = self.brains.get(agent_id)
            if brain is None:
                continue
            observation = build_observation(self.engine.state, agent_id)
            prompt = build_agent_prompt(observation)
            if self.log_agent_io:
                self.engine.log_event(
                    "agent_observation",
                    actor_id=agent_id,
                    position=agent.position,
                    data={"observation": observation},
                    scope="private",
                    recipients={agent_id},
                )
                self.engine.log_event(
                    "agent_prompt",
                    actor_id=agent_id,
                    position=agent.position,
                    data={"prompt": prompt},
                    scope="private",
                    recipients={agent_id},
                )
            decisions[agent_id] = parse_agent_response(brain.decide(observation))
        return self.engine.tick(decisions)
