import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agent_world.leaderboard_supervisor import resolve_supervisor_binary
from agent_world.leaderboard_launch import LaunchService


class RuntimeResolutionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.install = self.root / "OpenAI/Codex/bin"
        self.old = self.install / "retired/codex.exe"

    def runtime(self, version, timestamp):
        path = self.install / version / "codex.exe"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        os.utime(path, (timestamp, timestamp))
        return path

    def test_preserves_explicit_existing_runtime(self):
        old = self.runtime("retired", 1)
        self.runtime("replacement", 2)
        self.assertEqual(resolve_supervisor_binary(str(old)), str(old))

    def test_recovers_latest_runtime_after_update(self):
        self.runtime("zz-older", 1)
        current = self.runtime("aa-current", 2)
        self.assertEqual(resolve_supervisor_binary(str(self.old)), str(current))

    def test_missing_install_stays_blocked(self):
        self.assertIsNone(resolve_supervisor_binary(str(self.old)))
        self.assertIsNone(resolve_supervisor_binary(None))

    def test_never_substitutes_unrelated_configuration(self):
        self.runtime("current", 2)
        self.assertIsNone(resolve_supervisor_binary(str(self.root / "custom/codex.exe")))
        self.assertIsNone(resolve_supervisor_binary(str(self.install / "retired/other.exe")))

    def test_catalog_recovers_without_rewriting_settings(self):
        current = self.runtime("current", 2)
        service = LaunchService(self.root, settings={
            "launch_enabled": True, "monitor_thread_id": "monitor",
            "supervisor_binary": str(self.old)})
        with patch.object(service, "sources", return_value={"recipe": {}}), \
             patch("agent_world.leaderboard_launch.shutil.which", return_value="tmux"), \
             patch("agent_world.leaderboard_launch.AstraClient") as client, \
             patch("agent_world.leaderboard_launch.model_catalog", return_value=([], [])), \
             patch("agent_world.leaderboard_launch.saved_catalog", side_effect=lambda path, discover: discover()):
            self.assertIsNone(service.catalog()["blocker"])
            client.assert_called_once_with(str(current), self.root)
            client.return_value.verify.assert_called_once()
        self.assertEqual(service.settings["supervisor_binary"], str(self.old))


if __name__ == "__main__":
    unittest.main()
