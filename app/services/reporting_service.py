from __future__ import annotations

from app.services.inventory_service import InventoryService
from app.services.purchasing_service import PurchasingService


class ReportingService:
    def __init__(
        self,
        inventory_service: InventoryService,
        purchasing_service: PurchasingService,
    ) -> None:
        self.inventory_service = inventory_service
        self.purchasing_service = purchasing_service

    def low_stock_report(self, limit: int = 10) -> list[dict[str, str]]:
        return self.inventory_service.low_stock_items(limit=limit)

    def open_request_report(self, limit: int = 10) -> list[dict[str, str]]:
        return self.purchasing_service.list_open_requests(limit=limit)
