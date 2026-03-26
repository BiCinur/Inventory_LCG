from __future__ import annotations

import csv
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from app.models.schemas import DATA_DIR, TABLE_ID_FIELDS, TABLE_ID_PREFIXES, TABLE_SCHEMAS, format_decimal
from app.storage.file_lock import FileLock


class CSVStore:
    def __init__(self, data_dir: Path | str = DATA_DIR, lock_timeout_seconds: float = 10.0) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(self.data_dir / ".inventory.lock", timeout_seconds=lock_timeout_seconds)

    @contextmanager
    def transaction(self) -> Iterator["CSVStore"]:
        with self._lock.acquire():
            yield self

    def table_path(self, table_name: str) -> Path:
        if table_name not in TABLE_SCHEMAS:
            raise ValueError(f"Unknown table: {table_name}")
        return self.data_dir / table_name

    def read_rows(self, table_name: str) -> list[dict[str, str]]:
        path = self.table_path(table_name)
        if not path.exists():
            raise FileNotFoundError(f"Missing CSV table: {path}")

        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows: list[dict[str, str]] = []
            for row in reader:
                rows.append(self.normalize_row(table_name, row))
            return rows

    def write_rows(self, table_name: str, rows: list[dict[str, object]]) -> None:
        path = self.table_path(table_name)
        normalized_rows = [self.normalize_row(table_name, row) for row in rows]

        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TABLE_SCHEMAS[table_name])
            writer.writeheader()
            writer.writerows(normalized_rows)

    def append_row(self, table_name: str, row: dict[str, object]) -> dict[str, str]:
        path = self.table_path(table_name)
        normalized = self.normalize_row(table_name, row)

        file_exists = path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TABLE_SCHEMAS[table_name])
            if not file_exists or path.stat().st_size == 0:
                writer.writeheader()
            writer.writerow(normalized)

        return normalized

    def find_row(self, table_name: str, key_field: str, key_value: str) -> dict[str, str] | None:
        for row in self.read_rows(table_name):
            if row.get(key_field, "") == key_value:
                return row
        return None

    def next_id(self, table_name: str) -> str:
        id_field = TABLE_ID_FIELDS[table_name]
        prefix = TABLE_ID_PREFIXES[table_name]
        highest = 0

        for row in self.read_rows(table_name):
            raw_value = row.get(id_field, "")
            if not raw_value.startswith(f"{prefix}-"):
                continue
            try:
                highest = max(highest, int(raw_value.split("-", 1)[1]))
            except ValueError:
                continue

        return f"{prefix}-{highest + 1:03d}"

    def normalize_row(self, table_name: str, row: dict[str, object] | None) -> dict[str, str]:
        row = row or {}
        expected = TABLE_SCHEMAS[table_name]
        extra = sorted(set(row) - set(expected))
        if extra:
            extras = ", ".join(extra)
            raise ValueError(f"{table_name} received unexpected columns: {extras}")

        normalized: dict[str, str] = {}
        for column in expected:
            normalized[column] = self.stringify_value(row.get(column, ""))
        return normalized

    @staticmethod
    def stringify_value(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, Decimal):
            return format_decimal(value)
        return str(value).strip()
