from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.schemas import (
    INVENTORY_ITEMS_TABLE,
    INVENTORY_MOVEMENTS_TABLE,
    PURCHASE_REQUESTS_TABLE,
    PURCHASE_REQUEST_EVENTS_TABLE,
    ReceiveInventoryInput,
    USERS_TABLE,
    VENDORS_TABLE,
    format_decimal,
)
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.storage.csv_store import CSVStore


class InventoryService:
    def __init__(self, store: CSVStore) -> None:
        self.store = store

    def search_items(self, query: str, limit: int = 10) -> list[dict[str, str]]:
        rows = [
            row for row in self.store.read_rows(INVENTORY_ITEMS_TABLE) if row.get("status", "") == "active"
        ]
        query = query.strip().lower()

        if query:
            tokens = [token for token in query.split() if token]

            def matches(row: dict[str, str]) -> bool:
                searchable = " ".join(
                    [
                        row.get("item_id", ""),
                        row.get("item_name", ""),
                        row.get("category", ""),
                        row.get("description", ""),
                        row.get("vendor_sku", ""),
                        row.get("storage_location", ""),
                    ]
                ).lower()
                return all(token in searchable for token in tokens)

            rows = [row for row in rows if matches(row)]

        rows.sort(key=lambda row: row.get("item_name", "").lower())
        return [self._enrich_inventory_row(row) for row in rows[:limit]]

    def low_stock_items(self, limit: int = 10) -> list[dict[str, str]]:
        rows = []
        for row in self.store.read_rows(INVENTORY_ITEMS_TABLE):
            if row.get("status", "") != "active":
                continue
            quantity = self._parse_non_negative_decimal(row.get("quantity_on_hand", "0"), "quantity_on_hand")
            reorder_point = self._parse_non_negative_decimal(row.get("reorder_point", "0"), "reorder_point")
            if reorder_point > 0 and quantity <= reorder_point:
                rows.append(self._enrich_inventory_row(row))

        rows.sort(
            key=lambda row: (
                self._parse_non_negative_decimal(row.get("quantity_on_hand", "0"), "quantity_on_hand"),
                row.get("item_name", "").lower(),
            )
        )
        return rows[:limit]

    def receive_inventory(self, payload: ReceiveInventoryInput) -> dict[str, dict[str, str]]:
        actor = self._get_user_by_slack_user_id(payload.actor_slack_user_id)
        now = self._timestamp()

        with self.store.transaction():
            request_rows = self.store.read_rows(PURCHASE_REQUESTS_TABLE)
            request_index, request_row = self._find_row_index(request_rows, "request_id", payload.request_id.strip())
            if request_row is None:
                raise NotFoundError(f"Purchase request {payload.request_id} was not found.")

            current_status = request_row.get("request_status", "")
            if current_status == "received":
                raise ConflictError(f"Purchase request {payload.request_id} is already marked as received.")
            if current_status in {"rejected", "cancelled"}:
                raise ConflictError(
                    f"Purchase request {payload.request_id} is {current_status} and cannot be received."
                )

            received_quantity = self._resolve_received_quantity(request_row, payload.quantity_received)
            requested_quantity = self._parse_non_negative_decimal(
                request_row.get("quantity_requested", "0"), "quantity_requested"
            )
            actual_price = payload.actual_unit_price.strip()
            if actual_price:
                actual_price = format_decimal(
                    self._parse_non_negative_decimal(actual_price, "actual_unit_price")
                )

            inventory_rows = self.store.read_rows(INVENTORY_ITEMS_TABLE)
            item_index, inventory_item = self._find_inventory_item(inventory_rows, request_row)
            storage_location = payload.storage_location.strip()
            if not storage_location and inventory_item is not None:
                storage_location = inventory_item.get("storage_location", "")

            if inventory_item is None:
                vendor_id = request_row.get("vendor_id", "").strip()
                vendor_row = self.store.find_row(VENDORS_TABLE, "vendor_id", vendor_id) if vendor_id else None
                inventory_item = {
                    "item_id": self.store.next_id(INVENTORY_ITEMS_TABLE),
                    "item_name": request_row.get("item_name", ""),
                    "category": "",
                    "description": request_row.get("item_description", ""),
                    "unit": request_row.get("unit", ""),
                    "quantity_on_hand": format_decimal(received_quantity),
                    "reorder_point": "0",
                    "preferred_vendor_id": vendor_row["vendor_id"] if vendor_row else "",
                    "vendor_sku": request_row.get("vendor_sku", ""),
                    "storage_location": storage_location,
                    "last_counted_at": now[:10],
                    "status": "active",
                    "notes": "Created automatically from received purchase request",
                }
                inventory_rows.append(inventory_item)
            else:
                current_quantity = self._parse_non_negative_decimal(
                    inventory_item.get("quantity_on_hand", "0"), "quantity_on_hand"
                )
                updated_item = inventory_item.copy()
                updated_item["quantity_on_hand"] = format_decimal(current_quantity + received_quantity)
                updated_item["last_counted_at"] = now[:10]
                if storage_location:
                    updated_item["storage_location"] = storage_location
                inventory_item = updated_item
                inventory_rows[item_index] = self.store.normalize_row(INVENTORY_ITEMS_TABLE, updated_item)

            updated_request = request_row.copy()
            updated_request["request_status"] = "received"
            updated_request["purchasing_outcome"] = (
                "completed" if received_quantity >= requested_quantity else "partially_received"
            )
            updated_request["purchaser_user_id"] = request_row.get("purchaser_user_id", "") or actor["user_id"]
            updated_request["purchaser_name"] = request_row.get("purchaser_name", "") or actor["full_name"]
            updated_request["purchased_quantity"] = format_decimal(received_quantity)
            if actual_price:
                updated_request["actual_unit_price"] = actual_price
            if not updated_request.get("ordered_at", ""):
                updated_request["ordered_at"] = now
            updated_request["received_at"] = now
            updated_request["inventory_item_id"] = inventory_item["item_id"]
            if payload.notes.strip():
                updated_request["notes"] = self._append_note(updated_request.get("notes", ""), payload.notes.strip())

            request_rows[request_index] = self.store.normalize_row(PURCHASE_REQUESTS_TABLE, updated_request)

            event = {
                "event_id": self.store.next_id(PURCHASE_REQUEST_EVENTS_TABLE),
                "request_id": updated_request["request_id"],
                "event_at": now,
                "actor_user_id": actor["user_id"],
                "actor_name": actor["full_name"],
                "event_type": "received",
                "old_status": current_status,
                "new_status": "received",
                "details": payload.notes.strip() or "Inventory received and stock updated.",
            }
            movement = {
                "movement_id": self.store.next_id(INVENTORY_MOVEMENTS_TABLE),
                "item_id": inventory_item["item_id"],
                "movement_type": "receive",
                "quantity": format_decimal(received_quantity),
                "unit": inventory_item["unit"],
                "related_request_id": updated_request["request_id"],
                "performed_by_user_id": actor["user_id"],
                "performed_by_name": actor["full_name"],
                "performed_at": now,
                "storage_location": storage_location,
                "notes": payload.notes.strip() or "Inventory received from purchase request.",
            }

            self.store.write_rows(INVENTORY_ITEMS_TABLE, inventory_rows)
            self.store.write_rows(PURCHASE_REQUESTS_TABLE, request_rows)
            self.store.append_row(PURCHASE_REQUEST_EVENTS_TABLE, event)
            self.store.append_row(INVENTORY_MOVEMENTS_TABLE, movement)

        return {
            "request": updated_request,
            "inventory_item": inventory_item,
            "movement": movement,
        }

    @staticmethod
    def _append_note(existing_notes: str, new_note: str) -> str:
        if not existing_notes.strip():
            return new_note
        return f"{existing_notes.strip()} | {new_note}"

    def _find_inventory_item(
        self,
        rows: list[dict[str, str]],
        request_row: dict[str, str],
    ) -> tuple[int, dict[str, str] | None]:
        request_item_id = request_row.get("inventory_item_id", "").strip()
        if request_item_id:
            index, row = self._find_row_index(rows, "item_id", request_item_id)
            if row is not None:
                return index, row

        target_name = request_row.get("item_name", "").strip().lower()
        target_unit = request_row.get("unit", "").strip().lower()
        for index, row in enumerate(rows):
            if row.get("status", "") != "active":
                continue
            if row.get("item_name", "").strip().lower() == target_name and row.get("unit", "").strip().lower() == target_unit:
                return index, row
        return -1, None

    def _get_user_by_slack_user_id(self, slack_user_id: str) -> dict[str, str]:
        for row in self.store.read_rows(USERS_TABLE):
            if row.get("slack_user_id", "") == slack_user_id.strip() and row.get("status", "") == "active":
                return row
        raise NotFoundError(f"No active inventory user is mapped to Slack user {slack_user_id}.")

    def _resolve_received_quantity(self, request_row: dict[str, str], raw_quantity: str) -> Decimal:
        if raw_quantity.strip():
            return self._parse_positive_decimal(raw_quantity, "quantity_received")
        if request_row.get("purchased_quantity", "").strip():
            return self._parse_positive_decimal(request_row["purchased_quantity"], "purchased_quantity")
        return self._parse_positive_decimal(request_row.get("quantity_requested", "0"), "quantity_requested")

    @staticmethod
    def _parse_positive_decimal(value: str, field_name: str) -> Decimal:
        try:
            number = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValidationError(f"{field_name} must be numeric.") from exc
        if number <= 0:
            raise ValidationError(f"{field_name} must be greater than zero.")
        return number

    @staticmethod
    def _parse_non_negative_decimal(value: str, field_name: str) -> Decimal:
        try:
            number = Decimal(value.strip() or "0")
        except InvalidOperation as exc:
            raise ValidationError(f"{field_name} must be numeric.") from exc
        if number < 0:
            raise ValidationError(f"{field_name} must be zero or greater.")
        return number

    def _enrich_inventory_row(self, row: dict[str, str]) -> dict[str, str]:
        quantity = self._parse_non_negative_decimal(row.get("quantity_on_hand", "0"), "quantity_on_hand")
        reorder_point = self._parse_non_negative_decimal(row.get("reorder_point", "0"), "reorder_point")
        enriched = row.copy()
        enriched["is_low_stock"] = "yes" if reorder_point > 0 and quantity <= reorder_point else "no"
        return enriched

    @staticmethod
    def _find_row_index(
        rows: list[dict[str, str]],
        key_field: str,
        key_value: str,
    ) -> tuple[int, dict[str, str] | None]:
        for index, row in enumerate(rows):
            if row.get(key_field, "") == key_value:
                return index, row
        return -1, None

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")
