"""Safe import boundary for already-normalized PayGard reference records.

This module intentionally does not parse Aczen files. A future source adapter must
map the actual source into this PayGard-shaped contract and identify any fields
that remain unmapped before persistence is enabled.
"""

import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .config import DB_PATH
from .database import DatabaseManager


class LiveDatabaseWriteDisabled(RuntimeError):
    """Raised when a caller tries to import into the configured live database."""


class SourceMappingNotConfirmed(RuntimeError):
    """Raised when ACZEN records are persisted before their source mapping is reviewed."""


def _decimal(value: Any, field: str, *, allow_zero: bool = True) -> tuple[Decimal | None, str | None]:
    if value is None or isinstance(value, bool):
        return None, f"{field} is required and must be numeric"
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None, f"{field} is not a valid decimal amount"
    if not amount.is_finite():
        return None, f"{field} must be finite"
    if amount < 0 or (amount == 0 and not allow_zero):
        comparison = "greater than zero" if not allow_zero else "zero or greater"
        return None, f"{field} must be {comparison}"
    return amount, None


def _text(value: Any, field: str) -> tuple[str | None, str | None]:
    if not isinstance(value, str) or not value.strip():
        return None, f"{field} is required and must be non-empty text"
    return value.strip(), None


def _source_metadata(record: dict[str, Any], source: str) -> tuple[dict[str, Any] | None, str | None]:
    source_id = record.get("source_record_id")
    if source_id is not None and (not isinstance(source_id, str) or not source_id.strip()):
        return None, "source_record_id must be non-empty text when supplied"

    provenance = record.get("source_provenance")
    if provenance is not None and not isinstance(provenance, dict):
        return None, "source_provenance must be an object when supplied"
    unmapped = record.get("unmapped_fields", [])
    if not isinstance(unmapped, list) or any(not isinstance(field, str) or not field.strip() for field in unmapped):
        return None, "unmapped_fields must be a list of non-empty field names"
    if unmapped:
        return None, f"unmapped source fields require an explicit mapping: {', '.join(unmapped)}"

    try:
        provenance_json = json.dumps(provenance, ensure_ascii=False, allow_nan=False) if provenance is not None else None
    except (TypeError, ValueError):
        return None, "source_provenance must contain JSON-compatible values"
    return {
        "data_source": source,
        "source_record_id": source_id.strip() if source_id is not None else None,
        "source_provenance": provenance,
        "source_provenance_json": provenance_json,
    }, None


def _normalize_line_items(
    value: Any,
    field: str,
    *,
    require_unit_price: bool = True,
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if value is None:
        return None, None
    if not isinstance(value, list) or not value:
        return None, f"{field} must be a non-empty list when supplied"
    normalized = []
    for index, item in enumerate(value):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            return None, f"{prefix} must be an object"
        unknown = set(item) - {"description", "quantity", "unit_price", "line_total", "item"}
        if unknown:
            return None, f"{prefix} has unmapped fields: {', '.join(sorted(unknown))}"
        description, error = _text(item.get("description", item.get("item")), f"{prefix}.description")
        if error:
            return None, error
        quantity, error = _decimal(item.get("quantity"), f"{prefix}.quantity", allow_zero=False)
        if error:
            return None, error
        price = None
        if require_unit_price or item.get("unit_price") is not None:
            price, error = _decimal(item.get("unit_price"), f"{prefix}.unit_price")
            if error:
                return None, error
        line_total = None
        if item.get("line_total") is not None:
            line_total, error = _decimal(item["line_total"], f"{prefix}.line_total")
            if error:
                return None, error
        normalized.append({
            "description": description,
            "quantity": float(quantity),
            "unit_price": float(price) if price is not None else None,
            "line_total": float(line_total) if line_total is not None else None,
        })
    return normalized, None


def _normalize_purchase_order(record: Any, source: str) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(record, dict):
        return None, "record must be an object"
    allowed = {
        "po_number", "vendor", "status", "quantity", "unit_price", "amount",
        "line_items", "source_record_id", "source_provenance", "unmapped_fields",
    }
    unknown = set(record) - allowed
    if unknown:
        return None, f"unmapped fields require an explicit mapping: {', '.join(sorted(unknown))}"

    po_number, error = _text(record.get("po_number"), "po_number")
    if error:
        return None, error
    vendor, error = _text(record.get("vendor"), "vendor")
    if error:
        return None, error
    status, error = _text(record.get("status"), "status")
    if error:
        return None, error
    status = status.upper()
    if status != "APPROVED":
        return None, f"status '{status}' is not the normalized PayGard status APPROVED"

    line_items, error = _normalize_line_items(record.get("line_items"), "line_items")
    if error:
        return None, error
    amount, error = _decimal(record.get("amount"), "amount")
    if error:
        return None, error

    quantity = None
    unit_price = None
    if record.get("quantity") is not None or record.get("unit_price") is not None:
        quantity, error = _decimal(record.get("quantity"), "quantity", allow_zero=False)
        if error:
            return None, error
        unit_price, error = _decimal(record.get("unit_price"), "unit_price")
        if error:
            return None, error
    elif line_items is None:
        return None, "provide quantity and unit_price or line_items"

    metadata, error = _source_metadata(record, source)
    if error:
        return None, error
    return {
        "po_number": po_number,
        "vendor": vendor,
        "status": status,
        "quantity": float(quantity) if quantity is not None else None,
        "unit_price": float(unit_price) if unit_price is not None else None,
        "amount": float(amount),
        "line_items": line_items,
        **metadata,
    }, None


def _normalize_date(value: Any) -> tuple[str | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, datetime):
        return value.date().isoformat(), None
    if isinstance(value, date):
        return value.isoformat(), None
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()).isoformat(), None
        except ValueError:
            return None, "received_on must be an ISO date (YYYY-MM-DD)"
    return None, "received_on must be a date or ISO date string"


def _normalize_receipt(record: Any, source: str) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(record, dict):
        return None, "record must be an object"
    allowed = {
        "receipt_number", "po_number", "quantity", "received_on", "line_items",
        "source_record_id", "source_provenance", "unmapped_fields",
    }
    unknown = set(record) - allowed
    if unknown:
        return None, f"unmapped fields require an explicit mapping: {', '.join(sorted(unknown))}"

    receipt_number, error = _text(record.get("receipt_number"), "receipt_number")
    if error:
        return None, error
    po_number, error = _text(record.get("po_number"), "po_number")
    if error:
        return None, error
    quantity, error = _decimal(record.get("quantity"), "quantity", allow_zero=False)
    if error:
        return None, error
    received_on, error = _normalize_date(record.get("received_on"))
    if error:
        return None, error
    line_items, error = _normalize_line_items(
        record.get("line_items"),
        "line_items",
        require_unit_price=False,
    )
    if error:
        return None, error
    metadata, error = _source_metadata(record, source)
    if error:
        return None, error
    return {
        "receipt_number": receipt_number,
        "po_number": po_number,
        "quantity": float(quantity),
        "received_on": received_on,
        "line_items": line_items,
        **metadata,
    }, None


def _append_issue(issues: list[dict[str, Any]], entity: str, index: int, reason: str, category: str) -> None:
    issues.append({"entity": entity, "record_index": index, "reason": reason, "category": category})


def import_normalized_records(
    records: dict[str, Any],
    *,
    source: str,
    database: DatabaseManager | None = None,
    persist: bool = False,
    mapping_confirmed: bool = False,
    allow_live_database: bool = False,
) -> dict[str, Any]:
    """Validate canonical PayGard PO/receipt records; persist only by explicit opt-in.

    Source-specific files and field mappings belong in a separate adapter. This
    function accepts only PayGard's normalized field names and preserves supplied
    source IDs/provenance without interpreting them.
    """
    if not isinstance(records, dict):
        raise TypeError("records must be an object with purchase_orders and goods_receipts lists")
    source_name, source_error = _text(source, "source")
    if source_error:
        raise ValueError(source_error)
    source_name = source_name.upper()
    unknown_collections = set(records) - {"purchase_orders", "goods_receipts"}
    if unknown_collections:
        raise ValueError(f"Unsupported normalized collections: {', '.join(sorted(unknown_collections))}")

    issues: list[dict[str, Any]] = []
    normalized: dict[str, list[dict[str, Any]]] = {"purchase_orders": [], "goods_receipts": []}
    duplicate_count = 0
    invalid_count = 0
    seen_keys: dict[str, set[str]] = {"purchase_orders": set(), "goods_receipts": set()}
    seen_source_ids: dict[str, set[str]] = {"purchase_orders": set(), "goods_receipts": set()}

    for entity, validator, key_name in (
        ("purchase_orders", _normalize_purchase_order, "po_number"),
        ("goods_receipts", _normalize_receipt, "receipt_number"),
    ):
        entity_records = records.get(entity, [])
        if not isinstance(entity_records, list):
            invalid_count += 1
            _append_issue(issues, entity, -1, "collection must be a list", "invalid")
            continue
        for index, record in enumerate(entity_records):
            normalized_record, error = validator(record, source_name)
            if error:
                invalid_count += 1
                _append_issue(issues, entity, index, error, "invalid")
                continue
            record_key = normalized_record[key_name]
            source_id = normalized_record["source_record_id"]
            if record_key in seen_keys[entity] or (source_id is not None and source_id in seen_source_ids[entity]):
                duplicate_count += 1
                _append_issue(issues, entity, index, "duplicate normalized identifier in this batch", "duplicate")
                continue
            seen_keys[entity].add(record_key)
            if source_id is not None:
                seen_source_ids[entity].add(source_id)
            normalized[entity].append(normalized_record)

    valid_po_numbers = {record["po_number"] for record in normalized["purchase_orders"]}
    valid_receipts = []
    for index, receipt in enumerate(normalized["goods_receipts"]):
        if receipt["po_number"] not in valid_po_numbers:
            invalid_count += 1
            _append_issue(
                issues,
                "goods_receipts",
                index,
                "PO reference is not present in the valid normalized purchase-order batch",
                "invalid",
            )
            continue
        valid_receipts.append(receipt)
    normalized["goods_receipts"] = valid_receipts

    result = {
        "source": source_name,
        "persisted": False,
        "imported": 0,
        "prepared": sum(len(items) for items in normalized.values()),
        "skipped": 0,
        "invalid": invalid_count,
        "duplicate": duplicate_count,
        "issues": issues,
        "records": normalized,
    }
    if not persist:
        return result
    if database is None:
        raise ValueError("database must be provided when persist=True")
    if source_name == "ACZEN" and not mapping_confirmed:
        raise SourceMappingNotConfirmed(
            "ACZEN persistence requires reviewed source fields and business rules; keep preview mode enabled until mapping is confirmed."
        )

    target_path = Path(database.db_path).expanduser().resolve()
    live_path = Path(DB_PATH).expanduser().resolve()
    if target_path == live_path and not allow_live_database:
        raise LiveDatabaseWriteDisabled(
            "Import into the configured live database is disabled; use a temporary database or explicitly enable live writes after source mapping is confirmed."
        )

    prepared_count = result["prepared"]
    database.setup_database()
    connection = database.connect()
    blocked_po_numbers: set[str] = set()
    inserted_po_numbers: set[str] = set()
    try:
        for record in normalized["purchase_orders"]:
            existing_key = connection.execute(
                "SELECT data_source, source_record_id, vendor, status, quantity, unit_price, amount, line_items_json "
                "FROM purchase_orders WHERE po_number = ?",
                (record["po_number"],),
            ).fetchone()
            existing_source_id = None
            if record["source_record_id"] is not None:
                existing_source_id = connection.execute(
                    "SELECT po_number FROM purchase_orders WHERE data_source = ? AND source_record_id = ?",
                    (source_name, record["source_record_id"]),
                ).fetchone()
            if existing_key or existing_source_id:
                duplicate_count += 1
                if existing_key:
                    existing_lines = json.loads(existing_key["line_items_json"]) if existing_key["line_items_json"] else None
                    business_fields_match = all(
                        existing_key[field] == record[field]
                        for field in ("vendor", "status", "quantity", "unit_price", "amount")
                    ) and existing_lines == record["line_items"]
                    same_source_record = (
                        existing_key["data_source"] == source_name
                        and existing_key["source_record_id"] == record["source_record_id"]
                    )
                    if not (same_source_record and business_fields_match):
                        blocked_po_numbers.add(record["po_number"])
                if existing_source_id and existing_source_id["po_number"] != record["po_number"]:
                    blocked_po_numbers.add(record["po_number"])
                _append_issue(issues, "purchase_orders", -1, f"PO key or source ID already exists; existing data was not overwritten: {record['po_number']}", "duplicate")
                continue
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO purchase_orders
                (po_number, vendor, quantity, unit_price, amount, line_items_json, status,
                 data_source, source_record_id, source_provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["po_number"],
                    record["vendor"],
                    record["quantity"],
                    record["unit_price"],
                    record["amount"],
                    json.dumps(record["line_items"], ensure_ascii=False) if record["line_items"] is not None else None,
                    record["status"],
                    source_name,
                    record["source_record_id"],
                    record["source_provenance_json"],
                ),
            )
            if cursor.rowcount:
                result["imported"] += 1
                inserted_po_numbers.add(record["po_number"])
            else:
                duplicate_count += 1
                blocked_po_numbers.add(record["po_number"])
                _append_issue(issues, "purchase_orders", -1, f"PO key conflicts with existing data and was not overwritten: {record['po_number']}", "duplicate")

        for record in normalized["goods_receipts"]:
            if record["po_number"] in blocked_po_numbers:
                result["skipped"] += 1
                _append_issue(issues, "goods_receipts", -1, f"receipt not imported because its PO key conflicted: {record['po_number']}", "skipped")
                continue
            existing_po = connection.execute(
                "SELECT data_source FROM purchase_orders WHERE po_number = ?",
                (record["po_number"],),
            ).fetchone()
            if not existing_po or (record["po_number"] not in inserted_po_numbers and existing_po["data_source"] != source_name):
                result["skipped"] += 1
                _append_issue(issues, "goods_receipts", -1, f"receipt PO reference is missing or belongs to another data source: {record['po_number']}", "skipped")
                continue
            existing_key = connection.execute(
                "SELECT data_source, source_record_id FROM goods_receipts WHERE receipt_number = ?",
                (record["receipt_number"],),
            ).fetchone()
            existing_source_id = None
            if record["source_record_id"] is not None:
                existing_source_id = connection.execute(
                    "SELECT receipt_number FROM goods_receipts WHERE data_source = ? AND source_record_id = ?",
                    (source_name, record["source_record_id"]),
                ).fetchone()
            if existing_key or existing_source_id:
                duplicate_count += 1
                _append_issue(issues, "goods_receipts", -1, f"receipt key or source ID already exists; existing data was not overwritten: {record['receipt_number']}", "duplicate")
                continue
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO goods_receipts
                (receipt_number, po_number, quantity, received_on, line_items_json,
                 data_source, source_record_id, source_provenance_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["receipt_number"],
                    record["po_number"],
                    record["quantity"],
                    record["received_on"],
                    json.dumps(record["line_items"], ensure_ascii=False) if record["line_items"] is not None else None,
                    source_name,
                    record["source_record_id"],
                    record["source_provenance_json"],
                ),
            )
            if cursor.rowcount:
                result["imported"] += 1
            else:
                duplicate_count += 1
                _append_issue(issues, "goods_receipts", -1, f"receipt key conflicts with existing data and was not overwritten: {record['receipt_number']}", "duplicate")

        run_status = "COMPLETED_WITH_ISSUES" if result["skipped"] or invalid_count or duplicate_count else "COMPLETED"
        run_cursor = connection.execute(
            """
            INSERT INTO data_import_runs
            (source, status, mapping_confirmed, prepared_count, imported_count,
             skipped_count, invalid_count, duplicate_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_name,
                run_status,
                int(mapping_confirmed),
                prepared_count,
                result["imported"],
                result["skipped"],
                invalid_count,
                duplicate_count,
            ),
        )
        result["import_run_id"] = run_cursor.lastrowid
        result["status"] = run_status
        connection.commit()
    except (sqlite3.Error, TypeError, ValueError):
        connection.rollback()
        raise
    finally:
        connection.close()

    result["persisted"] = True
    result["prepared"] = 0
    result["duplicate"] = duplicate_count
    return result