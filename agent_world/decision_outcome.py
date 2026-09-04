"""Trusted connector outcomes, separate from untrusted model intent text."""

from agent_world.models import AgentDecision
from agent_world.metrics import (
    is_auth_failure_message, is_quota_failure_message,
    is_provider_failure_message, is_model_output_failure_message,
)


def failure_decision(message: str, *, kind: str | None = None) -> AgentDecision:
    """Classify adapter-generated diagnostics only, never a model response."""
    if kind is None:
        if is_model_output_failure_message("agent_response", message):
            kind = "model_output"
        elif is_auth_failure_message("agent_response", message):
            kind = "authentication"
        elif is_quota_failure_message("agent_response", message):
            kind = "quota"
        elif is_provider_failure_message("agent_response", message):
            kind = "provider"
        else:
            kind = "harness"
    if kind not in {"model_output", "authentication", "quota", "provider", "harness"}:
        raise ValueError(f"Unknown decision failure kind: {kind}")
    return AgentDecision(intent=message, actions=[{"type": "wait"}], failure_kind=kind)


def restore_decision(value: dict) -> AgentDecision:
    """Restore internal metadata only at the trusted local journal boundary."""
    decision = AgentDecision.from_json_like(value)
    if isinstance(value, dict) and value.get("failure_kind"):
        decision.failure_kind = value["failure_kind"]
    return decision
