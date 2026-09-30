"""Explain deterministic invoice verification evidence for human review.

This module does not call an AI service and does not change verification results.
"""

from typing import Any


def _check_items(verification: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    checks = verification.get("checks")
    if isinstance(checks, dict):
        return [(str(key), value) for key, value in checks.items() if isinstance(value, dict)]
    if isinstance(checks, (list, tuple)):
        return [
            (str(check.get("key") or index), check)
            for index, check in enumerate(checks)
            if isinstance(check, dict)
        ]
    return []


def _evidence_entry(key: str, check: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": key,
        "name": check.get("name") or key,
        "status": str(check.get("status") or "UNKNOWN").upper(),
        "expected": check.get("expected"),
        "actual": check.get("actual"),
        "evidence": check.get("evidence"),
        "explanation": check.get("explanation"),
        "severity": check.get("severity"),
    }


def _unique_strings(values: list[Any]) -> list[str]:
    unique = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if text and text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def analyze_invoice_risk(invoice: dict[str, Any] | None, verification: dict[str, Any] | None) -> dict[str, Any]:
    """Build a factual review summary from extraction fields and verifier output.

    The returned text is assembled only from observed statuses, check evidence,
    and extraction validation fields. No absent invoice value is inferred.
    """
    invoice = invoice if isinstance(invoice, dict) else {}
    verification = verification if isinstance(verification, dict) else {}
    verification_status = verification.get("status")
    if not isinstance(verification_status, str) or not verification_status.strip():
        verification_status = "UNKNOWN"
    else:
        verification_status = verification_status.strip().upper()

    passed_checks = []
    failed_checks = []
    incomplete_checks = []
    unclassified_checks = []
    for key, check in _check_items(verification):
        entry = _evidence_entry(key, check)
        if entry["status"] == "PASS":
            passed_checks.append(entry)
        elif entry["status"] in {"FAIL", "REVIEW REQUIRED"}:
            failed_checks.append(entry)
        elif entry["status"] == "INCOMPLETE":
            incomplete_checks.append(entry)
        else:
            unclassified_checks.append(entry)

    warnings = failed_checks + incomplete_checks
    missing_fields = _unique_strings(invoice.get("missing_fields", []))
    uncertain_fields = _unique_strings(invoice.get("uncertain_fields", []))
    validation_issues = _unique_strings(invoice.get("validation_issues", []))
    missing_information = _unique_strings(
        missing_fields
        + [f"Uncertain field: {field}" for field in uncertain_fields]
        + validation_issues
    )

    review_guidance = []
    for item in failed_checks:
        review_guidance.append(
            f"Review {item['name']} against its recorded expected and actual values."
        )
    for item in incomplete_checks:
        review_guidance.append(
            f"Obtain or confirm the information needed for {item['name']}; this check is incomplete."
        )
    for field in missing_fields:
        review_guidance.append(f"Provide or confirm the missing invoice field: {field}.")
    for field in uncertain_fields:
        review_guidance.append(f"Review the extracted candidate for the uncertain field: {field}.")
    review_guidance = _unique_strings(review_guidance)

    limitations = []
    if not passed_checks and not failed_checks and not incomplete_checks:
        limitations.append("No verification check evidence was provided; this analysis cannot explain individual checks.")
    if unclassified_checks:
        limitations.append("Some verification checks had unrecognized statuses and were not classified as pass, fail, or incomplete.")
    if verification_status == "UNKNOWN":
        limitations.append("The verification result did not include a final status.")
    if not passed_checks and not failed_checks and not incomplete_checks:
        review_guidance.append("Obtain the deterministic verification checks and evidence before relying on this outcome.")

    if verification_status == "PASSED":
        summary = (
            f"Deterministic verification returned PASSED with {len(passed_checks)} passed checks, "
            f"{len(failed_checks)} failed checks, and {len(incomplete_checks)} incomplete checks."
        )
    elif verification_status == "REVIEW REQUIRED":
        names = ", ".join(item["name"] for item in failed_checks) or "no individual failed check was provided"
        summary = f"Deterministic verification returned REVIEW REQUIRED. Recorded failed checks: {names}."
    elif verification_status == "INCOMPLETE":
        names = ", ".join(item["name"] for item in incomplete_checks) or "no individual incomplete check was provided"
        summary = f"Deterministic verification returned INCOMPLETE. Recorded incomplete checks: {names}."
    else:
        summary = "A verification outcome is not available from the supplied evidence."

    if missing_information:
        summary += f" Extraction information needing confirmation: {', '.join(missing_information)}."

    return {
        "analysis_method": "deterministic_fallback",
        "analysis_label": "Deterministic explanation; no AI model was used.",
        "ai_used": False,
        "verification_status": verification_status,
        "summary": summary,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "incomplete_checks": incomplete_checks,
        "unclassified_checks": unclassified_checks,
        "warnings": warnings,
        "missing_information": missing_information,
        "review_guidance": review_guidance,
        "limitations": limitations,
        "insufficient_evidence": bool(limitations),
    }