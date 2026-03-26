from __future__ import annotations

import json

from app.models.schemas import PurchaseRequestInput, ReceiveInventoryInput
from app.services.errors import InventoryAppError
from app.services.inventory_service import InventoryService
from app.services.purchasing_service import PurchasingService
from app.services.reporting_service import ReportingService


def register_handlers(
    slack_app,
    inventory_service: InventoryService,
    purchasing_service: PurchasingService,
    reporting_service: ReportingService,
) -> None:
    @slack_app.command("/inventory")
    def inventory_command(ack, body, client, respond, logger):
        ack()
        text = (body.get("text") or "").strip()

        try:
            if not text:
                respond(_help_text())
                return

            parts = text.split()
            subcommand = parts[0].lower()
            arguments = parts[1:]

            if subcommand == "help":
                respond(_help_text())
                return

            if subcommand == "search":
                query = " ".join(arguments)
                rows = inventory_service.search_items(query, limit=10)
                respond(_format_inventory_search(rows, query))
                return

            if subcommand == "low-stock":
                rows = reporting_service.low_stock_report(limit=10)
                respond(_format_low_stock(rows))
                return

            if subcommand == "request":
                initial_item_name = " ".join(arguments)
                projects = purchasing_service.list_projects()
                vendors = purchasing_service.list_vendors()
                if not projects:
                    respond("No active projects are loaded yet. Add at least one row to data/projects.csv first.")
                    return
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view=_build_purchase_request_modal(
                        projects=projects,
                        vendors=vendors,
                        initial_item_name=initial_item_name,
                    ),
                )
                return

            if subcommand == "request-status":
                if not arguments:
                    respond("Usage: /inventory request-status REQ-001")
                    return
                summary = purchasing_service.get_request_status(arguments[0])
                respond(_format_request_status(summary))
                return

            if subcommand == "receive":
                if not arguments:
                    respond("Usage: /inventory receive REQ-001")
                    return
                summary = purchasing_service.get_request_status(arguments[0])
                client.views_open(
                    trigger_id=body["trigger_id"],
                    view=_build_receive_modal(summary["request"]),
                )
                return

            if subcommand == "set-status":
                if len(arguments) < 2:
                    respond(
                        "Usage: /inventory set-status REQ-001 approved optional note "
                        "(approved, ordering, ordered, rejected, cancelled)"
                    )
                    return
                request_id = arguments[0]
                new_status = arguments[1].lower()
                note = " ".join(arguments[2:])
                updated = purchasing_service.update_request_status(
                    request_id=request_id,
                    new_status=new_status,
                    actor_slack_user_id=body["user_id"],
                    details=note,
                    notes=note,
                )
                respond(_format_status_update(updated))
                return

            respond(_help_text())
        except InventoryAppError as exc:
            respond(f"Inventory error: {exc}")
        except Exception:
            logger.exception("Unexpected error while handling /inventory")
            respond("The inventory bot hit an unexpected error while handling that command.")

    @slack_app.view("purchase_request_modal")
    def purchase_request_modal_submission(ack, body, client, logger):
        ack()
        try:
            values = body["view"]["state"]["values"]
            selected_project = _selected_option_value(values, "project_input", "project_select")
            selected_vendor = _selected_option_value(values, "vendor_input", "vendor_select")

            payload = PurchaseRequestInput(
                requested_by_slack_user_id=body["user"]["id"],
                project_id=selected_project,
                item_name=_plain_text_value(values, "item_name_input", "item_name_value"),
                item_description=_plain_text_value(values, "item_description_input", "item_description_value"),
                quantity_requested=_plain_text_value(values, "quantity_input", "quantity_value"),
                unit=_plain_text_value(values, "unit_input", "unit_value"),
                vendor_id=selected_vendor,
                needed_by=_plain_text_value(values, "needed_by_input", "needed_by_value"),
                justification=_plain_text_value(values, "justification_input", "justification_value"),
                vendor_sku=_plain_text_value(values, "vendor_sku_input", "vendor_sku_value"),
                notes=_plain_text_value(values, "notes_input", "notes_value"),
                estimated_unit_price=_plain_text_value(
                    values, "estimated_price_input", "estimated_price_value"
                ),
            )
            created = purchasing_service.create_request(payload)
            client.chat_postMessage(channel=body["user"]["id"], text=_format_created_request(created))
        except InventoryAppError as exc:
            client.chat_postMessage(channel=body["user"]["id"], text=f"Inventory error: {exc}")
        except Exception:
            logger.exception("Unexpected error while submitting purchase request modal")
            client.chat_postMessage(
                channel=body["user"]["id"],
                text="The inventory bot hit an unexpected error while creating that request.",
            )

    @slack_app.view("receive_inventory_modal")
    def receive_inventory_modal_submission(ack, body, client, logger):
        ack()
        try:
            metadata = json.loads(body["view"].get("private_metadata", "{}"))
            request_id = metadata.get("request_id", "")
            values = body["view"]["state"]["values"]

            payload = ReceiveInventoryInput(
                request_id=request_id,
                actor_slack_user_id=body["user"]["id"],
                quantity_received=_plain_text_value(values, "quantity_received_input", "quantity_received_value"),
                actual_unit_price=_plain_text_value(values, "actual_price_input", "actual_price_value"),
                storage_location=_plain_text_value(
                    values, "storage_location_input", "storage_location_value"
                ),
                notes=_plain_text_value(values, "receive_notes_input", "receive_notes_value"),
            )
            result = inventory_service.receive_inventory(payload)
            client.chat_postMessage(channel=body["user"]["id"], text=_format_received_inventory(result))
        except InventoryAppError as exc:
            client.chat_postMessage(channel=body["user"]["id"], text=f"Inventory error: {exc}")
        except Exception:
            logger.exception("Unexpected error while receiving inventory")
            client.chat_postMessage(
                channel=body["user"]["id"],
                text="The inventory bot hit an unexpected error while receiving inventory.",
            )


def _build_purchase_request_modal(
    projects: list[dict[str, str]],
    vendors: list[dict[str, str]],
    initial_item_name: str = "",
) -> dict[str, object]:
    blocks: list[dict[str, object]] = [
        {
            "type": "input",
            "block_id": "project_input",
            "label": {"type": "plain_text", "text": "Project"},
            "element": {
                "type": "static_select",
                "action_id": "project_select",
                "placeholder": {"type": "plain_text", "text": "Select a project"},
                "options": [_project_option(project) for project in projects[:100]],
            },
        },
        {
            "type": "input",
            "block_id": "item_name_input",
            "label": {"type": "plain_text", "text": "Item name"},
            "element": {
                "type": "plain_text_input",
                "action_id": "item_name_value",
                "initial_value": initial_item_name,
            },
        },
        {
            "type": "input",
            "block_id": "item_description_input",
            "optional": True,
            "label": {"type": "plain_text", "text": "Item description"},
            "element": {
                "type": "plain_text_input",
                "action_id": "item_description_value",
                "multiline": True,
            },
        },
        {
            "type": "input",
            "block_id": "quantity_input",
            "label": {"type": "plain_text", "text": "Quantity"},
            "element": {
                "type": "plain_text_input",
                "action_id": "quantity_value",
                "initial_value": "1",
            },
        },
        {
            "type": "input",
            "block_id": "unit_input",
            "label": {"type": "plain_text", "text": "Unit"},
            "element": {
                "type": "plain_text_input",
                "action_id": "unit_value",
                "initial_value": "each",
            },
        },
    ]

    if vendors:
        blocks.append(
            {
                "type": "input",
                "block_id": "vendor_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Vendor"},
                "element": {
                    "type": "static_select",
                    "action_id": "vendor_select",
                    "placeholder": {"type": "plain_text", "text": "Select a vendor"},
                    "options": [_vendor_option(vendor) for vendor in vendors[:100]],
                },
            }
        )
    else:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "No active vendors are loaded yet. You can still submit a request and fill vendor later.",
                    }
                ],
            }
        )

    blocks.extend(
        [
            {
                "type": "input",
                "block_id": "vendor_sku_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Vendor SKU"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "vendor_sku_value",
                },
            },
            {
                "type": "input",
                "block_id": "needed_by_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Needed by"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "needed_by_value",
                    "placeholder": {"type": "plain_text", "text": "YYYY-MM-DD"},
                },
            },
            {
                "type": "input",
                "block_id": "estimated_price_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Estimated unit price"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "estimated_price_value",
                },
            },
            {
                "type": "input",
                "block_id": "justification_input",
                "label": {"type": "plain_text", "text": "Justification"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "justification_value",
                    "multiline": True,
                },
            },
            {
                "type": "input",
                "block_id": "notes_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Notes"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "notes_value",
                    "multiline": True,
                },
            },
        ]
    )

    return {
        "type": "modal",
        "callback_id": "purchase_request_modal",
        "title": {"type": "plain_text", "text": "Purchase Request"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": blocks,
    }


def _build_receive_modal(request_row: dict[str, str]) -> dict[str, object]:
    default_quantity = request_row.get("purchased_quantity", "") or request_row.get("quantity_requested", "")
    metadata = json.dumps({"request_id": request_row["request_id"]})

    return {
        "type": "modal",
        "callback_id": "receive_inventory_modal",
        "private_metadata": metadata,
        "title": {"type": "plain_text", "text": "Receive Inventory"},
        "submit": {"type": "plain_text", "text": "Receive"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Request:* {request_row['request_id']}\n"
                        f"*Item:* {request_row['item_name']}\n"
                        f"*Requested:* {request_row['quantity_requested']} {request_row['unit']}"
                    ),
                },
            },
            {
                "type": "input",
                "block_id": "quantity_received_input",
                "label": {"type": "plain_text", "text": "Quantity received"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "quantity_received_value",
                    "initial_value": default_quantity,
                },
            },
            {
                "type": "input",
                "block_id": "actual_price_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Actual unit price"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "actual_price_value",
                    "initial_value": request_row.get("actual_unit_price", "")
                    or request_row.get("estimated_unit_price", ""),
                },
            },
            {
                "type": "input",
                "block_id": "storage_location_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Storage location"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "storage_location_value",
                },
            },
            {
                "type": "input",
                "block_id": "receive_notes_input",
                "optional": True,
                "label": {"type": "plain_text", "text": "Notes"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "receive_notes_value",
                    "multiline": True,
                },
            },
        ],
    }


def _plain_text_value(values: dict[str, object], block_id: str, action_id: str) -> str:
    block = values.get(block_id, {})
    action = block.get(action_id, {}) if isinstance(block, dict) else {}
    if not isinstance(action, dict):
        return ""
    return (action.get("value") or "").strip()


def _selected_option_value(values: dict[str, object], block_id: str, action_id: str) -> str:
    block = values.get(block_id, {})
    action = block.get(action_id, {}) if isinstance(block, dict) else {}
    if not isinstance(action, dict):
        return ""
    selected = action.get("selected_option") or {}
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("value") or "").strip()


def _project_option(project: dict[str, str]) -> dict[str, object]:
    return {
        "text": {"type": "plain_text", "text": project["project_name"][:75]},
        "value": project["project_id"],
    }


def _vendor_option(vendor: dict[str, str]) -> dict[str, object]:
    return {
        "text": {"type": "plain_text", "text": vendor["vendor_name"][:75]},
        "value": vendor["vendor_id"],
    }


def _help_text() -> str:
    return "\n".join(
        [
            "Inventory bot commands:",
            "/inventory search <text>",
            "/inventory request [item name]",
            "/inventory request-status <request_id>",
            "/inventory low-stock",
            "/inventory receive <request_id>",
            "/inventory set-status <request_id> <approved|ordering|ordered|rejected|cancelled> [note]",
        ]
    )


def _format_inventory_search(rows: list[dict[str, str]], query: str) -> str:
    header = f"Inventory search results for '{query}':" if query else "Inventory items:"
    if not rows:
        return f"{header}\nNo matching inventory items found."

    lines = [header]
    for row in rows:
        low_stock = "LOW STOCK" if row.get("is_low_stock") == "yes" else "ok"
        lines.append(
            f"- {row['item_id']}: {row['item_name']} | {row['quantity_on_hand']} {row['unit']} | "
            f"{row['storage_location'] or 'location not set'} | {low_stock}"
        )
    return "\n".join(lines)


def _format_low_stock(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No active items are currently at or below reorder point."

    lines = ["Low-stock inventory items:"]
    for row in rows:
        lines.append(
            f"- {row['item_id']}: {row['item_name']} | on hand {row['quantity_on_hand']} {row['unit']} | "
            f"reorder point {row['reorder_point']}"
        )
    return "\n".join(lines)


def _format_created_request(request_row: dict[str, str]) -> str:
    return "\n".join(
        [
            f"Created purchase request {request_row['request_id']}.",
            f"Project: {request_row['project_name']}",
            f"Item: {request_row['item_name']}",
            f"Quantity: {request_row['quantity_requested']} {request_row['unit']}",
            f"Status: {request_row['request_status']}",
        ]
    )


def _format_request_status(summary: dict[str, object]) -> str:
    request_row = summary["request"]
    events = summary["events"]
    lines = [
        f"Request {request_row['request_id']}",
        f"Status: {request_row['request_status']}",
        f"Outcome: {request_row['purchasing_outcome']}",
        f"Project: {request_row['project_name']}",
        f"Item: {request_row['item_name']}",
        f"Quantity: {request_row['quantity_requested']} {request_row['unit']}",
    ]
    if request_row.get("vendor_name", ""):
        lines.append(f"Vendor: {request_row['vendor_name']}")
    if request_row.get("po_number", ""):
        lines.append(f"PO: {request_row['po_number']}")
    if request_row.get("received_at", ""):
        lines.append(f"Received at: {request_row['received_at']}")

    lines.append("Recent events:")
    for event in events[-5:]:
        lines.append(
            f"- {event['event_at']} | {event['event_type']} | {event['actor_name']} | {event['details']}"
        )
    return "\n".join(lines)


def _format_received_inventory(result: dict[str, dict[str, str]]) -> str:
    request_row = result["request"]
    inventory_item = result["inventory_item"]
    return "\n".join(
        [
            f"Received inventory for {request_row['request_id']}.",
            f"Item: {inventory_item['item_name']}",
            f"Added quantity: {request_row['purchased_quantity']} {request_row['unit']}",
            f"Inventory item id: {inventory_item['item_id']}",
            f"Current stock: {inventory_item['quantity_on_hand']} {inventory_item['unit']}",
        ]
    )


def _format_status_update(request_row: dict[str, str]) -> str:
    return (
        f"Updated {request_row['request_id']} to {request_row['request_status']} "
        f"with outcome {request_row['purchasing_outcome']}."
    )
