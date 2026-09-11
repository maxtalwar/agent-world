import unittest
from agent_world.leaderboard import quota_retry_at

class QuotaDisplayTests(unittest.TestCase):
    def test_current_session_wait_supersedes_expired_weekly_deadline(self):
        old={"next_auto_resume_at_utc":"2026-09-10T21:01:00Z"}
        self.assertEqual(quota_retry_at({"retry_at":"2026-09-11T04:11:00Z"},old,old,None),"2026-09-11T04:11:00Z")
    def test_controller_schedule_used_when_no_current_wait(self):
        self.assertEqual(quota_retry_at({}, {}, {"next_auto_resume_at_utc":"future"},None),"future")
    def test_exhausted_wait_does_not_reuse_old_event(self):
        self.assertIsNone(quota_retry_at({"retry_at":"old"},{},{},"quota_wait_budget_exhausted"))
