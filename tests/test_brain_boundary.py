from __future__ import annotations

import unittest

from agent_world.brain_boundary import ConversationBoundary


class ConversationBoundaryTests(unittest.TestCase):
    def test_bounded_session_resumes_then_rotates_at_limit(self) -> None:
        boundary = ConversationBoundary(
            agent_id="agent-1",
            connector_profile="stateless-v2",
            conversation_mode="bounded-session-v1",
            max_turns=2,
        )

        first = boundary.prepare()
        boundary.commit(first, "session-1")
        second = boundary.prepare()
        boundary.commit(second, "session-1")
        third = boundary.prepare()

        self.assertTrue(first.full_context)
        self.assertEqual(second.resume_session_id, "session-1")
        self.assertFalse(second.full_context)
        self.assertTrue(third.full_context)
        self.assertEqual(third.generation, 2)

    def test_checkpoint_restore_preserves_provenance_but_starts_fresh(self) -> None:
        original = ConversationBoundary(
            agent_id="agent-1",
            connector_profile="stateless-v2",
            conversation_mode="bounded-session-v1",
            max_turns=10,
        )
        invocation = original.prepare()
        original.commit(invocation, "possibly-dirty-provider-session")

        restored = ConversationBoundary(
            agent_id="agent-1",
            connector_profile="stateless-v2",
            conversation_mode="bounded-session-v1",
            max_turns=10,
        )
        restored.restore_checkpoint_metadata(original.export_state())
        next_invocation = restored.prepare()

        self.assertIsNone(next_invocation.resume_session_id)
        self.assertTrue(next_invocation.full_context)
        self.assertEqual(
            restored.restored_checkpoint_session_id,
            "possibly-dirty-provider-session",
        )
        self.assertEqual(next_invocation.generation, 2)

    def test_stateless_mode_always_sends_full_context(self) -> None:
        boundary = ConversationBoundary(
            agent_id="agent-1",
            connector_profile="stateless-v2",
            conversation_mode="stateless",
            max_turns=10,
        )

        first = boundary.prepare()
        boundary.commit(first, None)
        second = boundary.prepare()

        self.assertTrue(first.full_context)
        self.assertTrue(second.full_context)
        self.assertIsNone(second.resume_session_id)


if __name__ == "__main__":
    unittest.main()
