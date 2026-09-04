"""Shared provider decision schema and stable system instructions."""
from typing import Any

AGENT_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "actions", "messages", "memory_updates"],
    "properties": {
        "intent": {
            "type": "string",
            "description": "A short reason for the choices this tick.",
            "maxLength": 180,
        },
        "actions": {
            "type": "array",
            "description": "Ordered action objects using valid action schemas from the observation.",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "type": {"type": "string"},
                },
                "required": ["type"],
            },
        },
        "messages": {
            "type": "array",
            "description": "Optional speech objects. Use mode say, whisper, or broadcast.",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "mode": {"type": "string"},
                    "text": {"type": "string", "maxLength": 240},
                    "to": {"type": "string"},
                },
                "required": ["mode", "text"],
            },
        },
        "memory_updates": {
            "type": "array",
            "description": "Facts the agent chooses to remember.",
            "maxItems": 3,
            "items": {"type": "string", "maxLength": 180},
        },
    },
}


SYSTEM_INSTRUCTIONS = (
    "You are choosing one tick of behavior for a simulated world agent. "
    "Pursue the objective stated in the world rulebook while respecting the simulated constraints. "
    "Use only valid actions from the observation. Return JSON only. "
    "Keep the JSON concise. Use short strings. "
    "Do not describe plans outside the JSON. Do not assume hidden abilities."
)


