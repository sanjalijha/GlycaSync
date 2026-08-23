from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"
ENV_EXAMPLE = ROOT_DIR / ".env.example"


def _on_serverless() -> bool:
    """Vercel/Lambda ship a read-only bundle; only /tmp is writable."""
    return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GlycaSync"
    app_env: str = "demo"
    database_path: str = "data/glycasync.db"
    debounce_seconds: int = 45
    public_base_url: str = "http://localhost:8000"

    @model_validator(mode="before")
    @classmethod
    def empty_env_as_missing(cls, data: Any) -> Any:
        """Vercel often sets env keys to ''; treat those as unset so defaults apply."""
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value != ""}
        return data

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_vision_model: str = "gpt-4o-mini"

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"
    # Approved WhatsApp template, used when a freeform body is not allowed.
    twilio_content_sid: str = ""
    # The webhook writes to patient charts and can trigger an automatic emergency
    # reply, so unsigned requests are refused unless this is deliberately turned off.
    twilio_validate_signature: bool = True

    clinic_name: str = "GlycaSync Diabetes Clinic"
    clinic_city: str = "Mumbai"

    @property
    def db_path(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
            # Relative paths resolve under the deploy bundle, which is read-only on
            # Vercel — SQLite cannot create glycasync.db there.
            if _on_serverless():
                path = Path("/tmp") / "glycasync" / path.name
            else:
                path = ROOT_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def static_dir(self) -> Path:
        path = ROOT_DIR / "ui" / "static"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def media_dir(self) -> Path:
        if _on_serverless():
            path = Path("/tmp") / "glycasync" / "media"
        else:
            path = ROOT_DIR / "data" / "media"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)

    @property
    def sarvam_enabled(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}/webhook/whatsapp"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def upsert_env_keys(updates: dict[str, str], *, path: Path | None = None) -> Path:
    """Write keys into `.env` without dropping comments or unrelated values."""
    dest = path or ENV_PATH
    if not dest.exists() and ENV_EXAMPLE.exists():
        dest.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")

    lines = dest.read_text(encoding="utf-8").splitlines() if dest.exists() else []
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                rewritten.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        rewritten.append(line)
    missing = [key for key in updates if key not in seen]
    if missing:
        if rewritten and rewritten[-1] != "":
            rewritten.append("")
        rewritten.extend(f"{key}={updates[key]}" for key in missing)
    dest.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
    return dest


def apply_settings_updates(updates: dict[str, str], *, path: Path | None = None) -> Settings:
    """Persist values to `.env` and to this process, then reload settings."""
    upsert_env_keys(updates, path=path)
    for key, value in updates.items():
        os.environ[key] = value
    return reload_settings()
