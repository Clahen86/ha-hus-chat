"""Good morning: one message at 7 with the day ahead - found in Home Assistant, nothing to set up.

Each line only when its source is there (none of them needed):
- the weather today (the first weather entity's daily forecast)
- dinner from Madplan (a day sensor dated today) and who cooks
- chores left today per child in Pligt-pilot
- the cheapest three hours for power the rest of the day (a price sensor with a "prices" list, e.g. Strømligning)

Nothing to say: no message. Off by default - switched on under Settings, "Messages from the house".
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

AT_HOUR = 7
CHEAP_HOURS = 3
SKIP_DISHES = {"", "–", "-", "Før planen", "unknown", "unavailable"}

WORDS = {
    "da": {"title": "☀️ Godmorgen", "weather": "{icon} {hi}° / {lo}°", "rain": "regn {mm} mm", "dinner": "🍽️ Aftensmad: {dish}",
           "cook": "{name} laver den", "chores": "🧹 Pligter i dag: {list}", "cheap": "⚡ Billigst strøm kl. {a}–{b}"},
    "en": {"title": "☀️ Good morning", "weather": "{icon} {hi}° / {lo}°", "rain": "rain {mm} mm", "dinner": "🍽️ Dinner: {dish}",
           "cook": "{name} cooks", "chores": "🧹 Chores today: {list}", "cheap": "⚡ Cheapest power {a}–{b}"},
}
SKY = {"sunny": "☀️", "clear-night": "🌙", "partlycloudy": "⛅", "cloudy": "☁️", "fog": "🌫️", "rainy": "🌧️", "pouring": "🌧️",
       "snowy": "🌨️", "snowy-rainy": "🌨️", "hail": "🌨️", "lightning": "🌩️", "lightning-rainy": "⛈️", "windy": "💨",
       "windy-variant": "💨", "exceptional": "⚠️"}


def words(hass: HomeAssistant) -> dict[str, str]:
    return WORDS.get((hass.config.language or "en").split("-")[0], WORDS["en"])


async def weather_line(hass: HomeAssistant, w: dict[str, str]) -> str | None:
    states = sorted(hass.states.async_all("weather"), key=lambda s: s.entity_id)
    if not states:
        return None
    try:
        res = await hass.services.async_call("weather", "get_forecasts", {"entity_id": states[0].entity_id, "type": "daily"},
                                             blocking=True, return_response=True)
        day = ((res or {}).get(states[0].entity_id) or {}).get("forecast", [])[0]
        hi, lo = round(float(day["temperature"])), round(float(day.get("templow", day["temperature"])))
    except Exception:  # noqa: BLE001 - no daily forecast: no weather line
        return None
    line = w["weather"].format(icon=SKY.get(str(day.get("condition")), "🌡️"), hi=hi, lo=lo)
    mm = day.get("precipitation")
    if isinstance(mm, (int, float)) and mm >= 0.5:
        line += f", {w['rain'].format(mm=round(mm, 1))}"
    return line


def dinner_line(hass: HomeAssistant, w: dict[str, str], today: str) -> str | None:
    seen: list[str] = []
    for e in er.async_get(hass).entities.values():
        if e.platform != "madplan" or e.domain != "sensor":
            continue
        s = hass.states.get(e.entity_id)
        if not s or s.attributes.get("dato") != today or s.attributes.get("fjernet") or s.state in SKIP_DISHES:
            continue
        dish = s.state + (f" ({w['cook'].format(name=s.attributes['kok_navn'])})" if s.attributes.get("kok_navn") else "")
        if dish not in seen:
            seen.append(dish)
    return w["dinner"].format(dish=" / ".join(seen)) if seen else None


async def chores_line(hass: HomeAssistant, w: dict[str, str]) -> str | None:
    get = getattr(hass.data.get("pligt_pilot"), "today", None)
    if not callable(get):
        return None
    try:
        counts = await get()
    except Exception:  # noqa: BLE001
        return None
    left = [f"{name} {n}" for name, n in (counts or {}).items() if isinstance(n, int) and n > 0]
    return w["chores"].format(list=", ".join(left)) if left else None


def cheap_line(hass: HomeAssistant, w: dict[str, str], now: datetime) -> str | None:
    for s in sorted(hass.states.async_all("sensor"), key=lambda s: s.entity_id):
        prices = s.attributes.get("prices")
        if not isinstance(prices, list) or not prices or not isinstance(prices[0], dict) or "start" not in prices[0]:
            continue
        hours: dict[datetime, list[float]] = {}
        for p in prices:
            try:
                start = p["start"] if isinstance(p["start"], datetime) else dt_util.parse_datetime(str(p["start"]))
                start = dt_util.as_local(start)
                if start.date() == now.date() and start.hour >= now.hour:
                    hours.setdefault(start.replace(minute=0, second=0, microsecond=0), []).append(float(p["price"]))
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        keys = sorted(hours)
        if len(keys) < CHEAP_HOURS:
            continue
        avg = {k: sum(v) / len(v) for k, v in hours.items()}
        runs = [keys[i:i + CHEAP_HOURS] for i in range(len(keys) - CHEAP_HOURS + 1)
                if keys[i + CHEAP_HOURS - 1] - keys[i] == timedelta(hours=CHEAP_HOURS - 1)]
        if not runs:
            continue
        best = min(runs, key=lambda r: sum(avg[k] for k in r))
        return w["cheap"].format(a=f"{best[0].hour:02d}", b=f"{(best[-1].hour + 1) % 24:02d}")
    return None


async def build(hass: HomeAssistant, now: datetime | None = None) -> tuple[str, str] | None:
    """(title, text), or None when there's nothing to say."""
    now, w = now or dt_util.now(), words(hass)
    lines = [await weather_line(hass, w), dinner_line(hass, w, now.date().isoformat()), await chores_line(hass, w),
             cheap_line(hass, w, now)]
    lines = [x for x in lines if x]
    return (w["title"], "\n".join(lines)) if lines else None
