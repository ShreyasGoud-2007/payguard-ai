"""Optional, evidence-bounded AI explanations for deterministic verification."""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from . import config


_NUMERIC_CHECK_KEYS = {
    "quantity_vs_po",
    "unit_price_match",
    "amount_match",
    "invoice_total_match",
    "receipt_support",
}
_CATEGORY_BY_STATUS = {
    "PASS": "passed",
    "FAIL": "failed",
    "REVIEW REQUIRED": "failed",
    "INCOMPLETE": "incomplete",
}
_PROHIBITED_ACTION = re.compile(r"\b(?:approve|approved|reject|rejected|pay|payment|authorize|authorise)\b", re.I)
_DECISION_RECOMMENDATION = re.compile(
    r"\b(?:invoice|bill|payment)\s+(?:is\s+)?(?:approved|rejected|paid|authorized|authorised)\b"
    r"|\b(?:approve|reject|pay|authorize|authorise)\s+(?:the\s+)?(?:invoice|bill|payment)\b"
    r"|\b(?:initiate|make|release|send)\s+(?:a\s+|the\s+)?payment\b",
    re.I,
)
_POSITIVE_CHECK_CLAIM = re.compile(
    r"\b(?:passed|passes|has passed|matched successfully|is compliant|is valid|was approved)\b",
    re.I,
)
_OVERALL_SUCCESS_CLAIM = re.compile(
    r"\b(?:all checks? passed|verification (?:passed|succeeded|was successful)|invoice (?:is\s+)?(?:valid|approved|cleared|passed))\b",
    re.I,
)


class ExplanationProvider(Protocol):
    name: str
    model: str

    def generate(self, evidence: dict[str, Any]) -> dict[str, Any]: ...


class OpenAIExplanationProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, client: Any | None = None):
        self.model = model
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, timeout=20.0, max_retries=0)
        self.client = client

    def generate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You explain invoice verification evidence to a human reviewer. "
                        "Use only the supplied fields and check references. Do not infer missing facts, "
                        "change or restate the verifier's decision, or recommend approval, rejection, "
                        "authorization, or payment. Return only a JSON object with exactly these keys: "
                        "summary (string), findings (array of {evidence_ref, category, explanation}), "
                        "missing_information (array of supplied field names), and review_actions "
                        "(array of {evidence_ref, action}). Include each supplied check exactly once in findings. "
                        "Categories must match the supplied check status. Reference only supplied check keys "
                        "or field:<name> references. Keep the summary concise."
                    ),
                },
                {"role": "user", "content": json.dumps(evidence, ensure_ascii=True, separators=(",", ":"))},
            ],
            response_format={"type": "json_object"},
            store=False,
            max_completion_tokens=700,
            temperature=0,
        )
        message = response.choices[0].message
        if getattr(message, "refusal", None):
            raise ValueError("The provider refused the explanation request")
        content = message.content
        if not isinstance(content, str):
            raise ValueError("The provider response did not contain JSON text")
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("The provider response was not a JSON object")
        return parsed


def build_ai_evidence_payload(invoice: dict[str, Any], verification: dict[str, Any]) -> dict[str, Any]:
    """Select only status, check evidence, numeric comparisons, and field names."""
    raw_checks = verification.get("checks")
    if isinstance(raw_checks, dict):
        checks = [(str(key), value) for key, value in raw_checks.items() if isinstance(value, dict)]
    elif isinstance(raw_checks, (list, tuple)):
        checks = [
            (str(item.get("key") or index), item)
            for index, item in enumerate(raw_checks)
            if isinstance(item, dict)
        ]
    else:
        checks = []

    safe_checks = []
    for key, check in checks[:40]:
        status = str(check.get("status") or "UNKNOWN").upper()
        safe_check = {
            "key": key,
            "name": str(check.get("name") or key)[:120],
            "status": status,
            "explanation": str(check.get("explanation") or "")[:400],
            "evidence": str(check.get("evidence") or "")[:160],
            "severity": str(check.get("severity") or "")[:40],
        }
        if key in _NUMERIC_CHECK_KEYS:
            expected = _safe_number(check.get("expected"))
            actual = _safe_number(check.get("actual"))
            if expected is not None:
                safe_check["expected"] = expected
            if actual is not None:
                safe_check["actual"] = actual
        elif key == "duplicate_check" and isinstance(check.get("actual"), bool):
            safe_check["actual"] = check["actual"]
        elif key == "po_approval":
            status_value = check.get("actual")
            if isinstance(status_value, str) and status_value.upper() in {"APPROVED", "PENDING", "REJECTED"}:
                safe_check["actual"] = status_value.upper()
        safe_checks.append(safe_check)

    missing = _string_fields(invoice.get("missing_fields"))
    uncertain = _string_fields(invoice.get("uncertain_fields"))
    validation_issues = invoice.get("validation_issues", [])
    return {
        "verification_status": _safe_status(verification.get("status")),
        "checks": safe_checks,
        "extraction_state": str(invoice.get("validation_state") or "UNKNOWN")[:40],
        "missing_information_refs": sorted(set(missing + uncertain)),
        "validation_issue_count": len(validation_issues) if isinstance(validation_issues, list) else 0,
    }


def _safe_number(value: Any) -> int | float | str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        try:
            number = Decimal(candidate)
        except InvalidOperation:
            return None
        if number.is_finite():
            return candidate
    return None


def _string_fields(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()][:50]


def _safe_status(value: Any) -> str:
    if isinstance(value, str) and value.upper() in {"PASSED", "REVIEW REQUIRED", "INCOMPLETE"}:
        return value.upper()
    return "UNKNOWN"


def _category_for_status(status: str) -> str:
    return _CATEGORY_BY_STATUS.get(status, "unclassified")


def _validate_response(response: Any, evidence: dict[str, Any]) -> dict[str, Any]:
    expected_keys = {"summary", "findings", "missing_information", "review_actions"}
    if not isinstance(response, dict) or set(response) != expected_keys:
        raise ValueError("Unexpected response structure")
    summary = response["summary"]
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 1200:
        raise ValueError("Invalid summary")

    checks = evidence["checks"]
    checks_by_key = {check["key"]: check for check in checks}
    findings = response["findings"]
    if not isinstance(findings, list) or len(findings) != len(checks):
        raise ValueError("Findings do not cover the supplied checks")
    validated_findings = []
    seen_findings = set()
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != {"evidence_ref", "category", "explanation"}:
            raise ValueError("Malformed finding")
        reference = finding["evidence_ref"]
        if reference not in checks_by_key or reference in seen_findings:
            raise ValueError("Unsupported or repeated evidence reference")
        check = checks_by_key[reference]
        expected_category = _category_for_status(check["status"])
        if finding["category"] != expected_category:
            raise ValueError("Finding category conflicts with deterministic check status")
        explanation = finding["explanation"]
        if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 600:
            raise ValueError("Invalid finding explanation")
        if expected_category != "passed" and _POSITIVE_CHECK_CLAIM.search(explanation):
            raise ValueError("Finding contradicts the deterministic check status")
        if _DECISION_RECOMMENDATION.search(explanation):
            raise ValueError("Finding contains an approval or payment decision")
        seen_findings.add(reference)
        validated_findings.append({
            "evidence_ref": reference,
            "category": expected_category,
            "explanation": explanation.strip(),
            "evidence": check,
        })
    if seen_findings != set(checks_by_key):
        raise ValueError("A supplied check was omitted")

    expected_missing = set(evidence["missing_information_refs"])
    missing_information = response["missing_information"]
    if (
        not isinstance(missing_information, list)
        or any(not isinstance(item, str) for item in missing_information)
        or len(missing_information) != len(set(missing_information))
        or set(missing_information) != expected_missing
    ):
        raise ValueError("Missing-information references do not match extraction evidence")

    review_actions = response["review_actions"]
    if not isinstance(review_actions, list) or len(review_actions) > 60:
        raise ValueError("Invalid reviewer actions")
    allowed_action_refs = set(checks_by_key) | {f"field:{field}" for field in expected_missing}
    required_action_refs = {
        key for key, check in checks_by_key.items() if check["status"] != "PASS"
    } | {f"field:{field}" for field in expected_missing}
    seen_action_refs = set()
    validated_actions = []
    for action in review_actions:
        if not isinstance(action, dict) or set(action) != {"evidence_ref", "action"}:
            raise ValueError("Malformed reviewer action")
        reference = action["evidence_ref"]
        text = action["action"]
        if reference not in allowed_action_refs or reference in seen_action_refs:
            raise ValueError("Unsupported or repeated reviewer-action reference")
        if not isinstance(text, str) or not text.strip() or len(text) > 400:
            raise ValueError("Invalid reviewer action")
        if _PROHIBITED_ACTION.search(text) or _DECISION_RECOMMENDATION.search(text):
            raise ValueError("Reviewer action contains a prohibited decision or payment instruction")
        seen_action_refs.add(reference)
        validated_actions.append({"evidence_ref": reference, "action": text.strip()})
    if not required_action_refs.issubset(seen_action_refs):
        raise ValueError("Reviewer actions omitted a failed, incomplete, or missing-information reference")

    if _DECISION_RECOMMENDATION.search(summary):
        raise ValueError("Summary contains a prohibited decision or payment instruction")
    if evidence["verification_status"] != "PASSED" and _OVERALL_SUCCESS_CLAIM.search(summary):
        raise ValueError("Summary contradicts the deterministic verification status")
    return {
        "summary": summary.strip(),
        "findings": validated_findings,
        "missing_information": missing_information,
        "review_actions": validated_actions,
    }


def _configured_provider() -> tuple[ExplanationProvider | None, str]:
    provider_name = (config.AI_PROVIDER or "disabled").strip().lower()
    if provider_name in {"", "disabled", "none"}:
        return None, "AI provider is disabled"
    if provider_name != "openai":
        return None, f"Unsupported AI provider: {provider_name}"
    api_key = config.OPENAI_API_KEY.strip() if isinstance(config.OPENAI_API_KEY, str) else ""
    if not api_key:
        return None, "OpenAI API key is not configured"
    model = config.OPENAI_MODEL.strip() if isinstance(config.OPENAI_MODEL, str) else ""
    if not model:
        return None, "OpenAI model is not configured"
    try:
        return OpenAIExplanationProvider(api_key, model), ""
    except ImportError:
        return None, "OpenAI SDK is unavailable"
    except Exception:
        return None, "OpenAI provider could not be initialized"


def _fallback(deterministic: dict[str, Any], reason: str) -> dict[str, Any]:
    findings = []
    for category, key_name in (
        ("passed", "passed_checks"),
        ("failed", "failed_checks"),
        ("incomplete", "incomplete_checks"),
        ("unclassified", "unclassified_checks"),
    ):
        for check in deterministic.get(key_name, []):
            findings.append({
                "evidence_ref": check.get("key"),
                "category": category,
                "explanation": check.get("explanation") or check.get("name") or "Check result recorded.",
                "evidence": check,
            })
    return {
        "source": "deterministic_fallback",
        "label": "Deterministic fallback; no AI-generated text was used.",
        "ai_used": False,
        "provider": None,
        "model": None,
        "verification_status": deterministic.get("verification_status", "UNKNOWN"),
        "summary": deterministic.get("summary", "No deterministic explanation is available."),
        "findings": findings,
        "missing_information": deterministic.get("missing_information", []),
        "review_actions": [
            {"evidence_ref": None, "action": text}
            for text in deterministic.get("review_guidance", [])
        ],
        "fallback_reason": reason,
    }


def generate_ai_explanation(
    invoice: dict[str, Any],
    verification: dict[str, Any],
    deterministic: dict[str, Any],
    *,
    provider: ExplanationProvider | None = None,
) -> dict[str, Any]:
    """Use a configured provider if available, otherwise return deterministic text."""
    evidence = build_ai_evidence_payload(invoice, verification)
    if not evidence["checks"]:
        return _fallback(deterministic, "No verifier check evidence is available for a model explanation")

    if provider is None:
        provider, reason = _configured_provider()
        if provider is None:
            return _fallback(deterministic, reason)

    try:
        raw_response = provider.generate(evidence)
        validated = _validate_response(raw_response, evidence)
    except Exception as exc:
        reason = "AI request timed out" if "timeout" in type(exc).__name__.lower() else "AI response unavailable or invalid"
        return _fallback(deterministic, reason)

    return {
        "source": "openai",
        "label": "AI-generated explanation (OpenAI); deterministic verification remains authoritative.",
        "ai_used": True,
        "provider": "openai",
        "model": getattr(provider, "model", config.OPENAI_MODEL),
        "verification_status": deterministic.get("verification_status", "UNKNOWN"),
        **validated,
        "fallback_reason": None,
    }