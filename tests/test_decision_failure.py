from __future__ import annotations

import hashlib
import json
import unittest

from agent_world.codex_brain import CODEX_AGENT_DECISION_SCHEMA
from agent_world.decision_failure import (
    ambiguous_boundary_metadata,
    attribute_decision_failure,
    validate_decision_contract,
)
from agent_world.openrouter_brain import AGENT_DECISION_SCHEMA


def _standard_decision() -> dict:
    return {
        "intent": "move east",
        "actions": [{"type": "move", "direction": "east"}],
        "messages": [],
        "memory_updates": [],
    }


class DecisionFailureAttributionTests(unittest.TestCase):
    def test_contract_invalid_output_is_attributed_to_model(self) -> None:
        attribution = attribute_decision_failure(
            '{"intent":"move"',
            AGENT_DECISION_SCHEMA,
        )

        self.assertEqual(attribution.origin, "model_output")
        self.assertEqual(attribution.failure_class, "output_contract_violation")
        self.assertFalse(attribution.contract_validation.valid)

    def test_contract_valid_output_rejected_by_adapter_is_harness_failure(self) -> None:
        payload = json.dumps(_standard_decision())
        attribution = attribute_decision_failure(
            payload,
            AGENT_DECISION_SCHEMA,
        )

        self.assertEqual(attribution.origin, "harness")
        self.assertEqual(
            attribution.failure_class,
            "adapter_rejected_contract_valid_output",
        )
        self.assertTrue(attribution.contract_validation.valid)

    def test_codex_nested_arguments_are_part_of_the_contract(self) -> None:
        valid = {
            "intent": "move east",
            "actions": [
                {"type": "move", "arguments_json": '{"direction":"east"}'}
            ],
            "messages": [],
            "memory_updates": [],
        }
        invalid = {
            **valid,
            "actions": [
                {"type": "move", "arguments_json": '{"direction":"east"'}
            ],
        }

        self.assertTrue(
            validate_decision_contract(
                valid,
                CODEX_AGENT_DECISION_SCHEMA,
                codex_nested_arguments=True,
            ).valid
        )
        validation = validate_decision_contract(
            invalid,
            CODEX_AGENT_DECISION_SCHEMA,
            codex_nested_arguments=True,
        )
        self.assertFalse(validation.valid)
        self.assertIn("arguments_json is not valid JSON", validation.detail)

    def test_declared_schema_fields_and_limits_are_checked(self) -> None:
        invalid = _standard_decision()
        invalid["unexpected"] = True

        validation = validate_decision_contract(
            invalid,
            AGENT_DECISION_SCHEMA,
        )

        self.assertFalse(validation.valid)
        self.assertIn("undeclared field", validation.detail)

    def test_ambiguous_failure_preserves_complete_provider_envelope(self) -> None:
        envelope = '{"type":"result","usage":{"input_tokens":10}}'
        metadata = ambiguous_boundary_metadata(envelope, "no decision")

        self.assertEqual(metadata["decision_failure_origin"], "ambiguous_boundary")
        self.assertEqual(
            metadata["decision_contract_validation"],
            "not_tested",
        )
        self.assertEqual(metadata["failed_raw_provider_envelope"], envelope)
        self.assertEqual(
            metadata["failed_raw_provider_envelope_sha256"],
            hashlib.sha256(envelope.encode("utf-8")).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
