from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path

from app.models.schemas import (
    INVENTORY_ITEMS_TABLE,
    INVENTORY_MOVEMENTS_TABLE,
    PROJECTS_TABLE,
    PURCHASE_REQUESTS_TABLE,
    PURCHASE_REQUEST_EVENTS_TABLE,
    TABLE_SCHEMAS,
    USERS_TABLE,
    VENDORS_TABLE,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
TEST_TMP_DIR = ROOT_DIR / ".test_tmp"


def write_table(data_dir: Path, table_name: str, rows: list[dict[str, str]]) -> None:
    path = data_dir / table_name
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TABLE_SCHEMAS[table_name])
        writer.writeheader()
        writer.writerows(rows)


def create_empty_dataset(data_dir: Path) -> None:
    for table_name in TABLE_SCHEMAS:
        write_table(data_dir, table_name, [])


def make_test_dir() -> Path:
    TEST_TMP_DIR.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=TEST_TMP_DIR))


def remove_test_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def create_sample_dataset(
    data_dir: Path,
    *,
    inventory_items: list[dict[str, str]] | None = None,
    inventory_movements: list[dict[str, str]] | None = None,
    purchase_requests: list[dict[str, str]] | None = None,
    purchase_request_events: list[dict[str, str]] | None = None,
) -> None:
    create_empty_dataset(data_dir)

    write_table(
        data_dir,
        USERS_TABLE,
        [
            {
                "user_id": "USR-001",
                "slack_user_id": "U_REQ",
                "full_name": "Alice Requester",
                "team": "Operations",
                "email": "alice@example.com",
                "role": "requester",
                "status": "active",
            },
            {
                "user_id": "USR-002",
                "slack_user_id": "U_BUY",
                "full_name": "Bob Buyer",
                "team": "Procurement",
                "email": "bob@example.com",
                "role": "purchaser",
                "status": "active",
            },
        ],
    )
    write_table(
        data_dir,
        PROJECTS_TABLE,
        [
            {
                "project_id": "PRJ-001",
                "project_name": "Main Lab",
                "project_owner_user_id": "USR-001",
                "project_owner_name": "Alice Requester",
                "cost_center": "CC-1001",
                "status": "active",
                "notes": "",
            }
        ],
    )
    write_table(
        data_dir,
        VENDORS_TABLE,
        [
            {
                "vendor_id": "VND-001",
                "vendor_name": "Acme Supplies",
                "contact_name": "Pat Vendor",
                "email": "vendor@example.com",
                "phone": "+1-555-0100",
                "website": "https://acme.example",
                "default_currency": "USD",
                "status": "active",
                "notes": "",
            }
        ],
    )
    write_table(data_dir, INVENTORY_ITEMS_TABLE, inventory_items or [])
    write_table(data_dir, INVENTORY_MOVEMENTS_TABLE, inventory_movements or [])
    write_table(data_dir, PURCHASE_REQUESTS_TABLE, purchase_requests or [])
    write_table(
        data_dir,
        PURCHASE_REQUEST_EVENTS_TABLE,
        purchase_request_events or [],
    )
