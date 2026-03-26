from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

USERS_TABLE = "users.csv"
PROJECTS_TABLE = "projects.csv"
VENDORS_TABLE = "vendors.csv"
INVENTORY_ITEMS_TABLE = "inventory_items.csv"
INVENTORY_MOVEMENTS_TABLE = "inventory_movements.csv"
PURCHASE_REQUESTS_TABLE = "purchase_requests.csv"
PURCHASE_REQUEST_EVENTS_TABLE = "purchase_request_events.csv"

TABLE_SCHEMAS = {
    USERS_TABLE: [
        "user_id",
        "slack_user_id",
        "full_name",
        "team",
        "email",
        "role",
        "status",
    ],
    PROJECTS_TABLE: [
        "project_id",
        "project_name",
        "project_owner_user_id",
        "project_owner_name",
        "cost_center",
        "status",
        "notes",
    ],
    VENDORS_TABLE: [
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
    INVENTORY_ITEMS_TABLE: [
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
    INVENTORY_MOVEMENTS_TABLE: [
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
    PURCHASE_REQUESTS_TABLE: [
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
    PURCHASE_REQUEST_EVENTS_TABLE: [
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

TABLE_ID_FIELDS = {
    USERS_TABLE: "user_id",
    PROJECTS_TABLE: "project_id",
    VENDORS_TABLE: "vendor_id",
    INVENTORY_ITEMS_TABLE: "item_id",
    INVENTORY_MOVEMENTS_TABLE: "movement_id",
    PURCHASE_REQUESTS_TABLE: "request_id",
    PURCHASE_REQUEST_EVENTS_TABLE: "event_id",
}

TABLE_ID_PREFIXES = {
    USERS_TABLE: "USR",
    PROJECTS_TABLE: "PRJ",
    VENDORS_TABLE: "VND",
    INVENTORY_ITEMS_TABLE: "INV",
    INVENTORY_MOVEMENTS_TABLE: "MOV",
    PURCHASE_REQUESTS_TABLE: "REQ",
    PURCHASE_REQUEST_EVENTS_TABLE: "EVT",
}

REQUIRED_NON_EMPTY = {
    USERS_TABLE: {"user_id", "slack_user_id", "full_name", "role", "status"},
    PROJECTS_TABLE: {
        "project_id",
        "project_name",
        "project_owner_user_id",
        "project_owner_name",
        "status",
    },
    VENDORS_TABLE: {"vendor_id", "vendor_name", "default_currency", "status"},
    INVENTORY_ITEMS_TABLE: {
        "item_id",
        "item_name",
        "unit",
        "quantity_on_hand",
        "reorder_point",
        "status",
    },
    INVENTORY_MOVEMENTS_TABLE: {
        "movement_id",
        "item_id",
        "movement_type",
        "quantity",
        "unit",
        "performed_by_user_id",
        "performed_by_name",
        "performed_at",
    },
    PURCHASE_REQUESTS_TABLE: {
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
    PURCHASE_REQUEST_EVENTS_TABLE: {
        "event_id",
        "request_id",
        "event_at",
        "actor_user_id",
        "actor_name",
        "event_type",
    },
}

ALLOWED_VALUES = {
    (USERS_TABLE, "role"): {"requester", "purchaser", "admin"},
    (USERS_TABLE, "status"): {"active", "inactive"},
    (PROJECTS_TABLE, "status"): {"active", "on_hold", "closed"},
    (VENDORS_TABLE, "status"): {"active", "inactive"},
    (INVENTORY_ITEMS_TABLE, "status"): {"active", "discontinued", "archived"},
    (INVENTORY_MOVEMENTS_TABLE, "movement_type"): {
        "receive",
        "consume",
        "adjust_add",
        "adjust_remove",
        "reserve",
        "unreserve",
    },
    (PURCHASE_REQUESTS_TABLE, "request_status"): {
        "requested",
        "approved",
        "ordering",
        "ordered",
        "received",
        "rejected",
        "cancelled",
    },
    (PURCHASE_REQUESTS_TABLE, "purchasing_outcome"): {
        "pending",
        "approved",
        "completed",
        "partially_received",
        "rejected",
        "cancelled",
    },
    (PURCHASE_REQUEST_EVENTS_TABLE, "event_type"): {
        "request_created",
        "approved",
        "ordering_started",
        "ordered",
        "received",
        "rejected",
        "cancelled",
        "note_added",
    },
    (PURCHASE_REQUEST_EVENTS_TABLE, "new_status"): {
        "requested",
        "approved",
        "ordering",
        "ordered",
        "received",
        "rejected",
        "cancelled",
    },
}

NUMERIC_FIELDS = {
    (INVENTORY_ITEMS_TABLE, "quantity_on_hand"),
    (INVENTORY_ITEMS_TABLE, "reorder_point"),
    (INVENTORY_MOVEMENTS_TABLE, "quantity"),
    (PURCHASE_REQUESTS_TABLE, "quantity_requested"),
    (PURCHASE_REQUESTS_TABLE, "purchased_quantity"),
    (PURCHASE_REQUESTS_TABLE, "estimated_unit_price"),
    (PURCHASE_REQUESTS_TABLE, "actual_unit_price"),
}

REFERENCE_CHECKS = [
    (PROJECTS_TABLE, "project_owner_user_id", USERS_TABLE, True),
    (INVENTORY_ITEMS_TABLE, "preferred_vendor_id", VENDORS_TABLE, False),
    (INVENTORY_MOVEMENTS_TABLE, "item_id", INVENTORY_ITEMS_TABLE, True),
    (INVENTORY_MOVEMENTS_TABLE, "related_request_id", PURCHASE_REQUESTS_TABLE, False),
    (INVENTORY_MOVEMENTS_TABLE, "performed_by_user_id", USERS_TABLE, True),
    (PURCHASE_REQUESTS_TABLE, "requested_by_user_id", USERS_TABLE, True),
    (PURCHASE_REQUESTS_TABLE, "project_id", PROJECTS_TABLE, True),
    (PURCHASE_REQUESTS_TABLE, "vendor_id", VENDORS_TABLE, False),
    (PURCHASE_REQUESTS_TABLE, "purchaser_user_id", USERS_TABLE, False),
    (PURCHASE_REQUESTS_TABLE, "inventory_item_id", INVENTORY_ITEMS_TABLE, False),
    (PURCHASE_REQUEST_EVENTS_TABLE, "request_id", PURCHASE_REQUESTS_TABLE, True),
    (PURCHASE_REQUEST_EVENTS_TABLE, "actor_user_id", USERS_TABLE, True),
]

OPEN_REQUEST_STATUSES = {"requested", "approved", "ordering", "ordered"}
TERMINAL_REQUEST_STATUSES = {"received", "rejected", "cancelled"}

REQUEST_EVENT_TYPES_BY_STATUS = {
    "approved": "approved",
    "ordering": "ordering_started",
    "ordered": "ordered",
    "received": "received",
    "rejected": "rejected",
    "cancelled": "cancelled",
}

DEFAULT_PURCHASING_OUTCOME_BY_STATUS = {
    "requested": "pending",
    "approved": "approved",
    "ordering": "approved",
    "ordered": "approved",
    "received": "completed",
    "rejected": "rejected",
    "cancelled": "cancelled",
}


@dataclass(frozen=True)
class PurchaseRequestInput:
    requested_by_slack_user_id: str
    project_id: str
    item_name: str
    quantity_requested: str
    unit: str
    vendor_id: str = ""
    needed_by: str = ""
    justification: str = ""
    item_description: str = ""
    vendor_sku: str = ""
    notes: str = ""
    estimated_unit_price: str = ""


@dataclass(frozen=True)
class ReceiveInventoryInput:
    request_id: str
    actor_slack_user_id: str
    quantity_received: str = ""
    actual_unit_price: str = ""
    storage_location: str = ""
    notes: str = ""


def format_decimal(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"
