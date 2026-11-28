"""0.16: what to bring from the timetable, the weather when it matters (child, bigger child, grown-up), news from school,
the cook's start time, and when school starts."""

from datetime import datetime, timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hus_chat import morning, smart

from .test_calendars import _calendars
from .test_chat import chat  # noqa: F401

W = morning.WORDS["da"]


def test_what_to_bring() -> None:
    assert smart.bring(["IDR, Helene", "DAN, Maria", "IDR, Sille"]) == ["pe"]
    assert smart.bring(["SVØ, X", "Tur til Zoo"]) == ["swim", "trip"]
    assert smart.bring(["MAT, Per", "Idrætsdag?"]) == []  # not a PE lesson's subject


def _h(day, hour, **k):
    return {"t": day + timedelta(hours=hour), "rain": False, "snow": False, "temp": 5, "wind_ms": 3, **k}


def test_weather_for_a_child_a_bigger_child_and_the_grown_ups() -> None:
    day = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hours = [_h(day, 7, temp=-2), _h(day, 13, rain=True), _h(day, 14, rain=True), _h(day, 18)]
    kid = morning.weather_advice(hours, [(day + timedelta(hours=7), day + timedelta(hours=8), "go"),
                                         (day + timedelta(hours=13, minutes=30), day + timedelta(hours=14, minutes=30), "home")], W, "kid")
    assert any("regnjakke" in x and "hjem" in x for x in kid) and any("Frost" in x for x in kid)
    big = morning.weather_advice(hours, [(day + timedelta(hours=7), day + timedelta(hours=9), "go"),
                                         (day + timedelta(hours=14), day + timedelta(hours=17), "home")], W, "big")
    assert "Regn kl. 14 – tag jakke." in big
    ad = morning.weather_adult(hours, {"person.lilly": (day + timedelta(hours=8), day + timedelta(hours=13, minutes=50))}, {"person.lilly": "Lilly"}, W)
    assert ad.startswith("🌧️ Regn 13–15") and "Lilly har fri i det" in ad
    assert morning.weather_advice([_h(day, 8), _h(day, 15)], [(day + timedelta(hours=7), day + timedelta(hours=9), "go")], W, "kid") == []  # fine weather: nothing


async def test_the_morning_brings_it_together(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.config.language = "da"
    day = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    _calendars(hass, {"calendar.skema_lilly": [{"summary": "IDR, Helene", "start": (day + timedelta(hours=8)).isoformat(), "end": (day + timedelta(hours=13, minutes=50)).isoformat()}]})
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    aula = MockConfigEntry(domain="aula")
    aula.add_to_hass(hass)
    ent = er.async_get(hass).async_get_or_create("binary_sensor", "aula", "msg", suggested_object_id="aula_message", config_entry=aula)
    hass.states.async_set(ent.entity_id, "on", {"subject": "Juleklip fredag", "sender": "Søren", "text": "<p>Kære forældre</p>"})
    c.cooks = {"lilly|x": {"kid": "Lilly", "meal": "Kyllingewok", "time": "18:00", "date": dt_util.now().date().isoformat(), "sent": False}}
    hours = [_h(day, 13, rain=True), _h(day, 14, rain=True)]

    async def adult(p):
        return p.get("user_id") == "u-claus"
    with patch.object(type(c), "is_adult", side_effect=adult), patch.object(morning, "weather_line", return_value=None), \
            patch.object(morning, "weather_hours", return_value=hours):
        got = {p["id"]: text for p, _t, text, _g in await morning.for_everyone(hass, c, c.people())}
        again = {p["id"]: text for p, _t, text, _g in await morning.for_everyone(hass, c, c.people())}
    lilly, claus = got["person.lilly"], got["user.u-claus"]
    assert "Husk idrætstøj" in lilly and "regnjakke" in lilly and "Kyllingewok" in lilly and "18:00" in lilly
    assert "Juleklip fredag" in claus and "Juleklip" not in lilly and "idrætstøj" not in claus
    assert "Regn 13–15" in claus and "Lilly har fri i det" in claus
    assert "Juleklip" not in again["user.u-claus"]  # told once


async def test_when_school_starts_and_the_whole_day(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.config.language = "da"
    now = dt_util.now()
    mon = (now + timedelta(days=(0 - now.weekday()) % 7 or 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    _calendars(hass, {"calendar.skema_lilly": [{"summary": "DAN", "start": (mon + timedelta(hours=8)).isoformat(), "end": (mon + timedelta(hours=13, minutes=5)).isoformat()}]})
    a = await c.local_answer("u-lilly", "Hvornår møder Lilly på mandag?")
    assert "møder" in a and "8:00" in a and "13:05" not in a
    b = await c.local_answer("u-lilly", "hvordan ser Lillys mandag ud")
    assert "8:00" in b and "13:05" in b
    assert "13:05" in await c.local_answer("u-lilly", "hvornår har Lilly fri mandag")


def test_not_every_start_is_school() -> None:
    assert smart.question("Hvornår starter Lilly til fodbold?", ["Lilly"]) is None
    assert smart.question("Hvordan ser vejret ud i dag for børnene?", ["Lilly"]) is None
    assert smart.question("Hvornår skal Lilly af sted?", ["Lilly"]) == ("school", "Lilly") and smart.school_mode("Hvornår skal Lilly af sted?") == "start"
    assert smart.school_mode("Hvornår skal Lilly i skole?") == "start"


def test_rain_in_two_runs_and_units() -> None:
    day = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    hours = [_h(day, 8, rain=True), _h(day, 17, rain=True)]
    ad = morning.weather_adult(hours, {"person.lilly": (day + timedelta(hours=8), day + timedelta(hours=14))}, {"person.lilly": "Lilly"}, W)
    assert "8–9, 17–18" in ad and "Lilly" not in ad  # out of school at 14, between the showers
