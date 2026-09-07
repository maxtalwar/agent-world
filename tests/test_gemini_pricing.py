import unittest
from agent_world.gemini_pricing import historical_cost
from agent_world.leaderboard import model_label
from agent_world.usage import summarize_usd_cost

class GeminiPricingTests(unittest.TestCase):
    def test_names_and_effort_pricing(self):
        for version in ("3.6", "3.7"):
            model = f"gemini-{version}-flash-medium"
            self.assertEqual(model_label(model), f"Gemini {version} Flash")
            estimate = summarize_usd_cost([dict(model=model, prompt_tokens=1000000,
                cached_tokens=400000, completion_tokens=200000, reasoning_tokens=150000)])
            self.assertTrue(estimate["available"])
            self.assertAlmostEqual(estimate["cost_usd"]["total"], 1.23)
    def test_historical_fallback_is_limited_and_nonmutating(self):
        summary = dict(available=False, unknown_models=["gemini-3.6-flash-medium"], models={},
            uncached_input_tokens=600000, cached_input_tokens=400000, cache_write_tokens=0,
            output_tokens=200000, reasoning_output_tokens=150000)
        self.assertEqual(historical_cost(summary, "gemini-3.6-flash-medium"), 1.23)
        self.assertFalse(summary["available"])
        self.assertIsNone(historical_cost(summary, "gemini-3.7-flash-medium"))
        self.assertIsNone(historical_cost({**summary, "available": True}, "gemini-3.6-flash-medium"))
