import json
import sqlite3
from pathlib import Path
from typing import Any

from .config import DB_PATH


class DatabaseManager:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(DB_PATH)

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def setup_database(self):
        conn = self.connect()
        try:
            cursor = conn.cursor()

            def ensure_columns(table_name: str, expected: list[str]):
                existing = [row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()]
                for column_name, column_type in expected:
                    if column_name not in existing:
                        conn.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                        )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS purchase_orders (
                    po_number TEXT PRIMARY KEY,
                    vendor TEXT NOT NULL,
                    quantity INTEGER,
                    unit_price REAL,
                    amount REAL,
                    line_items_json TEXT,
                    status TEXT DEFAULT 'APPROVED',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    data_source TEXT NOT NULL DEFAULT 'LEGACY',
                    source_record_id TEXT,
                    source_provenance_json TEXT
                )
                """
            )
            ensure_columns("purchase_orders", [
                ("line_items_json", "TEXT"),
                ("status", "TEXT DEFAULT 'APPROVED'"),
                ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
                ("data_source", "TEXT NOT NULL DEFAULT 'LEGACY'"),
                ("source_record_id", "TEXT"),
                ("source_provenance_json", "TEXT"),
            ])

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS goods_receipts (
                    receipt_number TEXT PRIMARY KEY,
                    po_number TEXT NOT NULL,
                    quantity INTEGER,
                    received_on TEXT,
                    line_items_json TEXT,
                    data_source TEXT NOT NULL DEFAULT 'LEGACY',
                    source_record_id TEXT,
                    source_provenance_json TEXT,
                    FOREIGN KEY (po_number) REFERENCES purchase_orders(po_number)
                )
                """
            )
            ensure_columns("goods_receipts", [
                ("received_on", "TEXT"),
                ("line_items_json", "TEXT"),
                ("data_source", "TEXT NOT NULL DEFAULT 'LEGACY'"),
                ("source_record_id", "TEXT"),
                ("source_provenance_json", "TEXT"),
            ])
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS verified_invoices (
                    invoice_number TEXT PRIMARY KEY,
                    vendor TEXT NOT NULL,
                    po_number TEXT,
                    quantity INTEGER,
                    unit_price REAL,
                    amount REAL,
                    status TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    data_source TEXT NOT NULL DEFAULT 'LEGACY',
                    source_record_id TEXT,
                    source_provenance_json TEXT
                )
                """
            )
            ensure_columns("verified_invoices", [
                ("data_source", "TEXT NOT NULL DEFAULT 'LEGACY'"),
                ("source_record_id", "TEXT"),
                ("source_provenance_json", "TEXT"),
            ])
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_number TEXT PRIMARY KEY,
                    vendor TEXT,
                    po_number TEXT,
                    invoice_date TEXT,
                    amount REAL,
                    currency TEXT,
                    extraction_json TEXT,
                    verification_status TEXT,
                    source_file TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            ensure_columns("invoices", [
                ("vendor", "TEXT"),
                ("po_number", "TEXT"),
                ("invoice_date", "TEXT"),
                ("amount", "REAL"),
                ("currency", "TEXT"),
                ("extraction_json", "TEXT"),
                ("verification_status", "TEXT"),
                ("source_file", "TEXT"),
                ("created_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
            ])
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS verification_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT,
                    check_name TEXT,
                    check_key TEXT,
                    status TEXT,
                    expected_value TEXT,
                    actual_value TEXT,
                    explanation TEXT,
                    evidence TEXT,
                    severity TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS review_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number TEXT,
                    decision TEXT,
                    reviewer TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS uploaded_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    original_name TEXT,
                    stored_name TEXT,
                    file_path TEXT,
                    mime_type TEXT,
                    file_size INTEGER,
                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    invoice_number TEXT,
                    status TEXT
                )
                """
            )
            ensure_columns("uploaded_documents", [
                ("original_name", "TEXT"),
                ("stored_name", "TEXT"),
                ("file_path", "TEXT"),
                ("mime_type", "TEXT"),
                ("file_size", "INTEGER"),
                ("uploaded_at", "TEXT DEFAULT CURRENT_TIMESTAMP"),
                ("invoice_number", "TEXT"),
                ("status", "TEXT"),
                ("raw_ocr_text", "TEXT"),
                ("extraction_json", "TEXT"),
                ("result_json", "TEXT"),
                ("page_count", "INTEGER"),
                ("ocr_status", "TEXT"),
                ("final_status", "TEXT"),
            ])
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    message TEXT,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS data_import_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mapping_confirmed INTEGER NOT NULL DEFAULT 0,
                    prepared_count INTEGER NOT NULL DEFAULT 0,
                    imported_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    invalid_count INTEGER NOT NULL DEFAULT 0,
                    duplicate_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_goods_receipts_po ON goods_receipts(po_number)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_purchase_orders_vendor ON purchase_orders(vendor)"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_purchase_orders_source_id ON purchase_orders(data_source, source_record_id) WHERE source_record_id IS NOT NULL"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_goods_receipts_source_id ON goods_receipts(data_source, source_record_id) WHERE source_record_id IS NOT NULL"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_verified_invoices_source_id ON verified_invoices(data_source, source_record_id) WHERE source_record_id IS NOT NULL"
            )
            conn.commit()
        finally:
            conn.close()

    def insert_demo_data(self):
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO purchase_orders
                (po_number, vendor, quantity, unit_price, amount, status, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("PO500", "ABC Traders", 10, 100.0, 1000.0, "APPROVED", "DEMO"),
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO goods_receipts
                (receipt_number, po_number, quantity, received_on, data_source)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("GR500", "PO500", 10, "2026-09-30", "DEMO"),
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO verified_invoices
                (invoice_number, vendor, po_number, quantity, unit_price, amount, status, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("AI001", "ABC Traders", "PO500", 10, 100.0, 1000.0, "PASSED", "DEMO"),
            )
            cursor.execute(
                """
                INSERT OR IGNORE INTO verified_invoices
                (invoice_number, vendor, po_number, quantity, unit_price, amount, status, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("AI002", "ABC Traders", "PO500", 10, 100.0, 1000.0, "PASSED", "DEMO"),
            )
            conn.commit()
        finally:
            conn.close()

    def log_event(self, event_type: str, message: str, details: Any | None = None):
        conn = self.connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (event_type, message, details) VALUES (?, ?, ?)",
                (event_type, message, json.dumps(details) if details is not None else None),
            )
            conn.commit()
        finally:
            conn.close()

    def invoice_exists(self, invoice_number: str):
        if not invoice_number:
            return False
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM verified_invoices WHERE invoice_number = ?",
                (invoice_number,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def get_purchase_order(self, po_number: str):
        if not po_number:
            return None
        conn = self.connect()
        try:
            row = conn.execute(
                "SELECT * FROM purchase_orders WHERE po_number = ?",
                (po_number,),
            ).fetchone()
            if not row:
                return None
            record = dict(row)
            record["line_items"] = json.loads(record["line_items_json"]) if record.get("line_items_json") else []
            return record
        finally:
            conn.close()

    def get_goods_receipts(self, po_number: str):
        if not po_number:
            return []
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM goods_receipts WHERE po_number = ? ORDER BY received_on",
                (po_number,),
            ).fetchall()
            records = [dict(row) for row in rows]
            for record in records:
                record["line_items"] = json.loads(record["line_items_json"]) if record.get("line_items_json") else []
            return records
        finally:
            conn.close()

    def save_invoice(self, invoice: dict, status: str):
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO verified_invoices
                (invoice_number, vendor, po_number, quantity, unit_price, amount, status, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.get("invoice_number"),
                    invoice.get("vendor"),
                    invoice.get("po_number"),
                    invoice.get("quantity"),
                    invoice.get("unit_price"),
                    invoice.get("amount"),
                    status,
                    "UPLOAD",
                ),
            )
            conn.commit()
            return conn.total_changes > 0
        finally:
            conn.close()

    def save_workflow_result(
        self,
        invoice: dict,
        report: dict,
        original_name: str,
        stored_name: str,
        file_path: str,
        mime_type: str,
        file_size: int,
    ):
        invoice_number = invoice.get("invoice_number")
        status = report.get("status", "INCOMPLETE")
        serialized_invoice = json.dumps(invoice, ensure_ascii=False, default=str)
        serialized_report = json.dumps(report, ensure_ascii=False, default=str)
        conn = self.connect()
        try:
            if invoice_number:
                conn.execute(
                    """
                    INSERT INTO invoices
                    (invoice_number, vendor, po_number, invoice_date, amount, currency,
                     extraction_json, verification_status, source_file)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(invoice_number) DO UPDATE SET
                        vendor = excluded.vendor,
                        po_number = excluded.po_number,
                        invoice_date = excluded.invoice_date,
                        amount = excluded.amount,
                        currency = excluded.currency,
                        extraction_json = excluded.extraction_json,
                        verification_status = excluded.verification_status,
                        source_file = excluded.source_file
                    """,
                    (
                        invoice_number,
                        invoice.get("vendor"),
                        invoice.get("po_number"),
                        invoice.get("invoice_date"),
                        invoice.get("amount", invoice.get("total_amount")),
                        invoice.get("currency"),
                        serialized_invoice,
                        status,
                        file_path,
                    ),
                )
                if invoice.get("vendor"):
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO verified_invoices
                        (invoice_number, vendor, po_number, quantity, unit_price, amount, status, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            invoice_number,
                            invoice.get("vendor"),
                            invoice.get("po_number"),
                            invoice.get("quantity"),
                            invoice.get("unit_price"),
                            invoice.get("amount", invoice.get("total_amount")),
                            status,
                            "UPLOAD",
                        ),
                    )

            for check in report.get("checks", []):
                conn.execute(
                    """
                    INSERT INTO verification_results
                    (invoice_number, check_name, check_key, status, expected_value,
                     actual_value, explanation, evidence, severity)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice_number,
                        check.get("name"),
                        check.get("key"),
                        check.get("status"),
                        json.dumps(check.get("expected"), ensure_ascii=False, default=str),
                        json.dumps(check.get("actual"), ensure_ascii=False, default=str),
                        check.get("explanation"),
                        check.get("evidence"),
                        check.get("severity"),
                    ),
                )

            conn.execute(
                """
                INSERT INTO uploaded_documents
                (original_name, stored_name, file_path, mime_type, file_size,
                 invoice_number, status, raw_ocr_text, extraction_json, result_json,
                 page_count, ocr_status, final_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    original_name,
                    stored_name,
                    file_path,
                    mime_type,
                    file_size,
                    invoice_number,
                    status,
                    invoice.get("raw_ocr_text", ""),
                    serialized_invoice,
                    serialized_report,
                    invoice.get("page_count", 0),
                    invoice.get("ocr_status", "NOT_REQUIRED"),
                    status,
                ),
            )
            conn.execute(
                "INSERT INTO audit_logs (event_type, message, details) VALUES (?, ?, ?)",
                (
                    "invoice_workflow",
                    f"Invoice workflow completed with status {status}",
                    json.dumps({"invoice_number": invoice_number, "source_file": file_path, "ocr_status": invoice.get("ocr_status")}),
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_invoice_record(self, invoice_number: str):
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM invoices WHERE invoice_number = ?", (invoice_number,)).fetchone()
            if row is None:
                return None
            record = dict(row)
            record["extraction"] = json.loads(record["extraction_json"]) if record.get("extraction_json") else {}
            return record
        finally:
            conn.close()

    def get_verification_results(self, invoice_number: str):
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM verification_results WHERE invoice_number = ? ORDER BY id",
                (invoice_number,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_upload_records(self, limit: int = 50):
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM uploaded_documents ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def save_upload_record(self, original_name: str, stored_name: str, file_path: str, mime_type: str, file_size: int, invoice_number: str | None = None, status: str = "stored"):
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT INTO uploaded_documents
                (original_name, stored_name, file_path, mime_type, file_size, invoice_number, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (original_name, stored_name, file_path, mime_type, file_size, invoice_number, status),
            )
            conn.commit()
        finally:
            conn.close()

    def list_recent_activity(self, limit: int = 10):
        conn = self.connect()
        try:
            rows = conn.execute(
                """
                SELECT verified.invoice_number, verified.status, invoices.created_at
                FROM verified_invoices AS verified
                LEFT JOIN invoices ON invoices.invoice_number = verified.invoice_number
                ORDER BY
                    CASE WHEN invoices.created_at IS NULL THEN 1 ELSE 0 END,
                    invoices.created_at DESC,
                    verified.rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def dashboard_summary(self):
        conn = self.connect()
        try:
            saved_count = conn.execute("SELECT COUNT(*) FROM verified_invoices").fetchone()[0]
            invoice_count = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
            summary = {
                "total_invoices": max(saved_count, invoice_count),
                "passed": conn.execute("SELECT COUNT(*) FROM verified_invoices WHERE status = 'PASSED'").fetchone()[0],
                "review_required": conn.execute("SELECT COUNT(*) FROM verified_invoices WHERE status = 'REVIEW REQUIRED'").fetchone()[0],
                "incomplete": conn.execute("SELECT COUNT(*) FROM invoices WHERE verification_status = 'INCOMPLETE'").fetchone()[0],
            }
            return summary
        finally:
            conn.close()

    def data_source_summary(self):
        conn = self.connect()
        try:
            summary = {}
            for table in ("purchase_orders", "goods_receipts", "verified_invoices"):
                rows = conn.execute(
                    f"SELECT data_source, COUNT(*) AS record_count FROM {table} GROUP BY data_source"
                ).fetchall()
                summary[table] = {row["data_source"]: row["record_count"] for row in rows}
            return summary
        finally:
            conn.close()

    def get_recent_import_runs(self, limit: int = 10):
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT * FROM data_import_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            records = [dict(row) for row in rows]
            for record in records:
                record["mapping_confirmed"] = bool(record["mapping_confirmed"])
            return records
        finally:
            conn.close()

    def list_recent_audit_events(self, limit: int = 10):
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT event_type, message, details, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            events = []
            for row in rows:
                try:
                    details = json.loads(row["details"]) if row["details"] else {}
                except (TypeError, json.JSONDecodeError):
                    details = {}
                events.append({
                    "event_type": row["event_type"],
                    "message": row["message"],
                    "created_at": row["created_at"],
                    "invoice_number": details.get("invoice_number"),
                    "decision": details.get("decision"),
                })
            return events
        finally:
            conn.close()

    def save_review_decision(self, invoice_number: str, decision: str, reviewer: str, notes: str):
        conn = self.connect()
        try:
            conn.execute(
                "INSERT INTO review_decisions (invoice_number, decision, reviewer, notes) VALUES (?, ?, ?, ?)",
                (invoice_number, decision, reviewer, notes),
            )
            conn.commit()
        finally:
            conn.close()

    def record_review_decision(self, invoice_number: str, decision: str, reviewer: str, notes: str):
        values = {
            "invoice_number": invoice_number,
            "decision": decision,
            "reviewer": reviewer,
            "notes": notes,
        }
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise ValueError("invoice number, decision, reviewer, and notes are required")

        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "INSERT INTO review_decisions (invoice_number, decision, reviewer, notes) VALUES (?, ?, ?, ?)",
                tuple(value.strip() for value in values.values()),
            )
            conn.execute(
                "INSERT INTO audit_logs (event_type, message, details) VALUES (?, ?, ?)",
                (
                    "review_decision",
                    "Human reviewer recorded an invoice review decision",
                    json.dumps({
                        "invoice_number": invoice_number.strip(),
                        "decision": decision.strip(),
                        "reviewer": reviewer.strip(),
                    }),
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_review_history(self, invoice_number: str | None = None):
        conn = self.connect()
        try:
            if invoice_number:
                rows = conn.execute(
                    "SELECT * FROM review_decisions WHERE invoice_number = ? ORDER BY created_at DESC",
                    (invoice_number,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM review_decisions ORDER BY created_at DESC"
                ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add_purchase_order(self, po: dict):
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO purchase_orders
                (po_number, vendor, quantity, unit_price, amount, line_items_json, status,
                 data_source, source_record_id, source_provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    po.get("po_number"),
                    po.get("vendor"),
                    po.get("quantity"),
                    po.get("unit_price"),
                    po.get("amount"),
                    json.dumps(po.get("line_items"), ensure_ascii=False) if po.get("line_items") is not None else None,
                    po.get("status", "APPROVED"),
                    po.get("data_source", "LEGACY"),
                    po.get("source_record_id"),
                    json.dumps(po.get("source_provenance"), ensure_ascii=False) if po.get("source_provenance") is not None else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def add_goods_receipt(self, receipt: dict):
        conn = self.connect()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO goods_receipts
                (receipt_number, po_number, quantity, received_on, line_items_json,
                 data_source, source_record_id, source_provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt.get("receipt_number"),
                    receipt.get("po_number"),
                    receipt.get("quantity"),
                    receipt.get("received_on"),
                    json.dumps(receipt.get("line_items"), ensure_ascii=False) if receipt.get("line_items") is not None else None,
                    receipt.get("data_source", "LEGACY"),
                    receipt.get("source_record_id"),
                    json.dumps(receipt.get("source_provenance"), ensure_ascii=False) if receipt.get("source_provenance") is not None else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all_purchase_orders(self):
        conn = self.connect()
        try:
            rows = conn.execute("SELECT * FROM purchase_orders ORDER BY po_number").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def get_all_goods_receipts(self):
        conn = self.connect()
        try:
            rows = conn.execute("SELECT * FROM goods_receipts ORDER BY receipt_number").fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
