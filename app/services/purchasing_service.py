from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.schemas import (
    DEFAULT_PURCHASING_OUTCOME_BY_STATUS,
    OPEN_REQUEST_STATUSES,
    PROJECTS_TABLE,
    PURCHASE_REQUESTS_TABLE,
    PURCHASE_REQUEST_EVENTS_TABLE,
    PurchaseRequestInput,
    REQUEST_EVENT_TYPES_BY_STATUS,
    USERS_TABLE,
    VENDORS_TABLE,
    format_decimal,
)
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.storage.csv_store import CSVStore


class PurchasingService:
    def __init__(self, store: CSVStore) -> None:
        self.store = store

    def list_projects(self) -> list[dict[str, str]]:
        projects = [
            row for row in self.store.read_rows(PROJECTS_TABLE) if row.get("status", "") == "active"
        ]
        return sorted(projects, key=lambda row: row["project_name"].lower())

    def list_vendors(self) -> list[dict[str, str]]:
        vendors = [row for row in self.store.read_rows(VENDORS_TABLE) if row.get("status", "") == "active"]
        return sorted(vendors, key=lambda row: row["vendor_name"].lower())

    def list_open_requests(self, limit: int = 10) -> list[dict[str, str]]:
        rows = [
            row
            for row in self.store.read_rows(PURCHASE_REQUESTS_TABLE)
            if row.get("request_status", "") in OPEN_REQUEST_STATUSES
        ]
        rows.sort(key=lambda row: (row.get("needed_by", ""), row.get("requested_at", "")))
        return rows[:limit]

    def get_user_by_slack_user_id(self, slack_user_id: str) -> dict[str, str]:
        slack_user_id = slack_user_id.strip()
        if not slack_user_id:
            raise ValidationError("Slack user id is required.")

        for row in self.store.read_rows(USERS_TABLE):
            if row.get("slack_user_id", "") == slack_user_id and row.get("status", "") == "active":
                return row
        raise NotFoundError(f"No active inventory user is mapped to Slack user {slack_user_id}.")

    def create_request(self, payload: PurchaseRequestInput) -> dict[str, str]:
        requester = self.get_user_by_slack_user_id(payload.requested_by_slack_user_id)
        project = self._get_required_record(PROJECTS_TABLE, "project_id", payload.project_id)
        vendor = (
            self._get_required_record(VENDORS_TABLE, "vendor_id", payload.vendor_id)
            if payload.vendor_id.strip()
            else None
        )

        quantity = self._parse_positive_decimal(payload.quantity_requested, "quantity_requested")
        if not payload.unit.strip():
            raise ValidationError("unit is required.")
        if not payload.item_name.strip():
            raise ValidationError("item_name is required.")
        if not payload.justification.strip():
            raise ValidationError("justification is required.")

        estimated_price = ""
        if payload.estimated_unit_price.strip():
            estimated_price = format_decimal(
                self._parse_non_negative_decimal(payload.estimated_unit_price, "estimated_unit_price")
            )

        now = self._timestamp()

        with self.store.transaction():
            request_id = self.store.next_id(PURCHASE_REQUESTS_TABLE)
            row = {
                "request_id": request_id,
                "requested_at": now,
                "requested_by_user_id": requester["user_id"],
                "requested_by_name": requester["full_name"],
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "item_name": payload.item_name.strip(),
                "item_description": payload.item_description.strip(),
                "quantity_requested": format_decimal(quantity),
                "unit": payload.unit.strip(),
                "vendor_id": vendor["vendor_id"] if vendor else "",
                "vendor_name": vendor["vendor_name"] if vendor else "",
                "vendor_sku": payload.vendor_sku.strip(),
                "needed_by": payload.needed_by.strip(),
                "justification": payload.justification.strip(),
                "request_status": "requested",
                "purchasing_outcome": DEFAULT_PURCHASING_OUTCOME_BY_STATUS["requested"],
                "purchaser_user_id": "",
                "purchaser_name": "",
                "purchased_quantity": "",
                "estimated_unit_price": estimated_price,
                "actual_unit_price": "",
                "po_number": "",
                "ordered_at": "",
                "received_at": "",
                "inventory_item_id": "",
                "notes": payload.notes.strip(),
            }
            self.store.append_row(PURCHASE_REQUESTS_TABLE, row)

            event = {
                "event_id": self.store.next_id(PURCHASE_REQUEST_EVENTS_TABLE),
                "request_id": request_id,
                "event_at": now,
                "actor_user_id": requester["user_id"],
                "actor_name": requester["full_name"],
                "event_type": "request_created",
                "old_status": "",
                "new_status": "requested",
                "details": payload.justification.strip(),
            }
            self.store.append_row(PURCHASE_REQUEST_EVENTS_TABLE, event)

        return row

    def get_request_status(self, request_id: str) -> dict[str, object]:
        request_row = self._get_required_record(PURCHASE_REQUESTS_TABLE, "request_id", request_id)
        events = [
            row
            for row in self.store.read_rows(PURCHASE_REQUEST_EVENTS_TABLE)
            if row.get("request_id", "") == request_row["request_id"]
        ]
        events.sort(key=lambda row: row.get("event_at", ""))
        return {"request": request_row, "events": events}

    def update_request_status(
        self,
        request_id: str,
        new_status: str,
        actor_slack_user_id: str,
        *,
        details: str = "",
        po_number: str = "",
        purchased_quantity: str = "",
        estimated_unit_price: str = "",
        actual_unit_price: str = "",
        notes: str = "",
    ) -> dict[str, str]:
        allowed_statuses = {"requested", "approved", "ordering", "ordered", "rejected", "cancelled"}
        if new_status not in allowed_statuses:
            if new_status == "received":
                raise ValidationError("Use the receive workflow to mark a request as received.")
            raise ValidationError(f"Unsupported request status: {new_status}")

        actor = self.get_user_by_slack_user_id(actor_slack_user_id)

        quantity_value = ""
        if purchased_quantity.strip():
            quantity_value = format_decimal(
                self._parse_non_negative_decimal(purchased_quantity, "purchased_quantity")
            )

        estimated_value = ""
        if estimated_unit_price.strip():
            estimated_value = format_decimal(
                self._parse_non_negative_decimal(estimated_unit_price, "estimated_unit_price")
            )

        actual_value = ""
        if actual_unit_price.strip():
            actual_value = format_decimal(
                self._parse_non_negative_decimal(actual_unit_price, "actual_unit_price")
            )

        now = self._timestamp()

        with self.store.transaction():
            rows = self.store.read_rows(PURCHASE_REQUESTS_TABLE)
            index, current = self._find_row_index(rows, "request_id", request_id.strip())
            if current is None:
                raise NotFoundError(f"Purchase request {request_id} was not found.")

            old_status = current.get("request_status", "")
            if old_status in {"received", "rejected", "cancelled"} and new_status != old_status:
                raise ConflictError(
                    f"Purchase request {request_id} is already {old_status} and cannot move to {new_status}."
                )

            updated = current.copy()
            updated["request_status"] = new_status
            updated["purchasing_outcome"] = DEFAULT_PURCHASING_OUTCOME_BY_STATUS[new_status]

            if new_status in {"ordering", "ordered"}:
                updated["purchaser_user_id"] = actor["user_id"]
                updated["purchaser_name"] = actor["full_name"]

            if quantity_value:
                updated["purchased_quantity"] = quantity_value
            if estimated_value:
                updated["estimated_unit_price"] = estimated_value
            if actual_value:
                updated["actual_unit_price"] = actual_value
            if po_number.strip():
                updated["po_number"] = po_number.strip()
            if new_status == "ordered" and not updated.get("ordered_at", ""):
                updated["ordered_at"] = now
            if notes.strip():
                updated["notes"] = self._append_note(updated.get("notes", ""), notes.strip())

            rows[index] = self.store.normalize_row(PURCHASE_REQUESTS_TABLE, updated)
            self.store.write_rows(PURCHASE_REQUESTS_TABLE, rows)

            event_type = "note_added"
            event_new_status = old_status or updated["request_status"]
            if new_status != old_status:
                event_type = REQUEST_EVENT_TYPES_BY_STATUS.get(new_status, "note_added")
                event_new_status = new_status

            event_details = details.strip() or notes.strip() or f"Status set to {event_new_status}"
            event = {
                "event_id": self.store.next_id(PURCHASE_REQUEST_EVENTS_TABLE),
                "request_id": updated["request_id"],
                "event_at": now,
                "actor_user_id": actor["user_id"],
                "actor_name": actor["full_name"],
                "event_type": event_type,
                "old_status": old_status,
                "new_status": event_new_status,
                "details": event_details,
            }
            self.store.append_row(PURCHASE_REQUEST_EVENTS_TABLE, event)

        return updated

    def _get_required_record(self, table_name: str, key_field: str, key_value: str) -> dict[str, str]:
        key_value = key_value.strip()
        if not key_value:
            raise ValidationError(f"{key_field} is required.")

        row = self.store.find_row(table_name, key_field, key_value)
        if row is None:
            raise NotFoundError(f"{table_name} does not contain {key_field}={key_value}.")
        if table_name in {PROJECTS_TABLE, VENDORS_TABLE, USERS_TABLE} and row.get("status", "") != "active":
            raise ValidationError(f"{table_name} record {key_value} is not active.")
        return row

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
            number = Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValidationError(f"{field_name} must be numeric.") from exc
        if number < 0:
            raise ValidationError(f"{field_name} must be zero or greater.")
        return number

    @staticmethod
    def _append_note(existing_notes: str, new_note: str) -> str:
        if not existing_notes.strip():
            return new_note
        return f"{existing_notes.strip()} | {new_note}"

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
