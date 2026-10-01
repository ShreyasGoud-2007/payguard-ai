import hashlib
from pathlib import Path

from paygard_ai.config import DB_PATH
from paygard_ai.database import DatabaseManager
from paygard_ai.demo import run_synthetic_demo


def _hash_file(path):
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_six_synthetic_scenarios_use_real_workflow_and_isolated_database(tmp_path):
    live_hash = _hash_file(DB_PATH)
    result = run_synthetic_demo(tmp_path / "synthetic-demo", use_ocr=False, use_ai=False)

    expected = {
        "matching": "PASSED",
        "amount_mismatch": "REVIEW REQUIRED",
        "missing_information": "INCOMPLETE",
        "duplicate": "REVIEW REQUIRED",
        "po_not_approved": "REVIEW REQUIRED",
        "insufficient_receipt": "REVIEW REQUIRED",
    }
    assert {name: scenario["status"] for name, scenario in result["scenarios"].items()} == expected
    assert all(scenario["invoice"]["vendor"] == "SYNTHETIC DEMO SUPPLY CO" for scenario in result["scenarios"].values())
    assert all(scenario["risk_analysis"]["ai_explanation"]["source"] == "deterministic_fallback" for scenario in result["scenarios"].values())
    assert result["database_path"] != str(DB_PATH)

    from paygard_ai.database import DatabaseManager

    database = DatabaseManager(result["database_path"])
    uploads = database.get_upload_records(20)
    assert len(uploads) == 6
    assert all(record["final_status"] for record in uploads)
    conn = database.connect()
    try:
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE event_type = 'invoice_workflow'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert audit_count == 6
    assert _hash_file(DB_PATH) == live_hash


def test_dashboard_review_decision_is_explicit_audited_and_status_preserving(tmp_path, monkeypatch):
    import paygard_ai.config as app_config
    import paygard_ai.database as database_module
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    db_path = tmp_path / "review-dashboard.db"
    monkeypatch.setattr(database_module, "DB_PATH", db_path)
    monkeypatch.setattr(app_config, "AI_PROVIDER", "disabled")
    monkeypatch.setenv("PAYGARD_SKIP_DEMO_SEED", "1")
    st.cache_resource.clear()
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.add_purchase_order({
        "po_number": "SYNTH-PO-UI",
        "vendor": "SYNTHETIC DEMO SUPPLY CO",
        "quantity": 2,
        "unit_price": 50,
        "amount": 100,
        "status": "APPROVED",
        "data_source": "SYNTHETIC_DEMO",
    })
    manager.add_goods_receipt({
        "receipt_number": "SYNTH-GR-UI",
        "po_number": "SYNTH-PO-UI",
        "quantity": 1,
        "data_source": "SYNTHETIC_DEMO",
    })

    invoice_text = (
        "SYNTHETIC DEMO SUPPLY CO\nInvoice Number: SYNTH-UI-1\n"
        "Invoice Date: 2026-09-30\nPO Number: SYNTH-PO-UI\n"
        "Item: Synthetic Widget\nQuantity: 2\nUnit Price: 50\nTotal Amount: 100\n"
    ).encode()
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=45).run()
    app.file_uploader[0].set_value(("synthetic-review.txt", invoice_text, "text/plain"))
    app.button[0].click().run()
    assert app.session_state["last_invoice_result"]["status"] == "REVIEW REQUIRED"

    app.text_input[0].set_value("Synthetic Reviewer")
    app.selectbox[0].select("confirmed_exception")
    app.text_area[0].set_value("Synthetic receipt quantity is insufficient.")
    next(button for button in app.button if button.label == "Record review decision").click().run()

    assert not app.exception
    history = manager.get_review_history("SYNTH-UI-1")
    assert history[0]["decision"] == "confirmed_exception"
    assert history[0]["reviewer"] == "Synthetic Reviewer"
    assert history[0]["notes"] == "Synthetic receipt quantity is insufficient."
    assert any(item.value == "Verification checks" for item in app.subheader)
    assert any(item.value == "Recent audit trail" for item in app.subheader)
    assert any("Review decision saved" in item.value for item in app.success)
    invoice = manager.get_invoice_record("SYNTH-UI-1")
    assert invoice["verification_status"] == "REVIEW REQUIRED"
    connection = manager.connect()
    try:
        event = connection.execute(
            "SELECT event_type, details FROM audit_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        connection.close()
    assert event["event_type"] == "review_decision"
    assert '"invoice_number": "SYNTH-UI-1"' in event["details"]


def test_legacy_cli_defaults_to_a_separate_temporary_database(tmp_path, monkeypatch, capsys):
    import main as main_module

    demo_directory = tmp_path / "cli-demo"

    def create_demo_directory(prefix):
        demo_directory.mkdir()
        return str(demo_directory)

    monkeypatch.setattr(main_module.tempfile, "mkdtemp", create_demo_directory)

    main_module.run_demo()

    output = capsys.readouterr().out
    assert f"Demo database: {demo_directory / 'paygard_cli_demo.db'}" in output
    assert (demo_directory / "paygard_cli_demo.db").exists()
    assert Path(DB_PATH).resolve() != (demo_directory / "paygard_cli_demo.db").resolve()


def test_demo_cli_reports_expected_setup_error_with_nonzero_exit(monkeypatch, capsys):
    import sys
    import paygard_ai.demo as demo_module

    def fail_demo(*args, **kwargs):
        raise RuntimeError("synthetic OCR setup issue")

    monkeypatch.setattr(demo_module, "run_synthetic_demo", fail_demo)
    monkeypatch.setattr(sys, "argv", ["paygard-demo", "--ocr"])

    try:
        demo_module.main()
    except SystemExit as exc:
        assert exc.code != 0
    else:
        raise AssertionError("demo CLI should exit nonzero when setup fails")

    assert "synthetic OCR setup issue" in capsys.readouterr().err