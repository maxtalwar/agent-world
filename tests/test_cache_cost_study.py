import unittest

from scripts.analyze_cache_cost_study import cost, historical_projection


class CacheCostStudyTests(unittest.TestCase):
    def test_subsets_and_reasoning_not_double_billed(self):
        row = dict(prompt_tokens=100, cached_tokens=40, cache_write_tokens=10,
                   completion_tokens=20, reasoning_tokens=15)
        self.assertAlmostEqual(cost(row, [10, 1, 12.5, 50])["total"], .001665)
        with self.assertRaises(ValueError):
            cost(dict(row, cached_tokens=101), [10, 1, 12.5, 50])

    def test_projection_includes_template_once_and_bounds_cache(self):
        row = dict(prompt_tokens=100, cached_tokens=0, completion_tokens=20)
        fork = dict(row, prompt_tokens=110, cached_tokens=80)
        template = dict(prompt_tokens=50, cached_tokens=0, completion_tokens=1)
        rates = [10, 1, 12.5, 50]
        result = historical_projection([row] * 2, [row], [fork], [template], rates)
        self.assertAlmostEqual(result["after_usd"], 2 * .00138 + .00055)
        capped = historical_projection([row], [row], [fork], [], rates, 999)
        self.assertAlmostEqual(capped["after_usd"], .00111)


if __name__ == "__main__":
    unittest.main()
