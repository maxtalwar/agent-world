import copy
import json
from pathlib import Path
import tempfile
import unittest
from agent_world.astra_pricing import historical_cost
from agent_world.usage import summarize_usd_cost


class AstraPricingTests(unittest.TestCase):
    def test_standard_price_counts_reasoning_only_once(self):
        result = summarize_usd_cost([dict(model="gpt-6-astra", prompt_tokens=200000,
            cached_tokens=100000, cache_write_tokens=20000, completion_tokens=10000, reasoning_tokens=8000)])
        self.assertTrue(result["available"])
        self.assertAlmostEqual(result["cost_usd"]["total"], 1.65)

    def test_long_context_surcharge_boundary(self):
        for prompt, expected in [(272000, 3.22), (272001, 6.19002)]:
            result = summarize_usd_cost([dict(model="gpt-6-astra", prompt_tokens=prompt, completion_tokens=10000)])
            self.assertAlmostEqual(result["cost_usd"]["total"], expected)

    def test_historical_retries_reconcile_and_reports_stay_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = dict(model="gpt-6-astra", prompt_tokens=200000, cached_tokens=100000, completion_tokens=10000)
            summary = dict(available=False, unknown_models=["gpt-6-astra"], models={}, calls=2,
                uncached_input_tokens=200000, cached_input_tokens=200000, cache_write_tokens=0, output_tokens=20000)
            original = copy.deepcopy(summary)
            report = root / "run-report.json"
            report.write_text(json.dumps(summary))
            (root / "run-usage.jsonl").write_text(json.dumps(row))
            self.assertIsNone(historical_cost(summary, "gpt-6-astra", report))
            (root / "run-usage-partial-tick-0.jsonl").write_text(json.dumps(row))
            self.assertEqual(historical_cost(summary, "gpt-6-astra", report), 3.2)
            self.assertEqual(summary, original)
            self.assertEqual(json.loads(report.read_text()), original)
            self.assertIsNone(historical_cost({**summary, "available": True}, "gpt-6-astra", report))
            self.assertIsNone(historical_cost(summary, "gpt-6-other", report))


if __name__ == "__main__":
    unittest.main()
