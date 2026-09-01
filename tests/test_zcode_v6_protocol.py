from argparse import Namespace
import unittest

from agent_world.benchmarks import BENCHMARK_PROTOCOL_ID, BENCHMARK_SUITE_ID
from agent_world.cli import _apply_benchmark_protocol


class ZCodeV6ProtocolTests(unittest.TestCase):
    def test_zcode_uses_v6_world_four_workers_and_native_max(self) -> None:
        args = Namespace(
            benchmark_protocol=BENCHMARK_PROTOCOL_ID,
            population=None,
            brain="zcode",
            sequential_decisions=False,
            seed=11,
        )

        _apply_benchmark_protocol(args)

        self.assertEqual(BENCHMARK_PROTOCOL_ID, "participant-v6")
        self.assertEqual(BENCHMARK_SUITE_ID, "agent-world-participant-v6")
        self.assertEqual(args.preset, "frontier-generalists")
        self.assertEqual(args.world_variant, "frontier")
        self.assertEqual(args.reasoning_effort, "max")
        self.assertEqual(args.max_workers, 4)
        self.assertEqual(args.zcode_max_workers, 4)
        self.assertEqual(args.connector_profile, "stateless-v3")


if __name__ == "__main__":
    unittest.main()
