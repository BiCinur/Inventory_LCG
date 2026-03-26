from __future__ import annotations

import unittest
from decimal import Decimal

from app.models.schemas import INVENTORY_ITEMS_TABLE, USERS_TABLE
from app.storage.csv_store import CSVStore
from tests.support import create_empty_dataset, make_test_dir, remove_test_dir


class CSVStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data_dir = make_test_dir()
        create_empty_dataset(self.data_dir)
        self.store = CSVStore(self.data_dir)

    def tearDown(self) -> None:
        remove_test_dir(self.data_dir)

    def test_append_read_and_next_id(self) -> None:
        self.assertEqual(self.store.next_id(USERS_TABLE), "USR-001")

        self.store.append_row(
            USERS_TABLE,
            {
                "user_id": "USR-001",
                "slack_user_id": "U_TEST",
                "full_name": "Test User",
                "team": "Ops",
                "email": "test@example.com",
                "role": "requester",
                "status": "active",
            },
        )

        rows = self.store.read_rows(USERS_TABLE)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["full_name"], "Test User")
        self.assertEqual(self.store.next_id(USERS_TABLE), "USR-002")

    def test_write_rows_formats_decimal_values(self) -> None:
        self.store.write_rows(
            INVENTORY_ITEMS_TABLE,
            [
                {
                    "item_id": "INV-001",
                    "item_name": "USB-C Cable",
                    "category": "Cables",
                    "description": "",
                    "unit": "each",
                    "quantity_on_hand": Decimal("4.500"),
                    "reorder_point": Decimal("2"),
                    "preferred_vendor_id": "",
                    "vendor_sku": "",
                    "storage_location": "Shelf A",
                    "last_counted_at": "2026-03-26",
                    "status": "active",
                    "notes": "",
                }
            ],
        )

        rows = self.store.read_rows(INVENTORY_ITEMS_TABLE)
        self.assertEqual(rows[0]["quantity_on_hand"], "4.5")
        self.assertEqual(rows[0]["reorder_point"], "2")

    def test_normalize_row_rejects_unexpected_columns(self) -> None:
        with self.assertRaises(ValueError):
            self.store.normalize_row(USERS_TABLE, {"user_id": "USR-001", "unexpected": "value"})


if __name__ == "__main__":
    unittest.main()
