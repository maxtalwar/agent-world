import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from agent_world.claude_usage import exhausted_reset, claude_quota_reset

class ClaudeUsageTests(unittest.TestCase):
    now = datetime(2026, 9, 10, 19, tzinfo=timezone.utc)
    def window(self, percent, hour, name=None):
        return {"kind": "weekly_scoped" if name else "weekly_all", "percent": percent,
                "resets_at": f"2026-09-10T{hour}:00:00+00:00",
                "scope": {"model": {"display_name": name}} if name else None}
    def resolve(self, windows):
        return exhausted_reset({"limits": windows}, "claude-fable-5-1", now=self.now)
    def test_model_weekly_not_unexhausted_session(self):
        self.assertEqual(self.resolve([self.window(46, 23), self.window(55, 21), self.window(100, 21, "Fable")]).hour, 21)
    def test_latest_applicable_exhausted_limit(self):
        self.assertEqual(self.resolve([self.window(100, 23), self.window(100, 21, "Fable")]).hour, 23)
    def test_other_model_does_not_block(self):
        self.assertIsNone(self.resolve([self.window(100, 23, "Sonnet")]))
    def test_missing_reset_is_unknown(self):
        w=self.window(100, 21, "Fable"); w["resets_at"]=None
        self.assertIsNone(self.resolve([w, self.window(100, 23)]))
    def test_expired_or_naive_is_unknown(self):
        self.assertIsNone(self.resolve([self.window(100, 18)]))
        w=self.window(100, 21); w["resets_at"]="2026-09-10T21:00:00"
        self.assertIsNone(self.resolve([w]))
    def test_unavailable_endpoint_is_unknown(self):
        with patch("agent_world.claude_usage.read_claude_usage", side_effect=OSError("offline")):
            self.assertIsNone(claude_quota_reset("claude-fable-5-1"))
    def test_unrecognized_response_is_unknown(self):
        self.assertIsNone(exhausted_reset({}, "claude-fable-5-1", now=self.now))

    def test_session_waits_for_native_reset_without_inference(self):
        from datetime import timedelta
        from agent_world.claude_brain import ClaudeBrain
        from agent_world.session import SimulationSession
        from agent_world.brain_runtime import BrainRuntime
        from types import SimpleNamespace
        from unittest.mock import Mock
        brain = object.__new__(ClaudeBrain)
        brain.model = "claude-fable-5-1"
        brain.decide = Mock(side_effect=AssertionError("must not infer"))
        session = object.__new__(SimulationSession)
        session.quota_wait_max_seconds = 43200
        session._quota_wait_used = session._quota_wait_total = 0
        session._quota_backoff_seconds = 300
        session.quota_wait_poll_max_seconds = 1800
        session.brains = {"agent-1": brain}
        session.engine = SimpleNamespace(state=SimpleNamespace(tick=12), log_event=Mock())
        session.target_ticks = 60
        session.runtime = BrainRuntime()
        session.flush = Mock()
        session._sleep_for_quota = Mock()
        reset = datetime.now(timezone.utc) + timedelta(hours=2)
        with patch("agent_world.claude_usage.claude_quota_reset", return_value=reset) as read:
            self.assertTrue(session._wait_for_quota_reset(["out of usage credits"]))
        read.assert_called_once_with("claude-fable-5-1")
        brain.decide.assert_not_called()
        self.assertGreater(session._sleep_for_quota.call_args.args[0], 7200)
        event = session.engine.log_event.call_args_list[0].kwargs["data"]
        self.assertEqual(event["provider_reset_at_utc"], reset.isoformat())
