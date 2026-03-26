from __future__ import annotations

import unittest

from app.models.schemas import PurchaseRequestInput, ReceiveInventoryInput
from app.services.errors import ValidationError
from app.services.inventory_service import InventoryService
from app.services.purchasing_service import PurchasingService
from app.storage.csv_store import CSVStore
from tests.support import create_sample_dataset, make_test_dir, remove_test_dir


class PurchasingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data_dir = make_test_dir()
        create_sample_dataset(self.data_dir)
        self.store = CSVStore(self.data_dir)
        self.service = PurchasingService(self.store)

    def tearDown(self) -> None:
        remove_test_dir(self.data_dir)

    def test_create_request_writes_request_and_event(self) -> None:
        created = self.service.create_request(
            PurchaseRequestInput(
                requested_by_slack_user_id="U_REQ",
                project_id="PRJ-001",
                item_name="USB-C Cable",
                item_description="1 meter cable",
                quantity_requested="5",
                unit="each",
                vendor_id="VND-001",
                needed_by="2026-04-15",
                justification="New workstation setup",
                estimated_unit_price="9.99",
            )
        )

        self.assertEqual(created["request_id"], "REQ-001")
        self.assertEqual(created["request_status"], "requested")
        self.assertEqual(created["vendor_name"], "Acme Supplies")

        request_rows = self.store.read_rows("purchase_requests.csv")
        event_rows = self.store.read_rows("purchase_request_events.csv")
        self.assertEqual(len(request_rows), 1)
        self.assertEqual(len(event_rows), 1)
        self.assertEqual(event_rows[0]["event_type"], "request_created")

    def test_update_request_status_to_ordered_records_purchaser_and_event(self) -> None:
        create_sample_dataset(
            self.data_dir,
            purchase_requests=[
                {
                    "request_id": "REQ-001",
                    "requested_at": "2026-03-26T10:00:00-07:00",
                    "requested_by_user_id": "USR-001",
                    "requested_by_name": "Alice Requester",
                    "project_id": "PRJ-001",
                    "project_name": "Main Lab",
                    "item_name": "USB-C Cable",
                    "item_description": "1 meter cable",
                    "quantity_requested": "5",
                    "unit": "each",
                    "vendor_id": "VND-001",
                    "vendor_name": "Acme Supplies",
                    "vendor_sku": "ACM-USB-C",
                    "needed_by": "2026-04-15",
                    "justification": "New workstation setup",
                    "request_status": "approved",
                    "purchasing_outcome": "approved",
                    "purchaser_user_id": "",
                    "purchaser_name": "",
                    "purchased_quantity": "",
                    "estimated_unit_price": "9.99",
                    "actual_unit_price": "",
                    "po_number": "",
                    "ordered_at": "",
                    "received_at": "",
                    "inventory_item_id": "",
                    "notes": "",
                }
            ],
            purchase_request_events=[
                {
                    "event_id": "EVT-001",
                    "request_id": "REQ-001",
                    "event_at": "2026-03-26T10:00:00-07:00",
                    "actor_user_id": "USR-001",
                    "actor_name": "Alice Requester",
                    "event_type": "approved",
                    "old_status": "requested",
                    "new_status": "approved",
                    "details": "Approved by buyer",
                }
            ],
        )
        self.store = CSVStore(self.data_dir)
        self.service = PurchasingService(self.store)

        updated = self.service.update_request_status(
            request_id="REQ-001",
            new_status="ordered",
            actor_slack_user_id="U_BUY",
            po_number="PO-123",
            purchased_quantity="5",
            notes="Submitted to vendor",
        )

        self.assertEqual(updated["request_status"], "ordered")
        self.assertEqual(updated["purchaser_user_id"], "USR-002")
        self.assertEqual(updated["po_number"], "PO-123")
        self.assertEqual(updated["purchased_quantity"], "5")
        self.assertTrue(updated["ordered_at"])

        events = self.store.read_rows("purchase_request_events.csv")
        self.assertEqual(events[-1]["event_type"], "ordered")
        self.assertEqual(events[-1]["new_status"], "ordered")

    def test_update_request_status_rejects_received_transition(self) -> None:
        create_sample_dataset(
            self.data_dir,
            purchase_requests=[
                {
                    "request_id": "REQ-001",
                    "requested_at": "2026-03-26T10:00:00-07:00",
                    "requested_by_user_id": "USR-001",
                    "requested_by_name": "Alice Requester",
                    "project_id": "PRJ-001",
                    "project_name": "Main Lab",
                    "item_name": "USB-C Cable",
                    "item_description": "",
                    "quantity_requested": "5",
                    "unit": "each",
                    "vendor_id": "VND-001",
                    "vendor_name": "Acme Supplies",
                    "vendor_sku": "",
                    "needed_by": "",
                    "justification": "Test",
                    "request_status": "ordered",
                    "purchasing_outcome": "approved",
                    "purchaser_user_id": "USR-002",
                    "purchaser_name": "Bob Buyer",
                    "purchased_quantity": "5",
                    "estimated_unit_price": "",
                    "actual_unit_price": "",
                    "po_number": "PO-123",
                    "ordered_at": "2026-03-26T11:00:00-07:00",
                    "received_at": "",
                    "inventory_item_id": "",
                    "notes": "",
                }
            ],
        )
        self.store = CSVStore(self.data_dir)
        self.service = PurchasingService(self.store)

        with self.assertRaises(ValidationError):
            self.service.update_request_status(
                request_id="REQ-001",
                new_status="received",
                actor_slack_user_id="U_BUY",
            )


class InventoryServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data_dir = make_test_dir()
        create_sample_dataset(
            self.data_dir,
            inventory_items=[
                {
                    "item_id": "INV-001",
                    "item_name": "USB-C Cable",
                    "category": "Cables",
                    "description": "1 meter cable",
                    "unit": "each",
                    "quantity_on_hand": "2",
                    "reorder_point": "5",
                    "preferred_vendor_id": "VND-001",
                    "vendor_sku": "ACM-USB-C",
                    "storage_location": "Shelf A1",
                    "last_counted_at": "2026-03-26",
                    "status": "active",
                    "notes": "",
                }
            ],
            purchase_requests=[
                {
                    "request_id": "REQ-001",
                    "requested_at": "2026-03-26T10:00:00-07:00",
                    "requested_by_user_id": "USR-001",
                    "requested_by_name": "Alice Requester",
                    "project_id": "PRJ-001",
                    "project_name": "Main Lab",
                    "item_name": "USB-C Cable",
                    "item_description": "1 meter cable",
                    "quantity_requested": "3",
                    "unit": "each",
                    "vendor_id": "VND-001",
                    "vendor_name": "Acme Supplies",
                    "vendor_sku": "ACM-USB-C",
                    "needed_by": "2026-04-15",
                    "justification": "Restock",
                    "request_status": "ordered",
                    "purchasing_outcome": "approved",
                    "purchaser_user_id": "USR-002",
                    "purchaser_name": "Bob Buyer",
                    "purchased_quantity": "3",
                    "estimated_unit_price": "9.99",
                    "actual_unit_price": "",
                    "po_number": "PO-123",
                    "ordered_at": "2026-03-26T11:00:00-07:00",
                    "received_at": "",
                    "inventory_item_id": "INV-001",
                    "notes": "",
                }
            ],
            purchase_request_events=[
                {
                    "event_id": "EVT-001",
                    "request_id": "REQ-001",
                    "event_at": "2026-03-26T11:00:00-07:00",
                    "actor_user_id": "USR-002",
                    "actor_name": "Bob Buyer",
                    "event_type": "ordered",
                    "old_status": "approved",
                    "new_status": "ordered",
                    "details": "Sent to vendor",
                }
            ],
        )
        self.store = CSVStore(self.data_dir)
        self.service = InventoryService(self.store)

    def tearDown(self) -> None:
        remove_test_dir(self.data_dir)

    def test_search_and_low_stock(self) -> None:
        search_rows = self.service.search_items("usb cable")
        low_stock_rows = self.service.low_stock_items()

        self.assertEqual(len(search_rows), 1)
        self.assertEqual(search_rows[0]["item_id"], "INV-001")
        self.assertEqual(search_rows[0]["is_low_stock"], "yes")
        self.assertEqual(len(low_stock_rows), 1)

    def test_receive_inventory_updates_request_inventory_and_movement(self) -> None:
        result = self.service.receive_inventory(
            ReceiveInventoryInput(
                request_id="REQ-001",
                actor_slack_user_id="U_BUY",
                quantity_received="3",
                actual_unit_price="8.50",
                storage_location="Shelf A1",
                notes="Received in good condition",
            )
        )

        self.assertEqual(result["request"]["request_status"], "received")
        self.assertEqual(result["request"]["purchasing_outcome"], "completed")
        self.assertEqual(result["inventory_item"]["quantity_on_hand"], "5")

        request_rows = self.store.read_rows("purchase_requests.csv")
        inventory_rows = self.store.read_rows("inventory_items.csv")
        movement_rows = self.store.read_rows("inventory_movements.csv")
        event_rows = self.store.read_rows("purchase_request_events.csv")

        self.assertEqual(request_rows[0]["actual_unit_price"], "8.5")
        self.assertEqual(request_rows[0]["inventory_item_id"], "INV-001")
        self.assertTrue(request_rows[0]["received_at"])
        self.assertEqual(inventory_rows[0]["quantity_on_hand"], "5")
        self.assertEqual(movement_rows[0]["movement_type"], "receive")
        self.assertEqual(movement_rows[0]["quantity"], "3")
        self.assertEqual(event_rows[-1]["event_type"], "received")


if __name__ == "__main__":
    unittest.main()
