"""0.15: one good morning each with only what is theirs, the bins out the evening before - from the calendars."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import dt as dt_util

from custom_components.hus_chat import calendars, morning
from custom_components.hus_chat.const import HOUSE

from .test_chat import chat  # noqa: F401


def test_kinds_and_owners() -> None:
    people = [{"id": "person.lilly", "name": "Lilly"}, {"id": "person.holly", "name": "Holly Maria"}, {"id": "person.li", "name": "Li"}]
    assert calendars.kind_of("Skoleskema Lilly Sofie", None) == "school"
    assert calendars.kind_of("Fødselsdage Holly", None) == "birthday"
    assert calendars.kind_of("Affalddk Motelvej 13", "affalddk") == "waste"
    assert calendars.kind_of("Fælles Kalender", None) == "family"
    assert calendars.kind_of("Helligdage i danmark", None) == "holiday"
    assert calendars.kind_of("Clahen86@gmail.com", None) is None  # a private calendar stays out
    assert calendars.owner("Skoleskema Lilly Sofie", people) == "person.lilly"  # "Li" is no whole word in it
    assert calendars.owner("Fødselsdage Holly og Lilly", people) is None  # two fit: nobody's
    assert calendars.owner("Skoleskema Simone", people) is None


def _calendars(hass: HomeAssistant, events: dict[str, list[dict]]) -> None:
    for e in events:
        hass.states.async_set(e, "off", {"friendly_name": {"calendar.skema_lilly": "Skoleskema Lilly", "calendar.skema_wictor": "Skoleskema Wictor",
                                                            "calendar.fodselsdage_lilly": "Fødselsdage Lilly", "calendar.familie": "Familie",
                                                            "calendar.affald": "Affald Motelvej"}[e]})

    async def get_events(call: ServiceCall):
        return {e: {"events": events.get(e, [])} for e in ([call.data["entity_id"]] if isinstance(call.data["entity_id"], str) else call.data["entity_id"])}
    hass.services.async_register("calendar", "get_events", get_events, supports_response=SupportsResponse.ONLY)


async def test_each_gets_only_their_own_morning(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    day = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
    at = lambda h, m=0: (day + timedelta(hours=h, minutes=m)).isoformat()  # noqa: E731
    _calendars(hass, {
        "calendar.skema_lilly": [{"summary": "Dansk", "start": at(8), "end": at(9)}, {"summary": "Idræt", "start": at(12), "end": at(13, 30)}],
        "calendar.skema_wictor": [{"summary": "Matematik", "start": at(8, 15), "end": at(14)}],
        "calendar.fodselsdage_lilly": [{"summary": "Lilly: 🎂 Melina", "start": (day + timedelta(days=7)).date().isoformat(), "end": (day + timedelta(days=8)).date().isoformat()}],
        "calendar.familie": [{"summary": "Tandlæge", "start": at(15), "end": at(16)}],
    })
    admins = {"u-claus"}

    async def adult(p):
        return p.get("user_id") in admins
    with patch.object(type(c), "is_adult", side_effect=adult), patch.object(morning, "weather_line", return_value=None):
        got = {p["id"]: text for p, _t, text in await morning.for_everyone(hass, c, c.people())}
    lilly, wictor, claus = got["person.lilly"], got["person.wictor"], got["user.u-claus"]
    assert "8:00–13:30" in lilly and "Melina" in lilly and "14:00" not in lilly and "Tandlæge" not in lilly
    assert "8:15–14:00" in wictor and "Melina" not in wictor and "13:30" not in wictor
    assert "Lilly 13:30" in claus and "Wictor 14:00" in claus and "Tandlæge" in claus and "Melina" not in claus


async def test_good_morning_is_personal_and_once_a_day(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    c.set_rules({"morning": {"on": True}})
    from custom_components.hus_chat.watch import Watch

    w = Watch(hass, c)
    with patch.object(morning, "weather_line", return_value="☀️ 5° / 1°"):
        await w._morning()
        n = len(c.msgs)
        await w._morning()  # a restart at 7: not twice
    mornings = [m for m in c.msgs if m.get("topic") == "morning"]
    assert len(c.msgs) == n and len(mornings) == 3
    assert all(isinstance(m["to"], list) and len(m["to"]) == 1 for m in mornings)
    assert not c.can_see(next(m for m in mornings if m["to"] == ["person.lilly"]), "u-wictor")


async def test_the_bins_out_the_evening_before_and_gone_at_noon(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    tomorrow = (dt_util.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    _calendars(hass, {"calendar.affald": [{"summary": "Rest & Madaffald", "start": (tomorrow + timedelta(hours=7)).isoformat(),
                                           "end": (tomorrow + timedelta(hours=15)).isoformat()}]})
    from custom_components.hus_chat.watch import Watch

    w = Watch(hass, c)
    await w._waste()
    await w._waste()  # once
    bins = [m for m in c.msgs if m.get("topic") == "waste"]
    assert len(bins) == 1 and "Rest & Madaffald" in bins[0]["title"] and bins[0]["take"] and bins[0]["to"] == "home"
    assert any(x["msg"] == bins[0]["id"] for x in c.now)
    bins[0]["until"] = 0  # noon has passed
    await w._waste_over()
    assert bins[0]["done"] and not any(x["msg"] == bins[0]["id"] for x in c.now)


async def test_a_personal_message_is_not_read_aloud(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    c.speak = {"on": True, "player": "media_player.stue"}
    hass.states.async_set("media_player.stue", "idle")
    with patch.object(type(c), "_say") as say:
        await c.post(HOUSE, "Skole 8–13", kind="house", to=["person.lilly"])
        await c.post(HOUSE, "Vasken er færdig", kind="house", to="home")
        await hass.async_block_till_done()
    assert say.call_count == 1


async def test_only_the_child_and_grown_ups_see_when_school_is_out(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    day = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    _calendars(hass, {"calendar.skema_lilly": [{"summary": "Dansk", "start": (day + timedelta(hours=8)).isoformat(), "end": (day + timedelta(hours=13, minutes=30)).isoformat()}]})

    async def adult(p):
        return p.get("user_id") == "u-claus"
    with patch.object(type(c), "is_adult", side_effect=adult):
        assert "13:30" in await c.local_answer("u-claus", "hvornår har Lilly fri?")
        assert "13:30" in await c.local_answer("u-lilly", "hvornår har Lilly fri?")
        assert "13:30" not in await c.local_answer("u-wictor", "hvornår har Lilly fri?")


def test_a_hyphen_joins_a_name_and_own_calendars_are_nobody_elses() -> None:
    people = [{"id": "person.anne", "name": "Anne"}, {"id": "person.lilly", "name": "Lilly"}]
    assert calendars.owner("Skoleskema Anne-Marie", people) is None
    assert calendars.kind_of("Lillys fridage", None) is None


async def test_a_reply_never_quotes_what_you_may_not_see(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    private = await c.post(HOUSE, "Skole 8–13", kind="house", title="Godmorgen Claus", to=["user.u-claus"])
    r = await c.post("person.lilly", "hej", reply=private["id"])
    assert "reply" not in r
    ok = await c.post("user.u-claus", "tak", reply=private["id"])
    assert ok["reply"]["id"] == private["id"]


def test_every_day_keeps_its_clock_over_summer_time() -> None:
    from custom_components.hus_chat.chat import Chat

    # 02:30 the night before the clocks go forward (Europe/Copenhagen, 29 March 2026): the next stays 02:30-ish, the day after 02:30
    import zoneinfo
    from datetime import datetime

    with patch.object(dt_util, "get_default_time_zone", return_value=zoneinfo.ZoneInfo("Europe/Copenhagen")), \
            patch.object(dt_util, "as_local", side_effect=lambda d: d.astimezone(zoneinfo.ZoneInfo("Europe/Copenhagen"))):
        start = datetime(2026, 3, 27, 2, 30, tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")).timestamp()
        rem = {"when": start, "every": 1, "at": "02:30"}
        for _ in range(4):
            rem["when"] = Chat._next(rem)
        assert datetime.fromtimestamp(rem["when"], zoneinfo.ZoneInfo("Europe/Copenhagen")).strftime("%H:%M") == "02:30"
