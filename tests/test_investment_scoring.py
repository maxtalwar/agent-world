import unittest

from agent_world.benchmarks import BENCHMARK_ACCOUNTING_VALUES, INVESTMENT_ACCOUNTING_VALUES
from agent_world.production_scoring import derive_production_counts


class InvestmentScoringTests(unittest.TestCase):
    def craft(self, recipe, outputs):
        return {"type": "craft", "actor_id": "agent-1", "tick": 3,
                "data": {"recipe": recipe, "outputs": outputs}}

    def test_investment_crafts_score_in_investment_worlds(self):
        counts = derive_production_counts(
            [self.craft("preserved_food", {"preserved_food": 2})], member_ids=["agent-1"], target_ticks=10,
            economy_mode="organic", accounting_values=INVESTMENT_ACCOUNTING_VALUES, investment_mode="invest-v1",
        )
        # Preserving food converts goods without adding value: 2 food + 1 wood in, 2 preserved food out.
        self.assertEqual((counts["production_output_value"], counts["production_intermediate_input_value"]), (7.0, 7.0))

    def test_investment_crafts_are_rejected_in_standard_worlds(self):
        from agent_world.outcome_scoring import ScoringEvidenceError
        with self.assertRaises(ScoringEvidenceError):
            derive_production_counts(
                [self.craft("preserved_food", {"preserved_food": 2})], member_ids=["agent-1"], target_ticks=10,
                economy_mode="organic", accounting_values=BENCHMARK_ACCOUNTING_VALUES,
            )

    def test_published_accounting_values_are_unchanged(self):
        self.assertFalse({"preserved_food", "cloth", "clothing"} & set(BENCHMARK_ACCOUNTING_VALUES))
        self.assertEqual(INVESTMENT_ACCOUNTING_VALUES["clothing"], 14.0)


if __name__ == "__main__":
    unittest.main()
