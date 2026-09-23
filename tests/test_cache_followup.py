import unittest

from scripts.analyze_cache_followup import cache_class, refresh_projection, ttl_estimate


class CacheFollowupTests(unittest.TestCase):
    def test_missing_write_counts_are_unknown_not_zero(self):
        self.assertFalse(ttl_estimate([{"prompt_tokens": 100}], [10, 1, 12.5, 50])["available"])

    def test_ttl_delta_and_fixed_output(self):
        row = dict(prompt_tokens=100, cached_tokens=40, cache_write_tokens=50,
                   completion_tokens=20)
        result = ttl_estimate([row], [10, 1, 12.5, 50])
        self.assertAlmostEqual(result["saving_usd"], 50 * 7.5 / 1e6)
        self.assertEqual(result["five_minute"]["usd"]["output"],
                         result["conditional_one_hour"]["usd"]["output"])
        self.assertFalse(result["historical_ttl_verified"])

    def test_cache_classes_allow_rounding_but_not_short_prefix(self):
        self.assertEqual(cache_class(14336, 14504), "near_template")
        self.assertEqual(cache_class(9856, 13204), "partial")
        self.assertEqual(cache_class(0, 13204), "miss")

    def test_frequency_update_changes_only_cache_cost(self):
        prior = {"rates_per_million_input_cached_write_output": [10, 1, 12.5, 50],
                 "fork_decisions": {"cached_tokens": 100, "calls": 2},
                 "historical": {"calls": 1000, "usd": {"total": 20}},
                 "prompt_growth_adjusted_current_cli_projection": {"after_usd": 10}}
        result = refresh_projection(prior, [100, 100])
        self.assertAlmostEqual(result["projected_fork_usd"], 9.55)


if __name__ == "__main__":
    unittest.main()
