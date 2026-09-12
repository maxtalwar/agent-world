import unittest
from agent_world.usage import summarize_usd_cost, _usd_rate_model

class PricingTests(unittest.TestCase):
    def test_current_native_catalog_is_priced_or_explicitly_unpublished(self):
        for model in ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5",
                      "claude-fable-5-1", "claude-opus-5[1m]", "claude-opus-4-5-20251101",
                      "claude-sonnet-5", "claude-haiku-4-5-20251001", "grok-4.5", "grok-4.6"]:
            self.assertIsNotNone(_usd_rate_model(model), model)
        self.assertIsNone(_usd_rate_model("gpt-5.3-codex-spark"))

    def test_opus45_cost_with_disjoint_cache_categories(self):
        cost = summarize_usd_cost([{"model": "claude-opus-4-5", "prompt_tokens": 3000000,
                 "cached_tokens": 1000000, "cache_write_tokens": 1000000, "completion_tokens": 1000000}])
        self.assertTrue(cost["available"])
        self.assertEqual(cost["cost_usd"]["total"], 36.75)

    def test_fable51_has_own_cache_price(self):
        cost = summarize_usd_cost([{"model": "claude-fable-5-1", "prompt_tokens": 1000000,
                                  "cached_tokens": 1000000}])
        self.assertEqual(cost["cost_usd"]["total"], .25)
