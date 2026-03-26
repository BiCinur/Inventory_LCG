# Architecture

## Goal

Build an inventory and purchasing workflow where:

- humans can read and edit the data in CSV files
- a Slack bot can answer inventory questions
- users can request items to be purchased
- every purchase request records project, quantity, vendor, requester, and outcome
- inventory and request history stay auditable

## Recommended MVP architecture

```text
Slack users
    |
    v
Slack app / bot
    |
    v
Application service layer
    |-- inventory service
    |-- purchasing service
    |-- validation rules
    |
    v
CSV storage layer
    |-- inventory_items.csv
    |-- inventory_movements.csv
    |-- purchase_requests.csv
    |-- purchase_request_events.csv
    |-- projects.csv
    |-- vendors.csv
    |-- users.csv
    |
    v
Backups + reports
```

## Why this is a good starting point

- CSV stays simple for humans and AI tools.
- IDs make the data reliable for joins and automation.
- Repeating human-readable names in request rows makes the files easy to inspect without lookups.
- Current-state tables answer fast questions.
- Append-only event tables preserve history and accountability.

## Core design rules

### 1. Keep two kinds of tables

Current-state tables:

- `inventory_items.csv`
- `purchase_requests.csv`

Audit tables:

- `inventory_movements.csv`
- `purchase_request_events.csv`

The first group tells you the latest state. The second group tells you how you got there.

### 2. Use stable IDs everywhere

Examples:

- `USR-001` for users
- `PRJ-001` for projects
- `VND-001` for vendors
- `INV-001` for inventory items
- `REQ-001` for purchase requests

IDs let the Slack bot update the right rows safely even if names change later.

### 3. Let the bot be the main writer

Humans can still edit the CSV files, but the safest pattern is:

- humans maintain master data such as users, projects, vendors, and item metadata
- the bot creates purchase requests and status updates
- the bot writes stock movement rows
- a validator runs after edits so broken references are caught early

### 4. Treat status changes as events

When a request moves from `requested` to `ordered`, do two things:

- update the current row in `purchase_requests.csv`
- append a row in `purchase_request_events.csv`

This gives you a readable current table and a complete history.

## File-by-file design

| File | Purpose | Main writer |
| --- | --- | --- |
| `users.csv` | Slack user directory and roles | Human admin |
| `projects.csv` | Valid projects and owners | Human admin |
| `vendors.csv` | Vendor directory | Human admin |
| `inventory_items.csv` | Current stock by item | Human admin + bot |
| `inventory_movements.csv` | Every stock receipt, usage, or adjustment | Bot |
| `purchase_requests.csv` | Current state of each purchase request | Bot |
| `purchase_request_events.csv` | Full audit trail for request lifecycle | Bot |

## Main workflows

### A. Ask what is in inventory

1. User asks the Slack bot for an item.
2. Bot searches `inventory_items.csv`.
3. Bot returns quantity, unit, storage location, and reorder state.

### B. Request a purchase

1. User opens a Slack modal.
2. Bot collects:
   - requester
   - project
   - item
   - quantity
   - unit
   - vendor
   - needed-by date
   - justification
3. Bot validates that user, project, and vendor exist.
4. Bot writes one row to `purchase_requests.csv`.
5. Bot writes one row to `purchase_request_events.csv` with `request_created`.

### C. Buyer processes the request

1. Buyer reviews open requests.
2. Buyer changes status to `approved`, `ordering`, `ordered`, `rejected`, or `cancelled`.
3. Bot updates the current request row.
4. Bot appends an event row with timestamp, actor, and details.

### D. Goods are received

1. Buyer or stock manager marks a request as received.
2. Bot updates `purchase_requests.csv` with `received_at`, `actual_unit_price`, and final outcome.
3. Bot appends a `received` event.
4. Bot either:
   - increases the existing inventory item quantity, or
   - creates a new inventory item row if the item is new
5. Bot appends an `inventory_movements.csv` row with `movement_type=receive`.

## Slack bot surface area

Start small. These are enough for an MVP:

- `/inventory search <text>`: search current stock
- `/inventory request`: open purchase request modal
- `/inventory request-status <request_id>`: show status and event summary
- `/inventory receive <request_id>`: mark an order as received
- `/inventory low-stock`: list items below reorder point

Later you can add:

- `/inventory consume <item_id> <qty>`
- `/inventory reserve <item_id> <qty> <project_id>`
- `/inventory vendor <vendor_name>`

## Suggested code structure for the app

```text
app/
  bot/
    slack_app.py
    handlers.py
  services/
    inventory_service.py
    purchasing_service.py
    reporting_service.py
  storage/
    csv_store.py
    file_lock.py
  models/
    schemas.py
  jobs/
    backup_job.py
    validation_job.py
```

## Build order from scratch

### Phase 1: Define the contract

1. Finalize the CSV columns and allowed statuses.
2. Load users, projects, and vendors.
3. Seed your current inventory.
4. Make sure the validator passes.

### Phase 2: Build the storage layer

1. Create a CSV reader/writer module.
2. Add ID generation for requests, events, and movements.
3. Add file locking or serialized writes so the bot does not collide with manual edits.
4. Write unit tests for create, update, and append operations.

### Phase 3: Build the Slack bot

1. Create the Slack app.
2. Add slash commands and modals.
3. Wire commands to the service layer.
4. Return human-friendly responses with IDs and direct status summaries.

### Phase 4: Add operational safety

1. Run the validator after every bot write and on a schedule.
2. Save timestamped backups of the CSV directory.
3. Add a weekly report for:
   - open purchase requests
   - low-stock items
   - received items not yet counted

## Important tradeoffs

### CSV strengths

- easy to inspect
- easy to edit in spreadsheets
- easy for AI tools to parse
- low setup cost

### CSV risks

- concurrent edits can overwrite each other
- formulas or formatting in spreadsheet tools can damage the schema
- reporting gets harder as history grows

## Practical recommendation

Use CSV as the MVP data contract now, but plan for a database-backed source of truth if this becomes a shared operational system.

Good trigger points for upgrading to SQLite or Postgres:

- more than one frequent buyer
- many simultaneous editors
- more than a few dozen requests per week
- need for approvals, permissions, or stronger audit controls

When you upgrade, keep the same file shapes as import/export views so the bot contract does not need to change much.
