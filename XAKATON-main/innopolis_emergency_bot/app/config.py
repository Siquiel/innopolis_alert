from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _csv_ints(raw: str | None) -> list[int]:
    values: list[int] = []
    if not raw:
        return values
    for part in raw.split(","):
        part = part.strip()
        if part:
            values.append(int(part))
    return values


@dataclass(slots=True, frozen=True)
class Config:
    bot_token: str
    admin_ids: list[int]
    moderator_chat_id: int | None
    database_path: str
    city_name: str
    latitude: float | None
    longitude: float | None
    check_interval_minutes: int
    google_api_key: str | None
    google_model: str
    groq_api_key: str | None
    yandex_weather_api_key: str | None
    mchs_source_url: str | None
    postgres_dsn: str | None


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")

    def _maybe_float(name: str) -> float | None:
        raw = os.getenv(name, "").strip()
        return float(raw) if raw else None

    def _maybe_int(name: str) -> int | None:
        raw = os.getenv(name, "").strip()
        return int(raw) if raw else None

    return Config(
        bot_token=bot_token,
        admin_ids=_csv_ints(os.getenv("ADMIN_IDS")),
        moderator_chat_id=_maybe_int("MODERATOR_CHAT_ID"),
        database_path=os.getenv("DATABASE_PATH", "bot.db").strip(),
        city_name=os.getenv("CITY_NAME", "Innopolis").strip(),
        latitude=_maybe_float("LATITUDE"),
        longitude=_maybe_float("LONGITUDE"),
        check_interval_minutes=int(os.getenv("CHECK_INTERVAL_MINUTES", "10")),
        google_api_key=os.getenv("GOOGLE_API_KEY", "").strip() or None,
        google_model=os.getenv("GOOGLE_MODEL", "gemini-2.0-flash").strip(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip() or None,
        yandex_weather_api_key=os.getenv("YANDEX_WEATHER_API_KEY", "").strip() or None,
        mchs_source_url=os.getenv("MCHS_SOURCE_URL", "").strip() or None,
        postgres_dsn=os.getenv("POSTGRES_DSN", "").strip() or None,
    )
