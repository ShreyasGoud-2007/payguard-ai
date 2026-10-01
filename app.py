import mimetypes
import os
import uuid
from pathlib import Path

import streamlit as st

from paygard_ai.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE
from paygard_ai.database import DatabaseManager
from paygard_ai.workflow import process_invoice_file


DB = DatabaseManager()


@st.cache_resource
def ensure_seed_data():
    DB.setup_database()
    skip_seed = os.getenv("PAYGARD_SKIP_DEMO_SEED", "").strip().lower() in {"1", "true", "yes"}
    if not skip_seed:
        DB.insert_demo_data()
    return True


st.set_page_config(page_title="PayGard AI", page_icon="🧾", layout="wide")
ensure_seed_data()

st.title("PayGard AI Invoice Verification")
st.caption("Invoice evidence review. Verification results are deterministic; payment is never authorized here.")

with st.sidebar:
    st.header("Navigation")
    st.caption("Local verification workspace. No external API required.")

col1, col2, col3, col4 = st.columns(4)
summary = DB.dashboard_summary()
col1.metric("Total invoices", summary.get("total_invoices", 0))
col2.metric("Passed", summary.get("passed", 0))
col3.metric("Review required", summary.get("review_required", 0))
col4.metric("Incomplete", summary.get("incomplete", 0))

source_summary = DB.data_source_summary()
all_sources = sorted({source for table_counts in source_summary.values() for source in table_counts})
source_text = " | ".join(
    f"{source}: {source_summary['purchase_orders'].get(source, 0)} POs, "
    f"{source_summary['goods_receipts'].get(source, 0)} receipts, "
    f"{source_summary['verified_invoices'].get(source, 0)} invoice references"
    for source in all_sources
)
st.caption(f"Reference data source counts: {source_text or 'No reference records'}")
st.caption("Reference-source counts are separate from invoice uploads. Synthetic/demo rows are labeled; Aczen data is not currently connected.")

with st.form("invoice_processing"):
    uploaded_file = st.file_uploader(
        "Invoice file",
        type=["txt", "pdf", "png", "jpg", "jpeg"],
        help="Upload one invoice as TXT, PDF, PNG, JPG, or JPEG. Scans use local Tesseract OCR.",
    )
    st.caption(f"Maximum upload size: {MAX_UPLOAD_SIZE // (1024 * 1024)} MB. AI explanations are optional; the default is deterministic fallback.")
    submitted = st.form_submit_button("Process invoice")

if submitted:
    if uploaded_file is None:
        st.error("Choose an invoice file before processing.")
    else:
        original_name = Path(uploaded_file.name).name
        suffix = Path(original_name).suffix.lower()
        file_bytes = uploaded_file.getvalue()
        if suffix not in ALLOWED_EXTENSIONS:
            st.error(f"Unsupported file type: {suffix or 'unknown'}.")
        elif len(file_bytes) > MAX_UPLOAD_SIZE:
            st.error(f"File exceeds the {MAX_UPLOAD_SIZE // (1024 * 1024)} MB upload limit.")
        else:
            stored_name = f"{uuid.uuid4().hex}{suffix}"
            stored_path = Path("uploads") / stored_name
            stored_path.parent.mkdir(parents=True, exist_ok=True)
            stored_path.write_bytes(file_bytes)
            result = process_invoice_file(
                stored_path,
                DB,
                original_name=original_name,
                stored_name=stored_name,
                mime_type=mimetypes.guess_type(original_name)[0] or uploaded_file.type,
                file_size=len(file_bytes),
            )
            result["original_name"] = original_name
            st.session_state["last_invoice_result"] = result
            st.rerun()

result = st.session_state.get("last_invoice_result")
if result:
    invoice = result["invoice"]
    report = result["report"]
    st.header("Processing result")
    st.write(f"**File:** {result.get('original_name', Path(invoice.get('source_file', '')).name)} ({invoice.get('detected_format', 'unknown')})")
    st.write(f"**Pages:** {invoice.get('page_count', 0)} · **OCR:** {invoice.get('ocr_status', 'not run')} · **Extraction:** {invoice.get('validation_state', 'INCOMPLETE')}")
    if invoice.get("error"):
        st.error(invoice["error"])
    for error in invoice.get("ocr_errors", []):
        st.warning(error)

    st.subheader("Deterministic verification status")
    if result["status"] == "PASSED":
        st.success(result["status"])
    elif result["status"] == "REVIEW REQUIRED":
        st.warning(result["status"])
    else:
        st.error(result["status"])

    if invoice.get("missing_fields"):
        st.warning("Missing fields: " + ", ".join(invoice["missing_fields"]))
    if invoice.get("uncertain_fields"):
        st.write("**Fields needing review:** " + ", ".join(invoice["uncertain_fields"]))
    if invoice.get("validation_issues"):
        st.write("**Extraction issues:**")
        for issue in invoice["validation_issues"]:
            st.write(f"- {issue}")

    analysis = result.get("risk_analysis") or report.get("risk_analysis")
    if analysis:
        ai_explanation = analysis.get("ai_explanation", {})
        st.subheader("AI explanation and human review")
        st.caption(ai_explanation.get("label", "Deterministic fallback; no AI-generated text was used."))
        st.write(ai_explanation.get("summary", analysis.get("summary", "No explanation is available.")))
        if ai_explanation.get("fallback_reason"):
            st.caption(f"Fallback reason: {ai_explanation['fallback_reason']}")
        if ai_explanation.get("findings"):
            st.write("**Explanation findings and evidence references**")
            for finding in ai_explanation["findings"]:
                st.write(f"- {finding.get('category', 'finding')}: {finding.get('explanation', '')} [{finding.get('evidence_ref') or 'deterministic analysis'}]")
                evidence = finding.get("evidence")
                if isinstance(evidence, dict):
                    evidence_text = evidence.get("evidence")
                    expected = evidence.get("expected")
                    actual = evidence.get("actual")
                    st.caption(f"Evidence: {evidence_text or 'not supplied'}; expected: {expected}; actual: {actual}")
        missing_information = ai_explanation.get("missing_information", analysis.get("missing_information", []))
        if missing_information:
            st.write("**Missing or uncertain information**")
            for item in missing_information:
                st.write(f"- {item}")
        review_actions = ai_explanation.get("review_actions", [])
        if review_actions:
            st.write("**Reviewer next steps**")
            for item in review_actions:
                st.write(f"- {item.get('action', item) if isinstance(item, dict) else item}")
        elif analysis.get("review_guidance"):
            st.write("**Reviewer next steps**")
            for item in analysis["review_guidance"]:
                st.write(f"- {item}")
        for limitation in analysis.get("limitations", []):
            st.info(limitation)

    checks = report.get("checks", {})
    if isinstance(checks, dict):
        checks = list(checks.values())
    st.subheader("Verification checks")
    for check_status, label in (
        ("PASS", "Passed checks"),
        ("FAIL", "Failed checks"),
        ("INCOMPLETE", "Incomplete checks"),
    ):
        matching = [
            check for check in checks
            if isinstance(check, dict)
            and (check.get("status") == check_status or (check_status == "FAIL" and check.get("status") == "REVIEW REQUIRED"))
        ]
        with st.expander(f"{label} ({len(matching)})", expanded=check_status != "PASS" and bool(matching)):
            if matching:
                st.dataframe(
                    [{key: check.get(key) for key in ["name", "status", "expected", "actual", "evidence", "explanation"]} for check in matching],
                    use_container_width=True,
                )
            else:
                st.caption(f"No {label.lower()}.")

    with st.expander("Full verification report (technical details)"):
        st.json(report)

    invoice_number = invoice.get("invoice_number")
    if st.session_state.get("review_decision_saved") == invoice_number:
        st.success("Review decision saved and audit event recorded. Verification status was not changed.")
    if result["status"] in {"REVIEW REQUIRED", "INCOMPLETE"} and invoice_number:
        st.subheader("Human review decision")
        st.caption("Recording a review decision does not change the verification status or authorize payment.")
        with st.form("human_review_decision"):
            reviewer = st.text_input("Reviewer name")
            decision = st.selectbox(
                "Decision",
                ["needs_more_information", "confirmed_exception", "escalated"],
            )
            notes = st.text_area("Review notes")
            review_submitted = st.form_submit_button("Record review decision")
        if review_submitted:
            try:
                DB.record_review_decision(invoice_number, decision, reviewer, notes)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["review_decision_saved"] = invoice_number
                st.rerun()
        review_history = DB.get_review_history(invoice_number)
        if review_history:
            st.write("**Recorded review history**")
            st.dataframe(
                [{key: item.get(key) for key in ["decision", "reviewer", "notes", "created_at"]} for item in review_history],
                use_container_width=True,
            )

    st.subheader("Structured invoice fields")
    display_invoice = {key: value for key, value in invoice.items() if key not in {"source_text", "raw_ocr_text", "pages"}}
    st.json(display_invoice)
    with st.expander("Extracted text"):
        st.text(invoice.get("raw_ocr_text") or invoice.get("source_text") or "No text was extracted.")

with st.expander("Purchase orders"):
    po_rows = DB.get_all_purchase_orders()
    st.dataframe(po_rows, use_container_width=True)

with st.expander("Goods receipts"):
    rows = DB.get_all_goods_receipts()
    st.dataframe(rows, use_container_width=True)

with st.expander("Recent activity"):
    st.dataframe(DB.list_recent_activity(10), use_container_width=True)

with st.expander("Recent audit trail"):
    audit_events = DB.list_recent_audit_events(20)
    if audit_events:
        st.dataframe(audit_events, use_container_width=True)
    else:
        st.caption("No audit events have been recorded yet.")

with st.expander("Uploaded invoice history"):
    uploads = DB.get_upload_records(20)
    st.dataframe(
        [{key: row.get(key) for key in ["original_name", "invoice_number", "ocr_status", "final_status", "uploaded_at"]} for row in uploads],
        use_container_width=True,
    )

with st.expander("Data import status"):
    import_runs = DB.get_recent_import_runs(10)
    aczen_po_count = source_summary["purchase_orders"].get("ACZEN", 0)
    aczen_receipt_count = source_summary["goods_receipts"].get("ACZEN", 0)
    if not import_runs and not aczen_po_count and not aczen_receipt_count:
        st.info("No Aczen import is recorded. The Aczen dataset and field documentation have not been supplied.")
        st.write("Mapping confirmation: not confirmed")
        st.write("Aczen purchase orders: 0 | Aczen goods receipts: 0")
    elif import_runs:
        st.dataframe(
            [{key: run.get(key) for key in [
                "source", "status", "mapping_confirmed", "prepared_count", "imported_count",
                "skipped_count", "invalid_count", "duplicate_count", "created_at",
            ]} for run in import_runs],
            use_container_width=True,
        )
