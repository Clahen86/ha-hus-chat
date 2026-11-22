"""Good morning at 7: each line only when its source is there, nothing when there's nothing to say."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.hus_chat import morning

W = morning.WORDS["en"]


def _now() -> datetime:
    return dt_util.now().replace(hour=7, minute=0, second=0, microsecond=0)


async def test_nothing_to_say_no_message(hass: HomeAssistant) -> None:
    assert await morning.build(hass, _now()) is None


async def test_the_cheapest_three_hours_from_now(hass: HomeAssistant) -> None:
    now = _now()
    prices = []
    for h in range(24):
        for q in range(4):  # quarter hours, as Strømligning gives them
            prices.append({"start": now.replace(hour=h) + timedelta(minutes=15 * q), "price": 0.5 if 2 <= h < 5 else 1.0 if 13 <= h < 16 else 2.0})
    hass.states.async_set("sensor.price", "1", {"prices": prices})
    assert morning.cheap_line(hass, W, now) == "⚡ Cheapest power 13–16"  # the night before 7 has gone


async def test_dinner_from_madplan_today_with_the_cook(hass: HomeAssistant) -> None:
    now, reg = _now(), er.async_get(hass)
    for i, (dish, dato, kok) in enumerate((("Lasagne", now.date().isoformat(), "Silas"), ("Soup", "2000-01-01", None),
                                           ("Før planen", now.date().isoformat(), None))):
        e = reg.async_get_or_create("sensor", "madplan", f"x_dag_{i}")
        hass.states.async_set(e.entity_id, dish, {"dato": dato, "kok_navn": kok})
    assert morning.dinner_line(hass, W, now.date().isoformat()) == "🍽️ Dinner: Lasagne (Silas cooks)"


async def test_chores_from_pligt_pilot(hass: HomeAssistant) -> None:
    async def today():
        return {"Silas": 2, "Holly": 0}

    hass.data["pligt_pilot"] = SimpleNamespace(today=today)
    assert await morning.chores_line(hass, W) == "🧹 Chores today: Silas 2"
    hass.data["pligt_pilot"] = SimpleNamespace()  # an old Pligt-pilot: no line
    assert await morning.chores_line(hass, W) is None
