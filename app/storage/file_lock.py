from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class FileLock:
    def __init__(
        self,
        path: Path,
        timeout_seconds: float = 10.0,
        poll_interval_seconds: float = 0.1,
        stale_after_seconds: float = 300.0,
    ) -> None:
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.stale_after_seconds = stale_after_seconds

    @contextmanager
    def acquire(self) -> Iterator[None]:
        start = time.monotonic()
        self.path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                self._clear_stale_lock_if_needed()
                if time.monotonic() - start >= self.timeout_seconds:
                    raise TimeoutError(f"Timed out waiting for lock {self.path}")
                time.sleep(self.poll_interval_seconds)
                continue

            try:
                payload = f"pid={os.getpid()} created_at={time.time()}\n"
                os.write(descriptor, payload.encode("utf-8"))
            finally:
                os.close(descriptor)
            break

        try:
            yield
        finally:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass

    def _clear_stale_lock_if_needed(self) -> None:
        try:
            age_seconds = time.time() - self.path.stat().st_mtime
        except FileNotFoundError:
            return

        if age_seconds > self.stale_after_seconds:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
