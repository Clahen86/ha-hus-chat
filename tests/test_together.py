"""Together with Pligt-pilot and Madplan: machines taken both ways, dinner is ready, who cooks today."""

from datetime import datetime, timedelta

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events, async_fire_time_changed, async_mock_service

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hus_chat.const import HOUSE
from custom_components.hus_chat.watch import Watch, machine_type

from .test_chat import chat  # noqa: F401


def _at(hour: int, days: int = 0) -> datetime:
    return (dt_util.now() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


def test_machine_type_from_the_name():
    assert machine_type("Opvaskemaskine") == "dishwasher" and machine_type("Dishwasher") == "dishwasher"
    assert machine_type("Tørretumbler") == "dryer" and machine_type("Wäschetrockner") == "dryer" and machine_type("Torktumlare") == "dryer"
    assert machine_type("Vaskemaskine") == "washer" and machine_type("Waschmaschine") == "washer" and machine_type("Tvättmaskin") == "washer"
    assert machine_type("Fryser") == "other" and machine_type(None) == "other"


async def test_taken_in_the_chat_and_emptied_is_told(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    told = async_capture_events(hass, "hus_chat_machine")
    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e1", "name": "Vaskemaskine", "kind": "washing_machine"})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert m["mtype"] == "washer"
    await c.take(m["id"], "person.lilly")
    await hass.async_block_till_done()
    assert [e.data for e in told] == [{"kind": "taken", "machine": "washer", "name": "Lilly"}]
    hass.bus.async_fire("appliance_watch_emptied", {"entry_id": "e1", "name": "Vaskemaskine"})
    await hass.async_block_till_done()
    assert told[-1].data == {"kind": "emptied", "machine": "washer", "name": ""}


async def test_an_older_machine_message_finds_its_type_in_appliance_watch(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    aw = MockConfigEntry(domain="appliance_watch", title="Opvasker")
    aw.add_to_hass(hass)
    told = async_capture_events(hass, "hus_chat_machine")
    m = await c.post(HOUSE, "Opvasker færdig", kind="house", take=True, machine=aw.entry_id)
    await c.take(m["id"], "person.lilly")
    await hass.async_block_till_done()
    assert told[0].data["machine"] == "dishwasher"


async def test_a_freezer_or_a_plain_message_is_not_told(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    told = async_capture_events(hass, "hus_chat_machine")
    a = await c.post(HOUSE, "Fryser", kind="house", take=True, machine="aw:e9")
    b = await c.post(HOUSE, "Noget", kind="house", take=True)
    await c.take(a["id"], "person.lilly")
    await c.take(b["id"], "person.lilly")
    await hass.async_block_till_done()
    assert not told


async def test_a_child_takes_the_machine_in_pligt_pilot(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    told = async_capture_events(hass, "hus_chat_machine")
    for entry, name in (("e1", "Tørretumbler"), ("e2", "Vaskemaskine"), ("e3", "Vaskemaskine 2")):
        hass.bus.async_fire("appliance_watch_finished", {"entry_id": entry, "name": name})
        await hass.async_block_till_done()
    dryer, washer, washer2 = c.msgs[-3:]
    hass.bus.async_fire("pligt_pilot_task", {"kind": "taken", "source": "machine", "machine": "washer", "kid": "lilly", "title": "x", "task_id": "1"})
    await hass.async_block_till_done()
    assert washer2["taken"]["by"] == "person.lilly" and washer2["taken"]["name"] == "lilly"  # the newest open one
    assert not washer.get("taken") and not dryer.get("taken")
    assert calls["Claus"][-1].data["message"] == "clear_notification"  # gone from the phones as when tapped
    hass.bus.async_fire("pligt_pilot_task", {"kind": "taken", "source": "machine", "machine": "dryer", "kid": "Silas"})
    hass.bus.async_fire("pligt_pilot_task", {"kind": "taken", "source": "machine", "machine": "other", "kid": "Silas"})
    hass.bus.async_fire("pligt_pilot_task", {"kind": "removed", "source": "machine", "machine": "washer", "kid": "Silas"})
    await hass.async_block_till_done()
    assert dryer["taken"] == {**dryer["taken"], "by": HOUSE, "name": "Silas"} and not washer.get("taken")
    assert not told  # not told back


async def test_dinner_is_ready_to_those_at_home_and_read_aloud(hass: HomeAssistant, chat, freezer) -> None:  # noqa: F811
    c, calls = chat
    hass.states.async_set("tts.google", "idle")
    hass.states.async_set("media_player.stue", "idle", {"friendly_name": "Stue"})
    spoke = async_mock_service(hass, "tts", "speak")
    c.set_speak(True, "media_player.stue")
    freezer.move_to(_at(17))
    hass.bus.async_fire("pligt_pilot_task", {"kind": "done", "source": "meal", "meal": "Lasagne", "kid": "Silas", "title": "Maddag: Lasagne"})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert m["from"] == HOUSE and m["kind"] == "house" and m["to"] == "home" and "Lasagne (Silas)" in m["text"]
    assert calls["Lilly"] and not calls["Wictor"]
    assert spoke and "Lasagne" in spoke[0].data["message"]


async def test_who_cooks_today_once_at_seven(hass: HomeAssistant, chat, freezer) -> None:  # noqa: F811
    c, _ = chat
    freezer.move_to(_at(5))
    day = dt_util.now().date().isoformat()
    ev = {"person": "person.silas", "kid": "Silas", "date": day, "meal": "Tacos", "time": "18:00", "recipe": "", "ingredients": []}
    n = len(c.msgs)
    hass.bus.async_fire("madplan_cook", ev)
    await hass.async_block_till_done()
    assert len(c.msgs) == n  # waits for 7
    freezer.move_to(_at(7) + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert len(c.msgs) == n + 1 and m["to"] == "all" and "Silas" in m["text"] and "Tacos" in m["text"] and "18:00" in m["text"]
    hass.bus.async_fire("madplan_cook", {**ev, "kid": "silas"})  # again in the morning: no second message
    await hass.async_block_till_done()
    assert len(c.msgs) == n + 1


async def test_cooks_later_today_at_once_without_time(hass: HomeAssistant, chat, freezer) -> None:  # noqa: F811
    c, _ = chat
    freezer.move_to(_at(12))
    hass.bus.async_fire("madplan_cook", {"kid": "Lilly", "date": dt_util.now().date().isoformat(), "meal": "Suppe"})
    await hass.async_block_till_done()
    assert c.msgs[-1]["text"].endswith("Suppe")
    hass.bus.async_fire("madplan_cook", {"kid": "Lilly", "date": "2020-01-01", "meal": "Gammel"})  # a day gone by
    hass.bus.async_fire("madplan_cook", {"kid": "Lilly", "date": "i morgen", "meal": "Forkert"})
    await hass.async_block_till_done()
    assert c.msgs[-1]["text"].endswith("Suppe")


async def test_a_day_ahead_is_kept_over_a_restart(hass: HomeAssistant, chat, freezer) -> None:  # noqa: F811
    c, _ = chat
    freezer.move_to(_at(12))
    tomorrow = (dt_util.now() + timedelta(days=1)).date().isoformat()
    hass.bus.async_fire("madplan_cook", {"kid": "Wictor", "date": tomorrow, "meal": "Pizza", "time": "18:30"})
    await hass.async_block_till_done()
    n = len(c.msgs)
    assert c.cooks[f"wictor|{tomorrow}"]["sent"] is False
    watch = Watch(hass, c)  # as after a restart: finds the day in what was kept (the first one waits too)
    watch.start()
    freezer.move_to(_at(7, days=1) + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    said = [m for m in c.msgs[n:] if "Pizza" in m["text"]]
    assert len(said) == 1 and "18:30" in said[0]["text"]  # once, though two were waiting
    assert c.cooks[f"wictor|{tomorrow}"]["sent"] is True
    watch.stop()


async def test_a_child_gets_the_pligt_link_instead_of_take(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat

    class Pligt:
        async def kid_link(self, name: str, machine: str) -> str | None:
            return f"/pligter/k/abcdefgh/?machine={machine}" if name == "Lilly" else None

    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e1", "name": "Vaskemaskine", "kind": "washing_machine"})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert await c.pligt_link(m, "Lilly") is None  # no Pligt-pilot: take it in the chat as before
    hass.data["pligt_pilot"] = Pligt()
    assert await c.pligt_link(m, "Lilly") == "/pligter/k/abcdefgh/?machine=washer"
    assert await c.pligt_link(m, "Far") is None
    push = c._push_data(m, kid_url="/pligter/k/abcdefgh/?machine=washer")
    assert push["data"]["actions"][0] == {"action": "URI", "title": "Take it in Pligter", "uri": "/pligter/k/abcdefgh/?machine=washer"}
    await c.take(m["id"], "person.lilly")
    assert await c.pligt_link(m, "Lilly") is None  # taken: nothing to open
