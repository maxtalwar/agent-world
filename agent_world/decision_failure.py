"""Independent attribution for provider-output and harness decision failures."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True)
class ContractValidation:
    valid: bool
    detail: str


@dataclass(frozen=True)
class DecisionFailureAttribution:
    origin: str
    failure_class: str
    contract_validation: ContractValidation
    raw_response: str

    def usage_metadata(self, adapter_detail: str) -> dict[str, Any]:
        return {
            "decision_failure_origin": self.origin,
            "decision_failure_class": self.failure_class,
            "decision_failure_detail": adapter_detail,
            "decision_contract_validation": (
                "valid" if self.contract_validation.valid else "invalid"
            ),
            "decision_contract_detail": self.contract_validation.detail,
            "decision_failure_attribution_confidence": "confirmed",
            "failed_raw_response": self.raw_response,
            "failed_raw_response_sha256": _sha256(self.raw_response),
        }


def attribute_decision_failure(
    payload: Any,
    schema: dict[str, Any],
    *,
    codex_nested_arguments: bool = False,
) -> DecisionFailureAttribution:
    """Attribute invalid output or a subsequent production-adapter rejection."""

    raw_response = serialize_raw(payload)
    validation = validate_decision_contract(
        payload,
        schema,
        codex_nested_arguments=codex_nested_arguments,
    )
    if validation.valid:
        return DecisionFailureAttribution(
            origin="harness",
            failure_class="adapter_rejected_contract_valid_output",
            contract_validation=validation,
            raw_response=raw_response,
        )
    return DecisionFailureAttribution(
        origin="model_output",
        failure_class="output_contract_violation",
        contract_validation=validation,
        raw_response=raw_response,
    )


def ambiguous_boundary_metadata(
    provider_envelope: str,
    detail: str,
) -> dict[str, Any]:
    """Describe a failure before an independently testable payload was isolated."""

    return {
        "decision_failure_origin": "ambiguous_boundary",
        "decision_failure_class": "payload_extraction_failure",
        "decision_failure_detail": detail,
        "decision_contract_validation": "not_tested",
        "decision_contract_detail": "No isolated decision payload was available.",
        "decision_failure_attribution_confidence": "ambiguous",
        "failed_raw_provider_envelope": provider_envelope,
        "failed_raw_provider_envelope_sha256": _sha256(provider_envelope),
    }


def attributed_failure_message(
    provider_label: str,
    attribution: DecisionFailureAttribution,
    adapter_detail: str,
) -> str:
    if attribution.origin == "model_output":
        return (
            f"{provider_label} model output contract failed: "
            f"{attribution.contract_validation.detail}"
        )
    return (
        f"{provider_label} harness failed: adapter rejected contract-valid "
        f"output: {adapter_detail}"
    )


def validate_decision_contract(
    payload: Any,
    schema: dict[str, Any],
    *,
    codex_nested_arguments: bool = False,
) -> ContractValidation:
    """Validate raw output independently from the production decision adapter."""

    value = payload
    if isinstance(payload, str):
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            return ContractValidation(
                False,
                f"Payload is not valid JSON: {exc}",
            )

    issue = _schema_issue(value, schema, "$")
    if issue is not None:
        return ContractValidation(False, issue)

    if codex_nested_arguments:
        for index, action in enumerate(value.get("actions", [])):
            arguments_json = action.get("arguments_json")
            try:
                arguments = json.loads(arguments_json)
            except json.JSONDecodeError as exc:
                return ContractValidation(
                    False,
                    f"$.actions[{index}].arguments_json is not valid JSON: {exc}",
                )
            if not isinstance(arguments, dict):
                return ContractValidation(
                    False,
                    f"$.actions[{index}].arguments_json must encode an object",
                )

    return ContractValidation(True, "Payload satisfies the declared decision contract.")


def serialize_raw(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError):
        return repr(value)


def _schema_issue(value: Any, schema: dict[str, Any], path: str) -> str | None:
    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        return f"{path} must be {expected_type}, got {type(value).__name__}"

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        return f"{path} is not one of the declared values"

    if isinstance(value, str):
        maximum = schema.get("maxLength")
        if isinstance(maximum, int) and len(value) > maximum:
            return f"{path} exceeds maxLength {maximum}"

    if isinstance(value, list):
        maximum = schema.get("maxItems")
        if isinstance(maximum, int) and len(value) > maximum:
            return f"{path} exceeds maxItems {maximum}"
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issue = _schema_issue(item, item_schema, f"{path}[{index}]")
                if issue is not None:
                    return issue

    if isinstance(value, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                return f"{path}.{key} is required"
        properties = schema.get("properties") or {}
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                return f"{path} contains undeclared field {unknown[0]!r}"
        for key, child_schema in properties.items():
            if key in value and isinstance(child_schema, dict):
                issue = _schema_issue(value[key], child_schema, f"{path}.{key}")
                if issue is not None:
                    return issue
    return None


def _matches_type(value: Any, expected_type: str) -> bool:
    return {
        "array": isinstance(value, list),
        "boolean": isinstance(value, bool),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "null": value is None,
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "object": isinstance(value, dict),
        "string": isinstance(value, str),
    }.get(expected_type, True)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
