"""Versioned provider-invocation and conversation boundaries for model brains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CONNECTOR_PROFILES = frozenset({"stateless-v1", "stateless-v2", "stateless-v3"})
CONVERSATION_MODES = frozenset({"stateless", "bounded-session-v1"})
DEFAULT_SESSION_MAX_TURNS = 10


@dataclass(frozen=True)
class ConversationInvocation:
    """Describe whether one decision starts or continues a provider conversation."""

    resume_session_id: str | None
    full_context: bool
    generation: int
    turn: int

    @property
    def resumed(self) -> bool:
        return self.resume_session_id is not None


class ConversationBoundary:
    """Track one agent's bounded provider conversation.

    Provider conversations are deliberately not resumed from a crash checkpoint.
    The external CLIs mutate saved conversations in place, so a process can die
    after a provider accepted a turn but before the world committed that tick.
    Starting a fresh conversation from Agent World's explicit observation and
    memory is the only provider-neutral way to keep completed-tick checkpoints
    clean.
    """

    def __init__(
        self,
        *,
        agent_id: str | None,
        connector_profile: str,
        conversation_mode: str,
        max_turns: int,
    ):
        if connector_profile not in CONNECTOR_PROFILES:
            raise ValueError(f"unsupported connector profile: {connector_profile}")
        if conversation_mode not in CONVERSATION_MODES:
            raise ValueError(f"unsupported conversation mode: {conversation_mode}")
        if max_turns < 1:
            raise ValueError("bounded session turns must be at least 1")
        self.agent_id = agent_id
        self.connector_profile = connector_profile
        self.conversation_mode = conversation_mode
        self.max_turns = max_turns
        self.session_id: str | None = None
        self.generation = 0
        self.turns = 0
        self.last_reset_reason: str | None = None
        self.restored_checkpoint_session_id: str | None = None

    def prepare(self) -> ConversationInvocation:
        if self.conversation_mode == "stateless":
            return ConversationInvocation(
                resume_session_id=None,
                full_context=True,
                generation=0,
                turn=1,
            )
        if self.session_id is not None and self.turns < self.max_turns:
            return ConversationInvocation(
                resume_session_id=self.session_id,
                full_context=False,
                generation=self.generation,
                turn=self.turns + 1,
            )
        if self.session_id is not None:
            self.reset("turn_limit")
        self.generation += 1
        return ConversationInvocation(
            resume_session_id=None,
            full_context=True,
            generation=self.generation,
            turn=1,
        )

    def commit(self, invocation: ConversationInvocation, session_id: str | None) -> None:
        if self.conversation_mode == "stateless":
            return
        if not session_id:
            raise ValueError("bounded provider conversation returned no session id")
        self.session_id = session_id
        self.generation = invocation.generation
        self.turns = invocation.turn
        self.last_reset_reason = None

    def reset(self, reason: str) -> None:
        self.session_id = None
        self.turns = 0
        self.last_reset_reason = reason

    def export_state(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "agent_id": self.agent_id,
            "connector_profile": self.connector_profile,
            "conversation_mode": self.conversation_mode,
            "max_turns": self.max_turns,
            "provider_session_id": self.session_id,
            "generation": self.generation,
            "turns": self.turns,
            "last_reset_reason": self.last_reset_reason,
            "checkpoint_resume_policy": "fresh_session",
        }

    def restore_checkpoint_metadata(self, state: dict[str, Any]) -> None:
        """Retain provenance while intentionally abandoning the mutable provider chat."""

        if state.get("conversation_mode") != self.conversation_mode:
            raise ValueError("checkpoint conversation mode does not match the requested run")
        if state.get("connector_profile") != self.connector_profile:
            raise ValueError("checkpoint connector profile does not match the requested run")
        saved_agent = state.get("agent_id")
        if self.agent_id is not None and saved_agent not in {None, self.agent_id}:
            raise ValueError("checkpoint conversation state belongs to another agent")
        self.generation = int(state.get("generation") or 0)
        saved_session = state.get("provider_session_id")
        self.restored_checkpoint_session_id = str(saved_session) if saved_session else None
        self.reset("checkpoint_restore")

    def usage_metadata(self, invocation: ConversationInvocation) -> dict[str, Any]:
        return {
            "connector_profile": self.connector_profile,
            "conversation_mode": self.conversation_mode,
            "conversation_generation": invocation.generation,
            "conversation_turn": invocation.turn,
            "conversation_resumed": invocation.resumed,
            "full_context_sent": invocation.full_context,
            "session_max_turns": self.max_turns,
        }
