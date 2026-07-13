from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from agent_world.brain_factory import PopulationSpec
from agent_world.cli import _population_with_manifest_assignments, _provider_context_parity


class CliTelemetryTests(unittest.TestCase):
    def test_provider_context_parity_compares_provider_neutral_fingerprints(self) -> None:
        records = [
            {
                "provider": "claude_cli",
                "game_context_format": "static_context_v2+compact_dynamic_v2",
                "game_static_context_sha256": "same",
            },
            {
                "provider": "codex_cli",
                "game_context_format": "static_context_v2+compact_dynamic_v2",
                "game_static_context_sha256": "same",
            },
        ]

        parity = _provider_context_parity(records)

        self.assertTrue(parity["same_static_game_context"])
        self.assertTrue(parity["same_context_format"])

    def test_provider_context_parity_detects_drift(self) -> None:
        records = [
            {"provider": "claude_cli", "game_context_format": "v2", "game_static_context_sha256": "a"},
            {"provider": "codex_cli", "game_context_format": "v2", "game_static_context_sha256": "b"},
        ]

        self.assertFalse(_provider_context_parity(records)["same_static_game_context"])

    def test_population_can_reuse_exact_compatible_manifest_assignments(self) -> None:
        requested = PopulationSpec.parse_many(["1@claude-sonnet-5", "1@gpt-5.6-luna"])
        source = {
            "population": {
                **requested.to_dict(["agent-1", "agent-2"]),
                "assignment_strategy": "stratified",
                "assignment_seed": 101,
                "assignments": {"agent-1": "cohort-2", "agent-2": "cohort-1"},
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "manifest.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            replayed = _population_with_manifest_assignments(
                requested, path, {"agent-1", "agent-2"}
            )

        self.assertEqual(replayed.assignment_seed, 101)
        self.assertEqual(
            dict(replayed.assigned_groups),
            {"agent-1": "cohort-2", "agent-2": "cohort-1"},
        )


if __name__ == "__main__":
    unittest.main()
