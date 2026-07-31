from __future__ import annotations

from datetime import datetime, timezone
import unittest

from agent_world.claude_brain import _is_quota_error as claude_is_quota_error
from agent_world.codex_brain import _is_quota_error as codex_is_quota_error
from agent_world.cursor_brain import _is_quota_error as cursor_is_quota_error
from agent_world.provider_limits import is_quota_detail, quota_reset_at


# The exact text that escaped the old per-adapter marker lists, verbatim from
# the Fable seed-41 ledger.
FABLE_WEEKLY_LIMIT = (
    "claude -p exited 1: You've hit your weekly limit "
    "· resets 2pm (America/Los_Angeles)"
)


class QuotaDetectionTests(unittest.TestCase):
    def test_the_weekly_limit_message_that_corrupted_a_trial_is_detected(self) -> None:
        self.assertTrue(is_quota_detail(FABLE_WEEKLY_LIMIT))

    def test_every_adapter_shares_one_classifier(self) -> None:
        # Drift between three copies of this list is what caused the bug.
        for classifier in (
            claude_is_quota_error,
            codex_is_quota_error,
            cursor_is_quota_error,
        ):
            self.assertTrue(classifier(FABLE_WEEKLY_LIMIT), classifier)

    def test_known_provider_phrasings(self) -> None:
        for detail in (
            "You've hit your weekly limit",
            "You've reached your 5-hour limit",
            "Usage limit reached",
            "429 Too Many Requests",
            "rate_limit_exceeded",
            "Your credit balance is too low",
            "insufficient_quota",
            "You have exceeded your monthly limit",
            "Limit will reset at 10:00",
        ):
            self.assertTrue(is_quota_detail(detail), detail)

    def test_model_and_transport_failures_are_not_quota(self) -> None:
        # A false positive only pauses a run; a false negative fabricates agent
        # behavior. But these must not pause a run that should keep going.
        for detail in (
            "Invalid JSON response: unexpected token",
            "error_max_structured_output_retries",
            "connection refused",
            "response stalled mid-stream",
            "the agent chose to wait at the resource limit of the tile",
            "",
            None,
        ):
            self.assertFalse(is_quota_detail(detail), detail)


class QuotaResetParsingTests(unittest.TestCase):
    def test_wall_clock_with_timezone_resolves_to_the_next_occurrence(self) -> None:
        now = datetime(2026, 7, 29, 23, 0, tzinfo=timezone.utc)  # 4pm Los Angeles
        reset = quota_reset_at(FABLE_WEEKLY_LIMIT, now=now)
        self.assertIsNotNone(reset)
        # 2pm Los Angeles already passed today, so it is tomorrow's 2pm = 21:00Z.
        self.assertEqual(reset, datetime(2026, 7, 30, 21, 0, tzinfo=timezone.utc))

    def test_wall_clock_later_today_stays_today(self) -> None:
        now = datetime(2026, 7, 29, 17, 0, tzinfo=timezone.utc)  # 10am Los Angeles
        reset = quota_reset_at(FABLE_WEEKLY_LIMIT, now=now)
        self.assertEqual(reset, datetime(2026, 7, 29, 21, 0, tzinfo=timezone.utc))

    def test_relative_and_absolute_forms(self) -> None:
        now = datetime(2026, 7, 29, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(
            quota_reset_at("try again in 15 minutes", now=now),
            datetime(2026, 7, 29, 12, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(
            quota_reset_at("retry-after: 120", now=now),
            datetime(2026, 7, 29, 12, 2, tzinfo=timezone.utc),
        )
        self.assertEqual(
            quota_reset_at("resets at 2026-08-04T13:04", now=now),
            datetime(2026, 8, 4, 13, 4, tzinfo=timezone.utc),
        )

    def test_no_hint_returns_none_so_the_caller_backs_off(self) -> None:
        self.assertIsNone(quota_reset_at("You've hit your weekly limit", now=None))
        self.assertIsNone(quota_reset_at(None))


if __name__ == "__main__":
    unittest.main()
