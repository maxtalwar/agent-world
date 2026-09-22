from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_world.brain_boundary import CODEX_SHARED_PREFIX_MODE
from agent_world.brain_factory import BrainSpec
from agent_world.brain_runtime import BrainRuntime
from agent_world.codex_brain import CodexBrain, _codex_subtract_inherited_usage


def completed(session, *, seed=False, usage=None):
    response = {"intent": "ready" if seed else "wait", "actions": [] if seed else [
        {"type": "wait", "arguments_json": "{}"}], "messages": [], "memory_updates": []}
    events = [
        {"type": "thread.started", "thread_id": session},
        {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps(response)}},
        {"type": "turn.completed", "usage": usage or {
            "input_tokens": 100 if seed else 300, "cached_input_tokens": 50 if seed else 200,
            "output_tokens": 10 if seed else 30}},
    ]
    return subprocess.CompletedProcess([], 0, "\n".join(map(json.dumps, events)), "")


class CodexCacheTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.template_path = Path(self.directory.name) / "template.jsonl"
        self.template_path.write_text("static template")
        for target, value in [
            ("_codex_version_text", "codex-cli 0.156.0"),
            ("_codex_version", (0, 156, 0)),
            ("_codex_template_path", self.template_path),
        ]:
            patcher = patch("agent_world.codex_brain." + target, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def brain(self, runtime=None):
        return CodexBrain(executable="codex-test", runtime=runtime,
                          connector_profile="connector-v3", conversation_mode=CODEX_SHARED_PREFIX_MODE)

    def test_shared_template_never_inherits_sibling_observations_and_bills_once(self):
        runtime = BrainRuntime()
        first, second = self.brain(runtime), self.brain(runtime)
        with patch.object(CodexBrain, "_run_command", side_effect=[
            completed("template", seed=True), completed("fork-one"), completed("fork-two")
        ]) as run:
            one = first.decide({"tick": 1, "self": {"id": "private-one"}})
            two = second.decide({"tick": 2, "self": {"id": "private-two"}})
        self.assertEqual(one.actions, [{"type": "wait"}])
        self.assertEqual(two.actions, [{"type": "wait"}])
        self.assertNotIn("private-one", run.call_args_list[0].args[0])
        self.assertNotIn("private-two", run.call_args_list[0].args[0])
        self.assertTrue(run.call_args_list[0].kwargs["persist_template"])
        self.assertEqual(run.call_args_list[1].kwargs["fork_session_id"], "template")
        self.assertEqual(run.call_args_list[2].kwargs["fork_session_id"], "template")
        self.assertNotIn("private-one", run.call_args_list[2].args[0])
        rows = runtime.usage_records()
        self.assertEqual([r["prompt_tokens"] for r in rows], [100, 200, 200])
        self.assertEqual([r["cached_tokens"] for r in rows], [50, 150, 150])
        self.assertEqual([r["completion_tokens"] for r in rows], [10, 20, 20])
        self.assertEqual(rows[0]["usage_kind"], "cache_template")
        self.assertIsNone(rows[0]["agent_id"])
        self.assertIsNone(first.export_checkpoint_state()["provider_session_id"])
        self.assertIsNone(second.export_checkpoint_state()["provider_session_id"])

    def test_modified_template_is_rejected_before_another_request(self):
        brain = self.brain()
        with patch.object(brain, "_run_command", side_effect=[
            completed("template", seed=True), completed("fork")
        ]) as run:
            brain.decide({"tick": 1, "self": {"id": "one"}})
            self.template_path.write_text("modified history")
            decision = brain.decide({"tick": 2, "self": {"id": "one"}})
        self.assertEqual(run.call_count, 2)
        self.assertIn("template changed", decision.intent)

    def test_templates_are_scoped_to_a_run(self):
        with patch.object(CodexBrain, "_run_command", side_effect=[
            completed("template", seed=True), completed("fork"),
            completed("template", seed=True), completed("fork"),
        ]) as run:
            self.brain().decide({"self": {"id": "one"}})
            self.brain().decide({"self": {"id": "two"}})
        self.assertEqual(sum(call.kwargs.get("persist_template", False) for call in run.call_args_list), 2)

    def test_invalid_initialization_is_billed_but_not_used(self):
        brain = self.brain()
        with patch.object(brain, "_run_command", return_value=completed("not-ready")) as run:
            decision = brain.decide({"self": {"id": "one"}})
        self.assertEqual(run.call_count, 1)
        self.assertIn("initialization response", decision.intent)
        self.assertEqual(len(brain.runtime.usage_records()), 1)

    def test_cumulative_usage_cannot_decrease(self):
        with self.assertRaisesRegex(ValueError, "cumulative usage"):
            _codex_subtract_inherited_usage(completed("fork"), {"input_tokens": 301})

    def test_failed_template_usage_is_not_billed_twice(self):
        brain = self.brain()
        failed = completed("template", seed=True)
        failed.returncode = 1
        failed.stderr = "initialization failed"
        with patch.object(brain, "_run_command", return_value=failed) as run:
            brain.decide({"tick": 0, "self": {"id": "one"}})
        self.assertEqual(run.call_count, 1)
        self.assertEqual(sum(row["prompt_tokens"] for row in brain.runtime.usage_records()), 100)

    def test_native_command_uses_ephemeral_fork_and_read_only_sandbox(self):
        brain = self.brain()
        command = brain._command(brain._stable_schema_path, fork_session_id="template")
        self.assertEqual(command[1:4], ["exec", "fork", "--ephemeral"])
        self.assertIn('sandbox_mode="read-only"', command)
        self.assertNotIn("--sandbox", command)
        self.assertEqual(command[-2:], ["template", "-"])
        seed_command = brain._command(brain._stable_schema_path, persist_template=True)
        self.assertNotIn("--ephemeral", seed_command)

    def test_requires_released_cache_affinity_support(self):
        with patch("agent_world.codex_brain._codex_version", return_value=(0, 154, 0)):
            with self.assertRaisesRegex(ValueError, "0.156.0"):
                self.brain()

    def test_mode_is_codex_specific_and_explicit(self):
        for provider, profile in [("claude", "connector-v3"), ("codex", "connector-v1")]:
            with self.assertRaisesRegex(ValueError, "requires codex"):
                BrainSpec.resolve(provider, connector_profile=profile, conversation_mode=CODEX_SHARED_PREFIX_MODE)
        spec = BrainSpec.resolve("codex", connector_profile="connector-v3", conversation_mode=CODEX_SHARED_PREFIX_MODE)
        self.assertEqual(spec.conversation_mode, CODEX_SHARED_PREFIX_MODE)


if __name__ == "__main__":
    unittest.main()
