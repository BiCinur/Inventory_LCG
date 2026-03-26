# Inventory and Purchasing Starter

This workspace is a CSV-first starter for an inventory system that humans, AI tooling, and a Slack bot can all work with. The goal is to keep the data easy to inspect and edit while still making it structured enough to answer questions like:

- What is in stock right now?
- Who requested an item to be purchased?
- Which project is the purchase for?
- What vendor was used?
- What happened to the request in the end?

## Recommended shape

Use CSV as the human-facing contract, not as unstructured notes. The MVP pattern in this workspace is:

1. Slack users interact with a Slack bot.
2. The bot calls a small service layer that validates data before writing anything.
3. Humans can still edit the CSV files directly for master data and controlled corrections.
4. Every stock change and request status change also creates an audit row.

This gives you readable files now and a clean upgrade path to SQLite or Postgres later.

## Starter files

- [docs/architecture.md](docs/architecture.md): end-to-end architecture, workflows, and build order.
- [data/users.csv](data/users.csv): Slack users and requesters.
- [data/projects.csv](data/projects.csv): approved projects and owners.
- [data/vendors.csv](data/vendors.csv): vendor directory.
- [data/inventory_items.csv](data/inventory_items.csv): current inventory snapshot.
- [data/inventory_movements.csv](data/inventory_movements.csv): stock movement history.
- [data/purchase_requests.csv](data/purchase_requests.csv): current purchase request state.
- [data/purchase_request_events.csv](data/purchase_request_events.csv): purchase request audit trail.
- [scripts/validate_csv.py](scripts/validate_csv.py): validates required columns, IDs, and references.
- [app/storage/csv_store.py](app/storage/csv_store.py): CSV reader/writer with a simple lock file.
- [app/services/purchasing_service.py](app/services/purchasing_service.py): purchase request creation and status changes.
- [app/services/inventory_service.py](app/services/inventory_service.py): inventory search, low-stock reporting, and receiving stock.
- [app/bot/slack_app.py](app/bot/slack_app.py): Slack app entrypoint.

## Application status

The repo now includes a working scaffold for:

- shared CSV schema metadata
- a CSV storage layer with serialized writes
- a purchasing service
- an inventory service
- a Slack bot entrypoint with `/inventory` subcommands and modals

## Run locally

1. Install Python 3.11 or newer.
2. Create a virtual environment and install dependencies:
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
   - `pip install -r requirements.txt`
3. Copy `.env.example` to `.env`.
4. Set Slack credentials in `.env`:
   - `SLACK_BOT_TOKEN`
   - `SLACK_APP_TOKEN` for Socket Mode
   - `SLACK_SIGNING_SECRET` only if you want HTTP mode instead
   - `SLACK_SKIP_AUTH_TEST=1` if you want local/offline smoke tests without hitting Slack during app creation
5. Replace the sample rows in `data/users.csv`, `data/projects.csv`, and `data/vendors.csv` with your real team data.
6. Seed `data/inventory_items.csv` with your real stock.
7. Run `python scripts/validate_csv.py`.
8. Start the bot with `python -m app.bot.slack_app`.

If you are using the repo-local interpreter created in this workspace, the equivalent commands are:

- `.\.python\python.exe .\scripts\validate_csv.py`
- `.\.python\python.exe -m unittest discover -s tests -v`
- `.\.python\python.exe -m app.bot.slack_app`

## Slack setup

Recommended MVP setup:

- Enable Socket Mode in your Slack app.
- Add the `commands`, `chat:write`, and `users:read` scopes your workflow needs.
- Create one slash command: `/inventory`
- Route all inventory actions through that one command using subcommands.

## Supported bot commands

- `/inventory search <text>`
- `/inventory request [item name]`
- `/inventory request-status <request_id>`
- `/inventory low-stock`
- `/inventory receive <request_id>`
- `/inventory set-status <request_id> <approved|ordering|ordered|rejected|cancelled> [note]`

Use `/inventory receive` for the final receiving step so the bot updates both the request tables and the inventory tables together.

## Next improvements

Good next steps after this scaffold:

- add unit tests around `CSVStore`, `PurchasingService`, and `InventoryService`
- tighten Slack scopes and role checks for purchaser-only actions
- add backups and daily summary jobs
- move to SQLite later if concurrent editing becomes frequent

## MVP rule of thumb

CSV works well when one bot and a small team are editing predictable tables. If several people will edit the same files at the same time every day, move to a database-backed workflow sooner.
