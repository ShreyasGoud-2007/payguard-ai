from copy import deepcopy
from types import SimpleNamespace

import pytest

from paygard_ai import ai_provider, config
from paygard_ai.risk_analysis import analyze_invoice_risk


def make_context():
    invoice = {
        "invoice_number": "PRIVATE-INVOICE-77",
        "vendor": "Private Vendor Ltd",
        "po_number": "PRIVATE-PO-42",
        "source_text": "Private raw OCR document text",
        "raw_ocr_text": "Private raw OCR document text",
        "validation_state": "READY",
        "missing_fields": [],
        "uncertain_fields": [],
        "validation_issues": [],
    }
    verification = {
        "status": "REVIEW REQUIRED",
        "checks": {
            "vendor_match": {
                "key": "vendor_match",
                "name": "Vendor match",
                "status": "FAIL",
                "expected": "Private Vendor Ltd",
                "actual": "Other Private Vendor",
                "evidence": "PO vendor",
                "explanation": "The supplier on the invoice must match the approved vendor on the PO.",
                "severity": "high",
            },
            "amount_match": {
                "key": "amount_match",
                "name": "Invoice amount matches PO amount",
                "status": "FAIL",
                "expected": "100.00",
                "actual": "125.00",
                "evidence": "PO amount",
                "explanation": "The invoice total must match the approved PO amount.",
                "severity": "high",
            },
            "duplicate_check": {
                "key": "duplicate_check",
                "name": "Duplicate invoice",
                "status": "PASS",
                "expected": "invoice is not already verified",
                "actual": False,
                "evidence": "Database check",
                "explanation": "Duplicate invoice detection compares invoice numbers.",
                "severity": "low",
            },
        },
    }
    deterministic = analyze_invoice_risk(invoice, verification)
    return invoice, verification, deterministic


def valid_response(payload):
    findings = []
    review_actions = []
    category_by_status = {
        "PASS": "passed",
        "FAIL": "failed",
        "REVIEW REQUIRED": "failed",
        "INCOMPLETE": "incomplete",
    }
    for check in payload["checks"]:
        findings.append({
            "evidence_ref": check["key"],
            "category": category_by_status[check["status"]],
            "explanation": f"Explanation grounded in {check['key']}.",
        })
        if category_by_status[check["status"]] != "passed":
            review_actions.append({
                "evidence_ref": check["key"],
                "action": f"Review the recorded evidence for {check['key']}.",
            })
    return {
        "summary": "The verifier reported review-required checks; inspect their recorded evidence.",
        "findings": findings,
        "missing_information": payload["missing_information_refs"],
        "review_actions": review_actions,
    }


class FakeProvider:
    name = "test-provider"
    model = "test-model"

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.payload = None

    def generate(self, payload):
        self.payload = payload
        if self.error:
            raise self.error
        return self.response


def test_disabled_provider_uses_fallback_without_constructing_client(monkeypatch):
    invoice, verification, deterministic = make_context()
    monkeypatch.setattr(config, "AI_PROVIDER", "disabled")
    monkeypatch.setattr(ai_provider, "OpenAIExplanationProvider", lambda *args, **kwargs: pytest.fail("client should not be constructed"))

    result = ai_provider.generate_ai_explanation(invoice, verification, deterministic)

    assert result["source"] == "deterministic_fallback"
    assert result["ai_used"] is False
    assert "disabled" in result["fallback_reason"].lower()


def test_configured_provider_uses_structured_evidence_and_validated_response(monkeypatch):
    invoice, verification, deterministic = make_context()
    payload_capture = {}
    fake_provider = FakeProvider()

    def provider_factory(api_key, model):
        assert api_key == "test-secret-not-sent"
        assert model == "test-model"
        return fake_provider

    monkeypatch.setattr(config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-secret-not-sent")
    monkeypatch.setattr(config, "OPENAI_MODEL", "test-model")
    monkeypatch.setattr(ai_provider, "OpenAIExplanationProvider", provider_factory)

    def response_for_payload(payload):
        payload_capture.update(payload)
        return valid_response(payload)

    fake_provider.generate = response_for_payload
    result = ai_provider.generate_ai_explanation(invoice, verification, deterministic)

    assert result["source"] == "openai"
    assert result["ai_used"] is True
    assert result["verification_status"] == "REVIEW REQUIRED"
    assert "PRIVATE-INVOICE-77" not in repr(payload_capture)
    assert "PRIVATE-PO-42" not in repr(payload_capture)
    assert "Private Vendor Ltd" not in repr(payload_capture)
    assert "Private raw OCR document text" not in repr(payload_capture)
    assert "test-secret-not-sent" not in repr(payload_capture)
    assert payload_capture["checks"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda response: response.update(summary=""),
        lambda response: response["findings"][0].update(evidence_ref="invented_check"),
        lambda response: response["findings"][0].update(category="passed"),
        lambda response: response["findings"][0].update(explanation="This check passed successfully."),
        lambda response: response.update(status="PASSED"),
        lambda response: response.update(summary="All checks passed; the invoice is approved."),
        lambda response: response["missing_information"].append("invented_field"),
    ],
)
def test_invalid_or_unsupported_model_output_uses_fallback(mutator):
    invoice, verification, deterministic = make_context()
    payload = ai_provider.build_ai_evidence_payload(invoice, verification)
    response = valid_response(payload)
    mutator(response)
    provider = FakeProvider(response=response)

    result = ai_provider.generate_ai_explanation(invoice, verification, deterministic, provider=provider)

    assert result["source"] == "deterministic_fallback"
    assert result["ai_used"] is False
    assert result["verification_status"] == verification["status"]


@pytest.mark.parametrize("error", [TimeoutError("timed out"), RuntimeError("provider unavailable")])
def test_timeout_and_provider_errors_use_deterministic_fallback(error):
    invoice, verification, deterministic = make_context()
    provider = FakeProvider(error=error)

    result = ai_provider.generate_ai_explanation(invoice, verification, deterministic, provider=provider)

    assert result["source"] == "deterministic_fallback"
    assert result["verification_status"] == verification["status"]
    assert result["fallback_reason"]


def test_missing_openai_configuration_uses_fallback_without_constructing_client(monkeypatch):
    invoice, verification, deterministic = make_context()
    monkeypatch.setattr(config, "AI_PROVIDER", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    monkeypatch.setattr(config, "OPENAI_MODEL", "gpt-test")
    monkeypatch.setattr(ai_provider, "OpenAIExplanationProvider", lambda *args, **kwargs: pytest.fail("client should not be constructed"))

    result = ai_provider.generate_ai_explanation(invoice, verification, deterministic)

    assert result["source"] == "deterministic_fallback"
    assert "API key" in result["fallback_reason"]


def test_openai_sdk_adapter_sends_json_evidence_and_parses_structured_output():
    invoice, verification, deterministic = make_context()
    payload = ai_provider.build_ai_evidence_payload(invoice, verification)
    response_body = valid_response(payload)
    request_capture = {}

    class FakeCompletions:
        def create(self, **kwargs):
            request_capture.update(kwargs)
            import json

            content = json.dumps(response_body)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content, refusal=None))]
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    provider = ai_provider.OpenAIExplanationProvider("placeholder-key", "mock-model", client=fake_client)
    parsed = provider.generate(payload)

    assert parsed == response_body
    assert request_capture["model"] == "mock-model"
    assert request_capture["response_format"] == {"type": "json_object"}
    assert request_capture["store"] is False
    sent_content = request_capture["messages"][1]["content"]
    assert "PRIVATE-INVOICE-77" not in sent_content
    assert "Private Vendor Ltd" not in sent_content
    assert "Private raw OCR document text" not in sent_content
    assert "placeholder-key" not in sent_content


def test_ai_output_never_changes_verifier_status_or_checks():
    invoice, verification, deterministic = make_context()
    original = deepcopy(verification)
    payload = ai_provider.build_ai_evidence_payload(invoice, verification)
    provider = FakeProvider(response=valid_response(payload))

    result = ai_provider.generate_ai_explanation(invoice, verification, deterministic, provider=provider)

    assert result["verification_status"] == "REVIEW REQUIRED"
    assert verification == original