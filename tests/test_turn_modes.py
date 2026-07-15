from __future__ import annotations

import unittest

from agent_world.models import AgentDecision, WorldConfig
from agent_world.run_report import build_report
from agent_world.runner import SimulationRunner
from agent_world.world import WorldEngine


class _DecisionBrain:
    def __init__(self, decision: AgentDecision):
        self.decision = decision
        self.observations: list[dict] = []

    def decide(self, observation):
        self.observations.append(observation)
        return self.decision


class TurnModeTests(unittest.TestCase):
    def _engine(self) -> WorldEngine:
        return WorldEngine.create(WorldConfig(seed=19), agent_names=["A1", "A2", "A3"])

    def test_shuffled_order_is_reproducible_and_changes_across_ticks(self) -> None:
        first = self._engine()
        second = self._engine()

        first_orders = []
        second_orders = []
        for _ in range(4):
            first_orders.append(first.activation_order("shuffled-sequential-v1"))
            second_orders.append(second.activation_order("shuffled-sequential-v1"))
            first.tick({}, turn_mode="shuffled-sequential-v1")
            second.tick({}, turn_mode="shuffled-sequential-v1")

        self.assertEqual(first_orders, second_orders)
        self.assertGreater(len({tuple(order) for order in first_orders}), 1)

    def test_sequential_later_agent_observes_earlier_same_tick_speech(self) -> None:
        engine = self._engine()
        order = engine.activation_order("shuffled-sequential-v1")
        speaker = _DecisionBrain(
            AgentDecision(actions=[{"type": "say", "text": "same tick signal"}])
        )
        listener = _DecisionBrain(AgentDecision(actions=[{"type": "wait"}]))
        brains = {
            order[0]: speaker,
            order[1]: listener,
            order[2]: _DecisionBrain(AgentDecision(actions=[{"type": "wait"}])),
        }

        SimulationRunner(
            engine,
            brains,
            turn_mode="shuffled-sequential-v1",
        ).step()

        visible = listener.observations[0]["recent_events"]
        self.assertTrue(
            any(event["type"] == "say" and "same tick signal" in event["message"] for event in visible)
        )
        listener_observation = next(
            event
            for event in engine.state.events
            if event.type == "agent_observation" and event.actor_id == order[1]
        )
        self.assertEqual(listener_observation.data["activation"]["observed_after_activations"], 1)
        self.assertIn("say", listener_observation.data["activation"]["observed_same_tick_event_types"])

    def test_simultaneous_agents_do_not_observe_same_tick_speech(self) -> None:
        engine = self._engine()
        order = engine.activation_order("simultaneous-v1")
        listener = _DecisionBrain(AgentDecision(actions=[{"type": "wait"}]))
        brains = {
            order[0]: _DecisionBrain(
                AgentDecision(actions=[{"type": "say", "text": "same tick signal"}])
            ),
            order[1]: listener,
            order[2]: _DecisionBrain(AgentDecision(actions=[{"type": "wait"}])),
        }

        SimulationRunner(engine, brains, turn_mode="simultaneous-v1").step()

        self.assertFalse(
            any(event["type"] == "say" and "same tick signal" in event["message"] for event in listener.observations[0]["recent_events"])
        )

    def test_report_records_activation_order_visibility_and_position_bins(self) -> None:
        engine = self._engine()
        order = engine.activation_order("shuffled-sequential-v1")
        brains = {
            order[0]: _DecisionBrain(AgentDecision(actions=[{"type": "say", "text": "hello"}])),
            order[1]: _DecisionBrain(AgentDecision(actions=[{"type": "move", "direction": "sideways"}])),
            order[2]: _DecisionBrain(AgentDecision(actions=[{"type": "wait"}])),
        }
        SimulationRunner(
            engine, brains, turn_mode="shuffled-sequential-v1"
        ).step()

        report = build_report(
            [event.to_dict() for event in engine.state.events], engine.snapshot()
        )

        dynamics = report["turn_dynamics"]
        self.assertEqual(dynamics["mode"], "shuffled-sequential-v1")
        self.assertEqual(dynamics["ticks_with_schedule"], 1)
        self.assertGreaterEqual(dynamics["observations_with_same_tick_events"], 1)
        self.assertEqual(dynamics["invalid_actions_with_prior_resolutions"], 1)
        self.assertEqual(dynamics["invalid_actions_with_unobserved_prior_resolutions"], 0)
        self.assertIn("middle", dynamics["by_activation_position"])


if __name__ == "__main__":
    unittest.main()
