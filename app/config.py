from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    slack_skip_auth_test: bool
    data_dir: Path
    port: int = 3000

    @classmethod
    def from_env(cls) -> "Settings":
        raw_data_dir = os.getenv("INVENTORY_DATA_DIR", "").strip()
        data_dir = Path(raw_data_dir).expanduser() if raw_data_dir else ROOT_DIR / "data"

        return cls(
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN", "").strip(),
            slack_app_token=os.getenv("SLACK_APP_TOKEN", "").strip(),
            slack_signing_secret=os.getenv("SLACK_SIGNING_SECRET", "").strip(),
            slack_skip_auth_test=os.getenv("SLACK_SKIP_AUTH_TEST", "0").strip().lower()
            in {"1", "true", "yes", "on"},
            data_dir=data_dir,
            port=int(os.getenv("PORT", "3000")),
        )

    def validate(self) -> None:
        if not self.slack_bot_token:
            raise RuntimeError("SLACK_BOT_TOKEN is required.")
        if not self.slack_app_token and not self.slack_signing_secret:
            raise RuntimeError(
                "Set SLACK_APP_TOKEN for Socket Mode or SLACK_SIGNING_SECRET for HTTP mode."
            )
