"""Who gets a message for those at home when a phone hasn't said where it is, and the daily dinner poll."""

import time
from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hus_chat.const import HOUSE, UNSURE_S

from .test_chat import chat  # noqa: F401 - the family fixture


async def test_away_but_unsure_is_included(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    people = {p["name"]: p for p in c.people()}
    assert not people["Wictor"]["unsure"]  # just reported: surely away
    later = time.time() + UNSURE_S + 60
    with patch("custom_components.hus_chat.chat.time.time", return_value=later):
        assert {p["name"]: p for p in c.people()}["Wictor"]["unsure"]  # no word from the phone for hours: in doubt
    hass.states.async_set("person.wictor", "unknown", {"friendly_name": "Wictor", "user_id": "u-wictor", "device_trackers": []})
    await c.post(HOUSE, "Dæk bord", kind="house", to="home", take=True)
    await hass.async_block_till_done()
    assert len(calls["Wictor"]) == 1  # unknown: gets it too


async def test_the_dinner_poll_and_who_is_told(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    watch = c.watch if hasattr(c, "watch") else None
    from custom_components.hus_chat.watch import Watch

    w = watch or Watch(hass, c)
    c.rules["dinner"] = {"on": True, "at": "15:00"}
    now = dt_util.now().replace(hour=15, minute=0, second=0, microsecond=0)
    await w._dinner_poll(now)
    await w._dinner_poll(now)  # once a day
    polls = [m for m in c.msgs if m.get("topic") == "dinner"]
    assert len(polls) == 1 and [o["t"] for o in polls[0]["poll"]] == ["🙋 Yes", "No"]
    assert c.dinner_people() is None  # nobody answered yet: those at home
    assert c.vote(polls[0]["id"], "u-wictor", 0)
    assert c.dinner_people() == ["person.wictor"]
    await w._dinner_poll(now + timedelta(minutes=1))  # another minute: nothing new
    assert len([m for m in c.msgs if m.get("topic") == "dinner"]) == 1


async def test_send_to_dinner_reaches_only_the_yes(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    m = await c.post(HOUSE, "", kind="house", title="Home for dinner?", poll=["Yes", "No"], topic="dinner")
    c.dinner = {"date": dt_util.now().date().isoformat(), "msg": m["id"]}
    c.vote(m["id"], "u-wictor", 0)
    for k in calls:
        calls[k].clear()
    await hass.services.async_call("hus_chat", "send", {"message": "Maden er klar", "to": "dinner"}, blocking=True)
    await hass.async_block_till_done()
    assert len(calls["Wictor"]) == 1 and not calls["Lilly"]
