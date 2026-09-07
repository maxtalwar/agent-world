from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agent_world.antigravity_brain import AntigravityBrain, parse_antigravity_result
from agent_world.brain_factory import BrainSpec, PopulationSpec
from agent_world.cli import build_parser
from agent_world.headless_brain import BoundaryError
from agent_world.managed_runs import load_run_config
from agent_world.muse_brain import MuseBrain, muse_settings, parse_muse_result, parse_muse_trace

DECISION = {"intent": "observe", "actions": [{"type": "wait"}], "messages": [], "memory_updates": []}
SID = "11111111-1111-4111-8111-111111111111"
RID = "root-run"


def agy_result(**changes):
    result = {"status": "SUCCESS", "structured_output": DECISION, "conversation_id": SID,
              "usage": {"input_tokens": 100, "output_tokens": 20, "cache_read_tokens": 50, "thinking_tokens": 8}}
    result.update(changes)
    return json.dumps({"event": "result", "result": result})


def muse_row(kind, payload):
    return {"schema_version": 1, "stream": {"kind": "session", "id": SID},
            "payload_type": kind, "payload": payload}


def muse_result(text=None, **changes):
    final = {"run_stream": {"kind": "run", "id": RID}, "terminal": "completed",
             "text": json.dumps(DECISION) if text is None else text}
    final.update(changes)
    return json.dumps(muse_row("run.terminal." + final["terminal"], final))


def trace_row(event, run=RID, source="completion"):
    return json.dumps({"payload_type": "runtime.session", "payload": {
        "run_id": run, "source_run_record_id": source, "event": event}})


def muse_trace():
    return trace_row({"kind": "model_completed", "model": "muse-spark-1.3",
                      "usage": {"input_tokens": 100, "output_tokens": 20,
                                "cache_read_tokens": 50, "reasoning_tokens": 8}})


class NativeEnvelopeTests(unittest.TestCase):
    def test_antigravity_usage_and_unknowns(self):
        result = parse_antigravity_result(agy_result())
        self.assertEqual(result["usage"]["prompt_tokens"], 100)
        self.assertEqual(result["usage"]["cached_tokens"], 50)
        self.assertIsNone(result["response_model"])
        self.assertIsNone(parse_antigravity_result(agy_result(usage={}))["usage"]["prompt_tokens"])

    def test_antigravity_schema_finish_requires_native_evidence(self):
        def varint(n):
            out = bytearray()
            while n > 127:
                out.append((n & 127) | 128)
                n >>= 7
            return bytes(out) + bytes([n])
        def field(n, value):
            return varint(n * 8 + 2) + varint(len(value)) + value
        def payload(name):
            return b"\x08\x84\x01" + field(5, field(4, field(2, name)))
        step = {"event": "step_update", "step_update": {
            "conversation_id": SID, "step_index": 2, "step_type": "tool"}}
        stream = json.dumps(step) + "\n" + agy_result()
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            self.assertEqual(parse_antigravity_result(stream, trace_root=path)["tool_calls"], 1)
            with sqlite3.connect(path / (SID + ".db")) as conn:
                conn.execute("CREATE TABLE steps(idx INTEGER, step_type INTEGER, has_subtrajectory INTEGER, step_format INTEGER, step_payload BLOB)")
                conn.execute("INSERT INTO steps VALUES(2,132,0,0,?)", (payload(b"finish"),))
            parsed = parse_antigravity_result(stream, trace_root=path)
            self.assertEqual(parsed["tool_calls"], 0)
            self.assertEqual(len(parsed["trace_sha256"]), 64)
            for name, sub, blob in [(b"run_command", 0, None), (b"invoke_subagent", 0, None),
                                    (b"finish", 1, None), (b"finish", 0, b"broken")]:
                with self.subTest(name=name, sub=sub, blob=blob):
                    with sqlite3.connect(path / (SID + ".db")) as conn:
                        conn.execute("UPDATE steps SET has_subtrajectory=?,step_payload=?", (sub, blob or payload(name)))
                    self.assertEqual(parse_antigravity_result(stream, trace_root=path)["tool_calls"], 1)
            step["step_update"]["conversation_id"] = "foreign"
            self.assertEqual(parse_antigravity_result(json.dumps(step) + "\n" + agy_result(), trace_root=path)["tool_calls"], 1)

    def test_antigravity_requires_single_known_terminal(self):
        for text in ("", "[]", agy_result() + "\n" + agy_result(), agy_result(status="NEW_STATUS")):
            with self.subTest(text=text), self.assertRaises((ValueError, BoundaryError)):
                parse_antigravity_result(text)

    def test_antigravity_documented_non_success_statuses(self):
        for status in ("CANCELED", "INTERRUPTED", "INVALID", "WAITING", "RUNNING"):
            with self.subTest(status=status):
                result = parse_antigravity_result(agy_result(status=status))
                self.assertEqual(result["error"], status)

    def test_muse_configured_model_is_not_observed(self):
        configured = muse_row("run.model.configured", {"model": "a-configured-model"})
        result = parse_muse_result(json.dumps(configured) + "\n" + muse_result())
        self.assertNotIn("response_model", result)
        self.assertEqual(result["usage"], {})

    def test_muse_rejects_mixed_session_and_duplicate_terminal(self):
        other = json.loads(muse_result())
        other["stream"]["id"] = "other"
        for text in (muse_result() + "\n" + json.dumps(other), muse_result() + "\n" + muse_result()):
            with self.assertRaises(BoundaryError):
                parse_muse_result(text)

    def test_muse_rejects_mixed_run(self):
        other = muse_row("session.run.linked", {"run_stream": {"id": "other"}})
        with self.assertRaises(BoundaryError):
            parse_muse_result(json.dumps(other) + "\n" + muse_result())

    def test_muse_trace_deduplicates_and_ignores_mirrored_and_foreign_usage(self):
        trace = "\n".join([muse_trace(), muse_trace(),
                            trace_row({"kind": "goal_usage_attribution", "usage": {"input_tokens": 999}}, source="mirror"),
                            trace_row({"kind": "model_completed", "usage": {"input_tokens": 999}}, run="other")])
        result = parse_muse_trace(trace, RID)
        self.assertEqual(result["usage"]["prompt_tokens"], 100)
        self.assertEqual(result["usage"]["completion_tokens"], 20)
        self.assertEqual(result["native_configured_model"], "muse-spark-1.3")

    def test_muse_rejects_extra_model_completion(self):
        extra = json.loads(muse_trace())
        extra["payload"]["source_run_record_id"] = "extra"
        with self.assertRaises(BoundaryError):
            parse_muse_trace(muse_trace() + "\n" + json.dumps(extra), RID)

    def test_muse_trace_cannot_erase_reminder_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "2026/09/04" / SID / "session.jsonl"
            path.parent.mkdir(parents=True)
            path.write_text(muse_trace())
            reminder = muse_row("task.lifecycle.proposed", {"event": {"task_kind": "reminder.agent.plugin"}})
            brain = MuseBrain(executable="/fixture/muse")
            result = brain._parse(json.dumps(reminder) + "\n" + muse_result(), {"data_root": root})
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual(len(result["trace_sha256"]), 64)


class NativeDecisionTests(unittest.TestCase):
    def decide(self, stdout, code=0, stderr=""):
        brain = AntigravityBrain(executable="/fixture/agy")
        with patch.object(brain, "_execute", return_value=(subprocess.CompletedProcess([], code, stdout, stderr), {})):
            decision = brain.decide({"tick": 1, "self": {"id": "a"}})
        return brain, decision

    def test_valid_decision_and_usage(self):
        brain, decision = self.decide(agy_result())
        self.assertIsNone(decision.failure_kind)
        row = brain.runtime.usage_records()[0]
        self.assertEqual(row["reasoning_tokens"], 8)
        self.assertIsNone(row["cost"])
        self.assertEqual(row["model_provenance"], "requested_only")
        self.assertEqual(row["reasoning_effort_provenance"], "requested_only")

    def test_invalid_model_json_does_not_become_provider_quota(self):
        brain, decision = self.decide(agy_result(structured_output=None, response="quota exhausted"))
        self.assertEqual(decision.failure_kind, "model_output")
        self.assertIsNone(brain.runtime.blocking_failure())

    def test_model_mismatch_and_tool_attempt_are_harness_failures(self):
        cases = [agy_result(model="other-model"),
                 json.dumps({"event": "step_update", "step_update": {"step_type": "tool"}}) + "\n" + agy_result()]
        for stdout in cases:
            with self.subTest(stdout=stdout):
                brain, decision = self.decide(stdout)
                self.assertEqual(decision.failure_kind, "harness")

    def test_quota_failure_blocks_subsequent_calls(self):
        brain, decision = self.decide("", 1, "resource_exhausted: quota exceeded")
        self.assertEqual(decision.failure_kind, "quota")
        with patch.object(brain, "_execute") as execute:
            self.assertEqual(brain.decide({}).failure_kind, "quota")
            execute.assert_not_called()

    def test_antigravity_individual_quota_reached_blocks_calls(self):
        from agent_world.provider_limits import quota_reset_at
        from datetime import datetime, timezone, timedelta
        detail = "Individual quota reached. Please upgrade your subscription to increase your limits. Resets in 4h15m36s."
        brain, decision = self.decide(agy_result(status="ERROR", error=detail))
        self.assertEqual(decision.failure_kind, "quota")
        now = datetime(2026, 9, 6, 21, 5, tzinfo=timezone.utc)
        self.assertEqual(quota_reset_at(detail, now=now), now + timedelta(hours=4, minutes=15, seconds=36))
        with patch.object(brain, "_execute") as execute:
            self.assertEqual(brain.decide({}).failure_kind, "quota")
            execute.assert_not_called()

    def test_auth_failure_blocks(self):
        brain, decision = self.decide("", 1, "Please sign in")
        self.assertEqual(decision.failure_kind, "authentication")
        self.assertIsNotNone(brain.runtime.blocking_failure())

    def test_timeout_is_provider_failure(self):
        brain = AntigravityBrain(executable="/fixture/agy")
        with patch.object(brain, "_execute", side_effect=subprocess.TimeoutExpired("agy", 1)):
            self.assertEqual(brain.decide({}).failure_kind, "provider")

    def test_checkpoint_does_not_allow_model_change(self):
        brain = MuseBrain(executable="/fixture/muse")
        state = brain.export_checkpoint_state()
        state["model"] = "other"
        with self.assertRaises(ValueError):
            brain.restore_checkpoint_state(state)

    def test_environment_has_no_api_key_and_isolates_muse_state(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
            "META_API_KEY": "fixture", "OPENAI_API_KEY": "fixture", "MUSE_BASE_URL": "http://fixture"}):
            brain = MuseBrain(executable="/fixture/muse")
            env = brain._environment(root)
            self.assertNotIn("META_API_KEY", env)
            self.assertNotIn("MUSE_BASE_URL", env)
            self.assertEqual(env["XDG_DATA_HOME"], str(Path(root) / "data"))
            settings = json.loads((Path(root) / "config/muse/settings.json").read_text())
            self.assertEqual(settings, muse_settings())
            self.assertTrue(all(not v["enabled"] for v in settings["runtime_capabilities"].values()))

    def test_antigravity_preflight_requires_exact_model_and_effort(self):
        with patch("agent_world.antigravity_brain.Path.home", return_value=Path("/fixture")), patch(
            "agent_world.antigravity_brain.run_process", side_effect=[
                subprocess.CompletedProcess([], 0, "1.1.26", ""),
                subprocess.CompletedProcess([], 0, "gemini-3.7-flash-medium\tGemini\n", "")]):
            brain = AntigravityBrain(model="gemini-3.7-flash-medium", reasoning_effort="low", executable="/fixture/agy")
            self.assertIn("conflicts", brain.preflight())

    def test_antigravity_catalog_alone_is_not_readiness(self):
        for discovery, expected in (
            ("", False),
            ("Please sign in", False),
            ("Gemini Models\tWeekly Limit Remaining\t100%\t2026-09-12T00:00:00Z", True),
            ("Gemini Models\tWeekly Limit Remaining\t0%\t2026-09-12T00:00:00Z", True),
        ):
            with self.subTest(discovery=discovery), patch(
                "agent_world.antigravity_brain.Path.home", return_value=Path("/fixture")
            ), patch("agent_world.antigravity_brain.run_process", side_effect=[
                subprocess.CompletedProcess([], 0, "1.1.26", ""),
                subprocess.CompletedProcess([], 0, "gemini-3.7-flash-low Gemini", ""),
                subprocess.CompletedProcess([], 0, discovery, ""),
            ]):
                brain = AntigravityBrain(executable="/fixture/agy")
                self.assertEqual(brain.preflight() is None, expected)

    def test_ineligible_account_blocks_authentication(self):
        brain, decision = self.decide("", 1, "Your current account is not eligible for Antigravity")
        self.assertEqual(decision.failure_kind, "authentication")
        self.assertIsNotNone(brain.runtime.blocking_failure())

    def test_malformed_nested_event_is_a_harness_failure(self):
        brain, decision = self.decide(
            json.dumps({"event": "step_update", "step_update": None}) + "\n" + agy_result()
        )
        self.assertEqual(decision.failure_kind, "harness")

    def test_nonpositive_timeout_and_persistent_mode_rejected(self):
        for kwargs in ({"timeout_seconds": 0}, {"conversation_mode": "persistent-conversation-v1"},
                       {"connector_profile": "unknown"}):
            with self.assertRaises(ValueError):
                MuseBrain(executable="/fixture/muse", **kwargs)


class NativeRegistrationTests(unittest.TestCase):
    def test_population_inference_and_provider_scope(self):
        pop = PopulationSpec.parse_many(["1@gemini-3.7-flash-low", "1@muse-spark-1.3"])
        self.assertEqual([x.brain.provider for x in pop.groups], ["antigravity_cli", "muse_cli"])
        for group in pop.groups:
            self.assertTrue(group.brain.model_backed)
        self.assertEqual(BrainSpec.resolve("antigravity").model, "gemini-3.7-flash-low")

    def test_cli_provider_worker_flags(self):
        args = build_parser().parse_args(["run", "--brain", "muse", "--muse-max-workers", "2"])
        self.assertEqual(args.muse_max_workers, 2)

    def test_observer_config_accepts_native_models(self):
        from agent_world.observer import _parse_run_config
        for name in ("antigravity", "muse"):
            config = _parse_run_config({"brain": name})
            self.assertEqual(config.brain, name)
            self.assertIsNotNone(config.model)
            self.assertEqual(config.reasoning_effort, "low")

    def test_managed_configs_accept_native_providers(self):
        for brain, model in (("antigravity", "gemini-3.7-flash-low"), ("muse", "muse-spark-1.3")):
            config = {"schema_version": 1, "run_id": "native-fixture", "kind": "experiment",
                      "question": "Does the adapter work?", "model": {"brain": brain, "id": model, "reasoning_effort": "low"},
                      "runtime": {"ticks": 1, "agents": 1, "provider_max_workers": {brain: 1}}}
            with tempfile.TemporaryDirectory() as root:
                path = Path(root) / "run.json"
                path.write_text(json.dumps(config))
                self.assertEqual(load_run_config(path)["model"]["brain"], brain)


if __name__ == "__main__":
    unittest.main()
