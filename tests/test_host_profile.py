from __future__ import annotations

import json
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout

from agent_world.cli import main
from agent_world.host_profile import (
    GIB,
    default_host_profile_path,
    load_host_profile,
    recommend_worker_limits,
    resolved_worker_recommendations,
    write_host_profile,
)


class HostProfileTests(unittest.TestCase):
    def test_desktop_estimate_reproduces_measured_worker_defaults(self) -> None:
        workers = recommend_worker_limits(
            {"logical_cpus": 12, "total_memory_bytes": 31 * GIB}
        )

        self.assertEqual(workers["global"], 40)
        self.assertEqual(workers["providers"]["codex_cli"], 40)
        self.assertEqual(workers["providers"]["claude_cli"], 20)
        self.assertEqual(workers["providers"]["grok_cli"], 20)
        self.assertEqual(workers["providers"]["zcode_cli"], 20)
        self.assertEqual(workers["providers"]["openrouter"], 4)

    def test_memory_can_bound_a_many_core_host(self) -> None:
        workers = recommend_worker_limits(
            {"logical_cpus": 64, "total_memory_bytes": 3 * GIB}
        )

        self.assertLess(workers["global"], workers["estimate"]["cpu_ceiling"])
        self.assertEqual(workers["global"], workers["estimate"]["memory_ceiling"])

    def test_profile_round_trip_and_environment_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "host.json"
            profile = {
                "schema_version": 1,
                "workers": {
                    "global": 12,
                    "providers": {"codex_cli": 10, "claude_cli": 6},
                },
            }
            with patch.dict(os.environ, {"AGENT_WORLD_HOST_PROFILE": str(path)}):
                self.assertEqual(default_host_profile_path(), path)
                write_host_profile(profile)
                loaded = load_host_profile()
                global_workers, providers = resolved_worker_recommendations(loaded)

            self.assertEqual(global_workers, 12)
            self.assertEqual(providers["codex_cli"], 10)
            self.assertEqual(providers["claude_cli"], 6)
            self.assertEqual(providers["grok_cli"], 12)

    def test_setup_command_writes_reusable_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "host.json"

            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                main(["setup", "--write-profile", "--profile", str(path), "--json"])

            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(value["schema_version"], 1)
            self.assertGreaterEqual(value["workers"]["global"], 1)
            self.assertIn("codex_cli", value["workers"]["providers"])

    def test_host_profile_defaults_preserve_current_protocol_and_explicit_limits(self) -> None:
        from argparse import Namespace
        from agent_world.cli import _apply_benchmark_protocol, _resolve_provider_max_workers
        from agent_world.benchmarks import BENCHMARK_PROTOCOL_ID
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "host.json"
            profile = {"schema_version": 1, "workers": {"global": 8, "providers": {"codex_cli": 6}}}
            with patch.dict(os.environ, {"AGENT_WORLD_HOST_PROFILE": str(path)}):
                write_host_profile(profile)
                args = Namespace(benchmark_protocol=BENCHMARK_PROTOCOL_ID, population=None,
                                 brain="codex", sequential_decisions=False, seed=11)
                _apply_benchmark_protocol(args)
                self.assertEqual(args.reasoning_effort, "low")
                self.assertEqual(args.max_workers, 6)
                self.assertEqual(_resolve_provider_max_workers(Namespace(codex_max_workers=3), 8)["codex_cli"], 3)


if __name__ == "__main__":
    unittest.main()
