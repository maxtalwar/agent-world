import unittest
from collections import Counter
from unittest.mock import patch

from agent_world.interface import build_observation
from agent_world.models import AgentDecision, Structure, WorldConfig
from agent_world.world import WorldEngine
from agent_world.outcome_scoring import derive_action_execution_counts, ScoringEvidenceError
from agent_world.benchmarks import build_benchmark_results, aggregate_benchmark_reports
from agent_world.protocols import get_recipe, recipe_from_dict
from test_v8_pipeline import fixture


def engine():
    e = WorldEngine.create(WorldConfig(seed=3), agent_names=["A"])
    a = e.state.agents["agent-1"]
    a.inventory = Counter()
    return e, a


def action_counts(e, actions, messages=None):
    events = e.tick({ "agent-1": AgentDecision(actions=actions, messages=messages or []) })
    response = next(x for x in events if x.type == "agent_response")
    row = {"type": response.type, "message": response.message, "data": response.data}
    return derive_action_execution_counts({(response.tick, response.actor_id): row}), response


class CapacityFeedbackTests(unittest.TestCase):
    def test_resource_exists_but_weighted_capacity_is_insufficient(self):
        e, a = engine()
        a.inventory = Counter({"fiber": 9})  # 1 spare weight; water weighs 2.
        e.state.tile_at(a.position).resources["water"] = 5
        e.tick({"agent-1": AgentDecision(actions=[{"type": "gather", "resource": "water", "quantity": 1}])})
        failure = next(x for x in e.state.events if x.type == "invalid_action")
        self.assertIn("carrying capacity for water", failure.message)
        self.assertIn("9/10", failure.message)
        self.assertEqual(a.inventory["water"], 0)

    def test_well_reports_capacity_not_missing_water(self):
        e, a = engine()
        tile = e.state.tile_at(a.position)
        tile.resources["water"] = 0
        well = Structure(id="well-1", type="well", position=a.position, owner_id=a.id)
        e.state.structures[well.id] = well
        tile.structure_ids.append(well.id)
        a.inventory = Counter({"fiber": 10})
        e.tick({"agent-1": AgentDecision(actions=[{"type": "gather", "resource": "water", "quantity": 1}])})
        self.assertTrue(any(x.type == "invalid_action" and "carrying capacity" in x.message
                            for x in e.state.events))

    def test_freeing_capacity_allows_later_action_in_same_plan(self):
        e, a = engine()
        a.inventory = Counter({"fiber": 10})
        e.state.tile_at(a.position).resources["water"] = 5
        counts, _ = action_counts(e, [
            {"type": "gather", "resource": "water", "quantity": 1},
            {"type": "drop", "item": "fiber", "quantity": 2},
            {"type": "gather", "resource": "water", "quantity": 1},
        ])
        self.assertEqual(a.inventory["water"], 1)
        self.assertEqual(counts["execution_valid_actions"], 2)
        self.assertEqual(counts["execution_actions"], 3)

    def test_zero_quantity_does_not_claim_capacity_is_full(self):
        e, a = engine()
        e.state.tile_at(a.position).resources["water"] = 5
        e.tick({"agent-1": AgentDecision(actions=[{"type":"gather", "resource":"water", "quantity":0}])})
        failure = next(x for x in e.state.events if x.type == "invalid_action")
        self.assertIn("quantity", failure.message)
        self.assertNotIn("carrying capacity", failure.message)

    def test_absent_resource_remains_distinct_from_capacity(self):
        e, a = engine()
        e.state.tile_at(a.position).resources["wood"] = 0
        e.tick({"agent-1": AgentDecision(actions=[{"type": "chop", "resource": "wood", "quantity": 1}])})
        failure = next(x for x in e.state.events if x.type == "invalid_action")
        self.assertNotIn("carrying capacity", failure.message)


class ActionExecutionTests(unittest.TestCase):
    def test_bad_item_does_not_erase_successful_items(self):
        e, _ = engine()
        counts, response = action_counts(e, [{"type": "wait"}, {"type": "bogus"}, {"type": "wait"}])
        self.assertEqual(response.data["execution"]["actions"], ["success", "invalid", "success"])
        self.assertEqual(counts["execution_valid_actions"], 2)
        self.assertEqual(counts["execution_actions"], 3)

    def test_multiple_errors_from_one_proposal_count_once(self):
        e, a = engine()
        def fail(agent, action, ap):
            e._invalid(agent, action, "First issue")
            e._invalid(agent, action, "Second issue")
            return ap
        with patch.object(e, "_dispatch_action", side_effect=fail):
            counts, _ = action_counts(e, [{"type": "wait"}])
        self.assertEqual(counts["execution_actions"], 1)
        self.assertEqual(counts["execution_valid_actions"], 0)

    def test_unexecuted_tail_is_not_assumed_successful(self):
        e, _ = engine()
        counts, response = action_counts(e, [{"type": "wait"}] * 7)
        self.assertEqual(response.data["execution"]["actions"],
                         ["success"] * 4 + ["unexecuted"] * 3)
        self.assertEqual(counts["execution_valid_actions"], 4)
        self.assertEqual(counts["execution_actions"], 7)

    def test_contention_is_excluded_and_messages_count_once(self):
        e, _ = engine()
        def contested(agent, action, ap):
            e._invalid(agent, action, "Taken", failure_type="contention_failure")
            return ap
        with patch.object(e, "_dispatch_action", side_effect=contested):
            counts, _ = action_counts(e, [{"type": "wait"}])
        self.assertEqual(counts["execution_actions"], 0)
        self.assertEqual(counts["execution_contention_actions"], 1)
        e, _ = engine()
        counts, _ = action_counts(e, [{"type": "wait"}],
                                  [{"mode": "whisper", "to": "missing", "text": "hi"}])
        self.assertEqual(counts["execution_actions"], 2)
        self.assertEqual(counts["execution_valid_actions"], 1)

    def test_missing_telemetry_is_not_reconstructed_as_success(self):
        with self.assertRaises(ScoringEvidenceError):
            derive_action_execution_counts({(0,"a"):{"data":{"actions":[{"type":"wait"}]}}})

    def test_bad_model_output_never_earns_credit_for_fallback_wait(self):
        row = {"type":"agent_response", "message":"Codex model output contract failed: invalid JSON",
               "data":{"actions":[{"type":"wait"}]}}
        counts=derive_action_execution_counts({(0,"a"):row})
        self.assertEqual(counts["execution_actions"],1)
        self.assertEqual(counts["execution_valid_actions"],0)

    def test_implicit_rest_and_telemetry_stay_out_of_observation(self):
        e, a = engine()
        counts, _ = action_counts(e, [])
        self.assertEqual(counts["execution_valid_actions"],1)
        observation = build_observation(e.state, a.id)
        self.assertFalse(any(x["type"]=="agent_response" for x in observation["recent_events"]))

    def test_review_recipe_scores_actions_and_preserves_published_recipe(self):
        self.assertEqual(get_recipe("participant-v8").digest,
                         "cb02b974dfeea18806a55c6e404084e6fdfbbcb14c16e369057231b885fc3bf3")
        reports=[]
        for seed in (11,41):
            r, events, snapshot, _=fixture(seed, protocol="participant-v8-action-review")
            for e in events:
                if e["type"]=="agent_response":
                    e["data"]["actions"]=[{"type":"wait"},{"type":"bogus"},{"type":"wait"}]
                    e["data"]["execution"]={"schema_version":1,"actions":["success","invalid","success"],"messages":[]}
            r["benchmarks"]=build_benchmark_results(events,snapshot,r)
            reports.append(r)
        row=aggregate_benchmark_reports(reports,"participant-v8-action-review")["results"][0]
        self.assertEqual(row["scores"]["execution"]["score"],66.67)
        self.assertEqual(row["scores"]["capability"]["score"],80)

    def test_invalid_execution_unit_is_rejected(self):
        value=get_recipe("participant-v8-action-review").to_dict()
        value.pop("digest",None)
        value["scoring"]["parameters"]["execution_unit"]="tick"
        with self.assertRaises(ValueError):
            recipe_from_dict(value)
