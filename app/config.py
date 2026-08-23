from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


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

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_vision_model: str = "gpt-4o-mini"

    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    clinic_name: str = "GlycaSync Diabetes Clinic"
    clinic_city: str = "Mumbai"

    @property
    def db_path(self) -> Path:
        path = Path(self.database_path)
        if not path.is_absolute():
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
