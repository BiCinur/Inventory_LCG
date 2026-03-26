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

## How to start from scratch

1. Replace the sample rows in `data/users.csv`, `data/projects.csv`, and `data/vendors.csv` with your real team data.
2. Seed `data/inventory_items.csv` with the items you already keep in stock.
3. Run `python scripts/validate_csv.py` after manual edits.
4. Build a Slack bot on top of this contract. Start with:
   - `/inventory search`
   - `/inventory request`
   - `/inventory request-status`
   - `/inventory receive`
5. Make the bot the default writer for purchase requests and inventory movements.
6. Add daily backups and a simple report that summarizes open requests and low-stock items.
7. When editing volume grows, move the source of truth to SQLite and keep these CSV files as import/export views.

## MVP rule of thumb

CSV works well when one bot and a small team are editing predictable tables. If several people will edit the same files at the same time every day, move to a database-backed workflow sooner.
