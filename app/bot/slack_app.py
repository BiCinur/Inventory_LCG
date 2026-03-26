from __future__ import annotations

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from app.bot.handlers import register_handlers
from app.config import Settings
from app.services.inventory_service import InventoryService
from app.services.purchasing_service import PurchasingService
from app.services.reporting_service import ReportingService
from app.storage.csv_store import CSVStore


def create_app() -> tuple[App, Settings]:
    settings = Settings.from_env()
    settings.validate()

    app_kwargs = {
        "token": settings.slack_bot_token,
        "token_verification_enabled": not settings.slack_skip_auth_test,
    }
    if settings.slack_signing_secret:
        app_kwargs["signing_secret"] = settings.slack_signing_secret

    slack_app = App(**app_kwargs)
    store = CSVStore(settings.data_dir)
    inventory_service = InventoryService(store)
    purchasing_service = PurchasingService(store)
    reporting_service = ReportingService(inventory_service, purchasing_service)

    register_handlers(
        slack_app=slack_app,
        inventory_service=inventory_service,
        purchasing_service=purchasing_service,
        reporting_service=reporting_service,
    )
    return slack_app, settings


def main() -> None:
    slack_app, settings = create_app()

    if settings.slack_app_token:
        SocketModeHandler(slack_app, settings.slack_app_token).start()
        return

    slack_app.start(port=settings.port)


if __name__ == "__main__":
    main()
