from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import aiohttp

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AlertCandidate:
    source: str
    title: str
    body: str
    severity: str

    @property
    def dedupe_key(self) -> str:
        raw = f"{self.source}|{self.title}|{self.body}|{self.severity}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


async def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    timeout = aiohttp.ClientTimeout(total=20, connect=10, sock_connect=10, sock_read=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers) as response:
            response.raise_for_status()
            return await response.json()


CONDITION_LABELS = {
    "clear": "ясно",
    "partly-cloudy": "переменная облачность",
    "cloudy": "облачно",
    "overcast": "пасмурно",
    "fog": "туман",
    "thunderstorm": "гроза",
    "thunderstorm-with-rain": "гроза с дождём",
    "wet-snow": "мокрый снег",
    "hail": "град",
}


async def check_yandex_weather(api_key: str | None, city_name: str, latitude: float | None, longitude: float | None) -> AlertCandidate | None:
    if not api_key or latitude is None or longitude is None:
        return None
    url = f"https://api.weather.yandex.ru/v2/forecast?lat={latitude}&lon={longitude}&lang=ru_RU&limit=1&hours=false&extra=false"
    data = await _get_json(url, headers={"X-Yandex-Weather-Key": api_key})
    fact = data.get("fact", {})
    condition = str(fact.get("condition", "")).strip()
    temp = fact.get("temp")
    wind = float(fact.get("wind_speed") or 0)
    gust = float(fact.get("wind_gust") or 0)

    hazard = None
    if gust >= 15 or wind >= 15:
        hazard = f"сильный ветер, порывы до {max(gust, wind):g} м/с"
    elif condition in {"fog", "hail", "thunderstorm", "thunderstorm-with-rain", "wet-snow"}:
        hazard = CONDITION_LABELS.get(condition, condition)
    elif isinstance(temp, (int, float)) and temp >= 30:
        hazard = f"жара до {temp}°C"
    elif isinstance(temp, (int, float)) and temp <= -25:
        hazard = f"сильный мороз до {temp}°C"

    if not hazard:
        return None
    return AlertCandidate(
        source="yandex_weather",
        title=f"Погодный риск в {city_name}",
        body=f"Выявлен риск: {hazard}. Проверьте, нужно ли выпускать локальное предупреждение.",
        severity="warning",
    )


async def check_open_meteo(city_name: str, latitude: float | None, longitude: float | None) -> AlertCandidate | None:
    if latitude is None or longitude is None:
        return None
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        "&current=temperature_2m,wind_speed_10m,weather_code"
        "&timezone=auto"
    )
    data = await _get_json(url)
    current = data.get("current", {})
    weather_code = int(current.get("weather_code", -1) or -1)
    temp = float(current.get("temperature_2m", 0) or 0)
    wind = float(current.get("wind_speed_10m", 0) or 0)

    hazard = None
    if wind >= 15:
        hazard = f"сильный ветер {wind} м/с"
    elif temp >= 30:
        hazard = f"жара {temp}°C"
    elif temp <= -25:
        hazard = f"сильный мороз {temp}°C"
    elif weather_code in {45, 48}:
        hazard = "туман"
    elif weather_code in {95, 96, 99}:
        hazard = "гроза"

    if not hazard:
        return None
    return AlertCandidate(
        source="open_meteo",
        title=f"Погодный риск в {city_name}",
        body=f"Выявлен риск: {hazard}. Проверьте, нужно ли выпускать локальное предупреждение.",
        severity="warning",
    )


async def check_weather(city_name: str, latitude: float | None, longitude: float | None, yandex_api_key: str | None) -> AlertCandidate | None:
    if yandex_api_key:
        try:
            return await check_yandex_weather(yandex_api_key, city_name, latitude, longitude)
        except aiohttp.ClientResponseError as exc:
            if exc.status in {401, 403, 404, 429}:
                logger.warning("Yandex Weather unavailable (%s), switching to Open-Meteo", exc.status)
            else:
                logger.warning("Yandex Weather request failed (%s), switching to Open-Meteo", exc.status)
        except aiohttp.ClientError as exc:
            logger.warning("Yandex Weather network error, switching to Open-Meteo: %s", exc)
        except Exception:
            logger.exception("Yandex Weather check failed, switching to Open-Meteo")

    try:
        return await check_open_meteo(city_name, latitude, longitude)
    except aiohttp.ClientError as exc:
        logger.warning("Open-Meteo unavailable: %s", exc)
        return None
    except Exception:
        logger.exception("Open-Meteo check failed")
        return None


async def check_mchs_source(url: str | None) -> AlertCandidate | None:
    if not url:
        return None
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            text = (await response.text()).lower()
    keywords = ["шторм", "гроза", "пожар", "угроза", "эвакуац", "туман", "голол"]
    hits = [kw for kw in keywords if kw in text]
    if not hits:
        return None
    return AlertCandidate(
        source="mchs_source",
        title="Найдено возможное внешнее предупреждение",
        body=f"Во внешнем источнике найдены маркеры: {', '.join(hits)}.",
        severity="info",
    )
