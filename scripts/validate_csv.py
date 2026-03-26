from __future__ import annotations

import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

SCHEMAS = {
    "users.csv": [
        "user_id",
        "slack_user_id",
        "full_name",
        "team",
        "email",
        "role",
        "status",
    ],
    "projects.csv": [
        "project_id",
        "project_name",
        "project_owner_user_id",
        "project_owner_name",
        "cost_center",
        "status",
        "notes",
    ],
    "vendors.csv": [
        "vendor_id",
        "vendor_name",
        "contact_name",
        "email",
        "phone",
        "website",
        "default_currency",
        "status",
        "notes",
    ],
    "inventory_items.csv": [
        "item_id",
        "item_name",
        "category",
        "description",
        "unit",
        "quantity_on_hand",
        "reorder_point",
        "preferred_vendor_id",
        "vendor_sku",
        "storage_location",
        "last_counted_at",
        "status",
        "notes",
    ],
    "inventory_movements.csv": [
        "movement_id",
        "item_id",
        "movement_type",
        "quantity",
        "unit",
        "related_request_id",
        "performed_by_user_id",
        "performed_by_name",
        "performed_at",
        "storage_location",
        "notes",
    ],
    "purchase_requests.csv": [
        "request_id",
        "requested_at",
        "requested_by_user_id",
        "requested_by_name",
        "project_id",
        "project_name",
        "item_name",
        "item_description",
        "quantity_requested",
        "unit",
        "vendor_id",
        "vendor_name",
        "vendor_sku",
        "needed_by",
        "justification",
        "request_status",
        "purchasing_outcome",
        "purchaser_user_id",
        "purchaser_name",
        "purchased_quantity",
        "estimated_unit_price",
        "actual_unit_price",
        "po_number",
        "ordered_at",
        "received_at",
        "inventory_item_id",
        "notes",
    ],
    "purchase_request_events.csv": [
        "event_id",
        "request_id",
        "event_at",
        "actor_user_id",
        "actor_name",
        "event_type",
        "old_status",
        "new_status",
        "details",
    ],
}

UNIQUE_ID_FIELDS = {
    "users.csv": "user_id",
    "projects.csv": "project_id",
    "vendors.csv": "vendor_id",
    "inventory_items.csv": "item_id",
    "inventory_movements.csv": "movement_id",
    "purchase_requests.csv": "request_id",
    "purchase_request_events.csv": "event_id",
}

REQUIRED_NON_EMPTY = {
    "users.csv": {"user_id", "slack_user_id", "full_name", "role", "status"},
    "projects.csv": {
        "project_id",
        "project_name",
        "project_owner_user_id",
        "project_owner_name",
        "status",
    },
    "vendors.csv": {"vendor_id", "vendor_name", "default_currency", "status"},
    "inventory_items.csv": {
        "item_id",
        "item_name",
        "unit",
        "quantity_on_hand",
        "reorder_point",
        "status",
    },
    "inventory_movements.csv": {
        "movement_id",
        "item_id",
        "movement_type",
        "quantity",
        "unit",
        "performed_by_user_id",
        "performed_by_name",
        "performed_at",
    },
    "purchase_requests.csv": {
        "request_id",
        "requested_at",
        "requested_by_user_id",
        "requested_by_name",
        "project_id",
        "project_name",
        "item_name",
        "quantity_requested",
        "unit",
        "request_status",
    },
    "purchase_request_events.csv": {
        "event_id",
        "request_id",
        "event_at",
        "actor_user_id",
        "actor_name",
        "event_type",
    },
}

ALLOWED_VALUES = {
    ("users.csv", "role"): {"requester", "purchaser", "admin"},
    ("users.csv", "status"): {"active", "inactive"},
    ("projects.csv", "status"): {"active", "on_hold", "closed"},
    ("vendors.csv", "status"): {"active", "inactive"},
    ("inventory_items.csv", "status"): {"active", "discontinued", "archived"},
    (
        "inventory_movements.csv",
        "movement_type",
    ): {"receive", "consume", "adjust_add", "adjust_remove", "reserve", "unreserve"},
    (
        "purchase_requests.csv",
        "request_status",
    ): {"requested", "approved", "ordering", "ordered", "received", "rejected", "cancelled"},
    (
        "purchase_requests.csv",
        "purchasing_outcome",
    ): {"pending", "approved", "completed", "partially_received", "rejected", "cancelled"},
    (
        "purchase_request_events.csv",
        "event_type",
    ): {
        "request_created",
        "approved",
        "ordering_started",
        "ordered",
        "received",
        "rejected",
        "cancelled",
        "note_added",
    },
    (
        "purchase_request_events.csv",
        "new_status",
    ): {"requested", "approved", "ordering", "ordered", "received", "rejected", "cancelled"},
}

NUMERIC_FIELDS = {
    ("inventory_items.csv", "quantity_on_hand"),
    ("inventory_items.csv", "reorder_point"),
    ("inventory_movements.csv", "quantity"),
    ("purchase_requests.csv", "quantity_requested"),
    ("purchase_requests.csv", "purchased_quantity"),
    ("purchase_requests.csv", "estimated_unit_price"),
    ("purchase_requests.csv", "actual_unit_price"),
}

REFERENCE_CHECKS = [
    ("projects.csv", "project_owner_user_id", "users.csv", True),
    ("inventory_items.csv", "preferred_vendor_id", "vendors.csv", False),
    ("inventory_movements.csv", "item_id", "inventory_items.csv", True),
    ("inventory_movements.csv", "related_request_id", "purchase_requests.csv", False),
    ("inventory_movements.csv", "performed_by_user_id", "users.csv", True),
    ("purchase_requests.csv", "requested_by_user_id", "users.csv", True),
    ("purchase_requests.csv", "project_id", "projects.csv", True),
    ("purchase_requests.csv", "vendor_id", "vendors.csv", False),
    ("purchase_requests.csv", "purchaser_user_id", "users.csv", False),
    ("purchase_requests.csv", "inventory_item_id", "inventory_items.csv", False),
    ("purchase_request_events.csv", "request_id", "purchase_requests.csv", True),
    ("purchase_request_events.csv", "actor_user_id", "users.csv", True),
]


def load_rows(filename: str) -> tuple[list[dict[str, str]], list[str]]:
    path = DATA_DIR / filename
    errors: list[str] = []
    rows: list[dict[str, str]] = []

    if not path.exists():
        return rows, [f"{filename}: file is missing"]

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        expected = SCHEMAS[filename]

        missing = [column for column in expected if column not in headers]
        extra = [column for column in headers if column not in expected]

        if missing:
            errors.append(f"{filename}: missing columns: {', '.join(missing)}")
        if extra:
            errors.append(f"{filename}: unexpected columns: {', '.join(extra)}")

        for row in reader:
            cleaned = {}
            for key, value in row.items():
                if key is None:
                    continue
                cleaned[key] = (value or "").strip()
            rows.append(cleaned)

    return rows, errors


def validate_required_fields(
    rows_by_file: dict[str, list[dict[str, str]]],
) -> list[str]:
    errors: list[str] = []

    for filename, required_fields in REQUIRED_NON_EMPTY.items():
        for line_number, row in enumerate(rows_by_file.get(filename, []), start=2):
            for field in required_fields:
                if not row.get(field, ""):
                    errors.append(f"{filename}:{line_number}: {field} must not be empty")

    return errors


def validate_unique_ids(rows_by_file: dict[str, list[dict[str, str]]]) -> list[str]:
    errors: list[str] = []

    for filename, id_field in UNIQUE_ID_FIELDS.items():
        seen: dict[str, int] = {}
        for line_number, row in enumerate(rows_by_file.get(filename, []), start=2):
            value = row.get(id_field, "")
            if not value:
                errors.append(f"{filename}:{line_number}: {id_field} must not be empty")
                continue
            if value in seen:
                errors.append(
                    f"{filename}:{line_number}: duplicate {id_field} '{value}' first seen on line {seen[value]}"
                )
                continue
            seen[value] = line_number

    return errors


def validate_allowed_values(
    rows_by_file: dict[str, list[dict[str, str]]],
) -> list[str]:
    errors: list[str] = []

    for (filename, field), allowed in ALLOWED_VALUES.items():
        for line_number, row in enumerate(rows_by_file.get(filename, []), start=2):
            value = row.get(field, "")
            if value and value not in allowed:
                allowed_text = ", ".join(sorted(allowed))
                errors.append(
                    f"{filename}:{line_number}: {field} has invalid value '{value}' (allowed: {allowed_text})"
                )

    return errors


def validate_numeric_fields(
    rows_by_file: dict[str, list[dict[str, str]]],
) -> list[str]:
    errors: list[str] = []

    for filename, field in NUMERIC_FIELDS:
        for line_number, row in enumerate(rows_by_file.get(filename, []), start=2):
            value = row.get(field, "")
            if not value:
                continue
            try:
                number = Decimal(value)
            except InvalidOperation:
                errors.append(f"{filename}:{line_number}: {field} must be numeric")
                continue
            if number < 0:
                errors.append(f"{filename}:{line_number}: {field} must be zero or greater")

    return errors


def validate_references(
    rows_by_file: dict[str, list[dict[str, str]]],
) -> list[str]:
    errors: list[str] = []
    valid_ids: dict[str, set[str]] = defaultdict(set)

    for filename, id_field in UNIQUE_ID_FIELDS.items():
        valid_ids[filename] = {
            row.get(id_field, "") for row in rows_by_file.get(filename, []) if row.get(id_field, "")
        }

    for from_file, field, target_file, required in REFERENCE_CHECKS:
        target_ids = valid_ids.get(target_file, set())
        for line_number, row in enumerate(rows_by_file.get(from_file, []), start=2):
            value = row.get(field, "")
            if not value:
                if required:
                    errors.append(f"{from_file}:{line_number}: {field} must not be empty")
                continue
            if value not in target_ids:
                errors.append(
                    f"{from_file}:{line_number}: {field} references missing value '{value}' in {target_file}"
                )

    return errors


def validate_request_workflow_rules(
    rows_by_file: dict[str, list[dict[str, str]]],
) -> list[str]:
    errors: list[str] = []

    for line_number, row in enumerate(rows_by_file.get("purchase_requests.csv", []), start=2):
        status = row.get("request_status", "")

        if status in {"ordering", "ordered", "received"} and not row.get("purchaser_user_id", ""):
            errors.append(
                f"purchase_requests.csv:{line_number}: purchaser_user_id is required when status is {status}"
            )

        if status in {"ordered", "received"} and not row.get("ordered_at", ""):
            errors.append(f"purchase_requests.csv:{line_number}: ordered_at is required when status is {status}")

        if status == "received" and not row.get("received_at", ""):
            errors.append(
                f"purchase_requests.csv:{line_number}: received_at is required when status is received"
            )

    return errors


def main() -> int:
    rows_by_file: dict[str, list[dict[str, str]]] = {}
    errors: list[str] = []

    for filename in SCHEMAS:
        rows, load_errors = load_rows(filename)
        rows_by_file[filename] = rows
        errors.extend(load_errors)

    errors.extend(validate_required_fields(rows_by_file))
    errors.extend(validate_unique_ids(rows_by_file))
    errors.extend(validate_allowed_values(rows_by_file))
    errors.extend(validate_numeric_fields(rows_by_file))
    errors.extend(validate_references(rows_by_file))
    errors.extend(validate_request_workflow_rules(rows_by_file))

    if errors:
        print("CSV validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CSV validation passed.")
    for filename in SCHEMAS:
        print(f"- {filename}: {len(rows_by_file.get(filename, []))} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
