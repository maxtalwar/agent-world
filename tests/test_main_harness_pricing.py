import unittest
from agent_world.usage import summarize_usd_cost, _usd_rate_model

class PricingTests(unittest.TestCase):
    def test_current_native_catalog_is_priced_or_explicitly_unpublished(self):
        for model in ["gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5",
                      "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5[1m]", "claude-opus-4-5-20251101",
                      "claude-sonnet-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-haiku-4-5-20251001", "grok-4.5", "grok-4.6"]:
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

    def test_opus55_has_own_price_not_opus5_prefix(self):
        self.assertEqual(_usd_rate_model("claude-opus-5-5"), "claude-opus-5-5")
        cost = summarize_usd_cost([{"model": "claude-opus-5-5", "prompt_tokens": 3000000,
                 "cached_tokens": 1000000, "cache_write_tokens": 1000000, "completion_tokens": 1000000}])
        self.assertEqual(cost["cost_usd"]["total"], 29.2)

    def test_gpt61_sol_standard_short_context_price(self):
        self.assertEqual(_usd_rate_model("gpt-6.1-sol"), "gpt-6.1-sol")
        cost = summarize_usd_cost([{"model": "gpt-6.1-sol", "prompt_tokens": 2000000,
                 "cached_tokens": 1000000, "completion_tokens": 1000000}])
        self.assertEqual(cost["cost_usd"]["total"], 12.1)

    def test_sonnet55_and_haiku55_have_own_prices(self):
        usage = {"prompt_tokens": 3000000, "cached_tokens": 1000000,
                 "cache_write_tokens": 1000000, "completion_tokens": 1000000}
        self.assertEqual(_usd_rate_model("claude-sonnet-5-5"), "claude-sonnet-5-5")
        self.assertEqual(summarize_usd_cost([{"model": "claude-sonnet-5-5", **usage}])["cost_usd"]["total"], 14.6)
        self.assertEqual(summarize_usd_cost([{"model": "claude-haiku-5-5", **usage}])["cost_usd"]["total"], .735)

    def test_gpt61_terra_standard_short_context_price(self):
        self.assertEqual(_usd_rate_model("gpt-6.1-terra"), "gpt-6.1-terra")
        cost = summarize_usd_cost([{"model": "gpt-6.1-terra", "prompt_tokens": 2000000,
                 "cached_tokens": 1000000, "completion_tokens": 1000000}])
        self.assertEqual(cost["cost_usd"]["total"], 6.05)
