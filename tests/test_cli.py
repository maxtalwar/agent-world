from __future__ import annotations

import unittest

from agent_world.cli import _provider_context_parity


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


if __name__ == "__main__":
    unittest.main()
