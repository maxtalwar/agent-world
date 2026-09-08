import unittest
from agent_world.muse_pricing import historical_cost
from agent_world.usage import MODEL_USD_RATES_PER_MILLION

class MusePricingTests(unittest.TestCase):
    def test_backfill_separates_cached_input_and_inclusive_output(self):
        summary={"available":False,"unknown_models":["muse-spark-1.3"],"models":{},
                 "uncached_input_tokens":1000000,"cached_input_tokens":1000000,
                 "cache_write_tokens":0,"output_tokens":1000000,"reasoning_output_tokens":900000}
        self.assertEqual(historical_cost(summary,"muse-spark-1.3"),5.65)
        self.assertIsNone(historical_cost(summary,"muse-spark-1.2"))
        summary["available"]=True
        self.assertIsNone(historical_cost(summary,"muse-spark-1.3"))

    def test_new_runs_have_native_rate_mapping(self):
        self.assertEqual(float(MODEL_USD_RATES_PER_MILLION["muse-spark-1.3"]["output"]),4.25)
