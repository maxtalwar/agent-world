import copy
import unittest

from agent_world.benchmarks import BENCHMARK_ACCOUNTING_VALUES as VALUES
from agent_world.outcome_scoring import ScoringEvidenceError
from agent_world.production_scoring import derive_production_counts, score_production_counts
from agent_world.rules import recipes_for_mode
from agent_world.usage import summarize_decision_latency


def event(event_type, **data):
    return {"type": event_type, "tick": 0, "actor_id": "a", "data": data}


def counts(events, members=("a",), ticks=60):
    return derive_production_counts(events, member_ids=list(members), target_ticks=ticks,
                                    economy_mode="organic", accounting_values=VALUES)


class ProductionScoringTests(unittest.TestCase):
    def test_useful_output_is_independent_of_destination_and_specialization(self):
        output = event("harvest", resource="food", quantity=10, improved_land=True)
        base = counts([output])
        for flow in ("gift", "accept_trade", "contract_settled", "eat", "drop", "pickup"):
            self.assertEqual(base, counts([output, event(flow, items={"food": 10}, kind="payment")]))
        self.assertEqual(base["production_value_added"], 20)

    def test_farm_tending_and_unused_construction_do_not_double_count_harvest(self):
        actions = [event("build", completed=True), event("farm", quantity_added=12),
                   event("harvest", resource="food", quantity=5, improved_land=True)]
        self.assertEqual(counts(actions)["production_value_added"], 10)
        self.assertEqual(counts(actions[:-1])["production_value_added"], 0)

    def test_no_consumption_or_terminal_wealth_cliff(self):
        scores = []
        for quantity in (47, 49, 51, 53):
            raw = counts([event("gather", resource="water", quantity=quantity),
                          event("consume", quantity=50)])
            raw.update(initial_endowment_value=50, terminal_economic_value=quantity)
            scores.append(score_production_counts(raw)["score"])
        self.assertAlmostEqual(scores[1] - scores[0], scores[2] - scores[1], places=1)
        self.assertAlmostEqual(scores[2] - scores[1], scores[3] - scores[2], places=1)
        self.assertGreater(scores[0], 0)

    def test_crafting_counts_only_value_added_and_minting_is_not_free_wealth(self):
        recipe = recipes_for_mode("organic")["mint_coin"]
        raw = counts([event("craft", recipe="mint_coin", outputs=dict(recipe.outputs))])
        self.assertAlmostEqual(raw["production_value_added"], 0)
        self.assertEqual(score_production_counts(raw)["score"], 0)
        for name, recipe in recipes_for_mode("organic").items():
            if not recipe.outputs:
                continue
            extraction = [event("gather", resource=item, quantity=qty) for item, qty in recipe.inputs.items()]
            raw = counts(extraction + [event("craft", recipe=name, outputs=dict(recipe.outputs))])
            expected = sum(VALUES[item] * qty for item, qty in recipe.outputs.items())
            self.assertAlmostEqual(raw["production_value_added"], expected)

    def test_transfers_cannot_create_production_and_deaths_do_not_shrink_capacity(self):
        raw = counts([event("gift", items={"ore": 999}, kind="barter"),
                      event("death")], members=("a", "b"))
        self.assertEqual(raw["production_value_added"], 0)
        self.assertEqual(raw["production_possible_agent_ticks"], 120)

    def test_excludes_future_and_noncohort_output(self):
        actions = [event("harvest", resource="food", quantity=2)]
        actions += [{**actions[0], "tick": 60}, {**actions[0], "actor_id": "other"}]
        self.assertEqual(counts(actions)["production_value_added"], 4)

    def test_pooling_raw_counts_is_replication_invariant(self):
        raw = counts([event("mine", resource="ore", quantity=2)])
        doubled = {k: v * 2 if isinstance(v, (int, float)) else v for k, v in raw.items()}
        self.assertEqual(score_production_counts(raw)["score"], score_production_counts(doubled)["score"])

    def test_missing_unknown_or_nonfinite_production_is_rejected(self):
        for resource, quantity in (("unknown", 1), ("food", None), ("food", -1), ("food", float("nan"))):
            with self.assertRaises(ScoringEvidenceError):
                counts([event("gather", resource=resource, quantity=quantity)])
        with self.assertRaises(ScoringEvidenceError):
            counts([event("craft", recipe="tool", outputs={"tool": 999})])
        with self.assertRaises(ScoringEvidenceError):
            score_production_counts({})

    def test_latency_groups_retries_per_decision_without_idle_time(self):
        accepted = [{"tick": 1, "agent_id": "a", "duration_seconds": 3},
                    {"tick": 1, "agent_id": "b", "duration_seconds": 5}]
        retry = {"tick": 1, "agent_id": "a", "duration_seconds": 2, "committed": False}
        timing = summarize_decision_latency(accepted, [retry, *accepted])
        self.assertEqual(timing["decisions"], 2)
        self.assertEqual(timing["mean_seconds"], 5)
        self.assertEqual(timing["decision_seconds"], [5, 5])
        broken = copy.deepcopy(accepted)
        broken[1].pop("duration_seconds")
        self.assertFalse(summarize_decision_latency(broken)["complete"])
        self.assertIsNone(summarize_decision_latency(broken)["mean_seconds"])


if __name__ == "__main__":
    unittest.main()
