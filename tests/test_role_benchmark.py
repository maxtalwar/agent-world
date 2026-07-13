from __future__ import annotations

import unittest

from agent_world.role_benchmark import run_role_viability_benchmark


class RoleBenchmarkTests(unittest.TestCase):
    def test_benchmark_covers_each_specialist_for_every_seed(self) -> None:
        result = run_role_viability_benchmark([1, 2], ticks=3)

        self.assertEqual(
            set(result["roles"]),
            {"farmer", "forester", "miner", "fisher", "artisan"},
        )
        self.assertTrue(all(role["runs"] == 2 for role in result["roles"].values()))
        self.assertTrue(all(len(role["records"]) == 2 for role in result["roles"].values()))

    def test_benchmark_rejects_empty_seeds(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one seed"):
            run_role_viability_benchmark([], ticks=3)


if __name__ == "__main__":
    unittest.main()
