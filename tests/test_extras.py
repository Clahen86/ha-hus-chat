"""The extras: polls, pin, reminders, the shopping list, on my way home, read aloud."""

from datetime import timedelta
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from homeassistant.core import HomeAssistant, ServiceResponse, SupportsResponse
from homeassistant.util import dt as dt_util

from custom_components.hus_chat.const import HOUSE

from .test_chat import chat  # noqa: F401


async def test_poll_votes_once_per_person(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    m = await c.post("person.lilly", "Pizza eller burger?", poll=["Pizza", "Burger"])
    assert c.vote(m["id"], "u-wictor", 0) and c.vote(m["id"], "u-wictor", 1)
    assert m["poll"][0]["votes"] == [] and m["poll"][1]["votes"] == ["person.wictor"]
    assert c.vote(m["id"], "u-wictor", 1) and m["poll"][1]["votes"] == []  # tapped again: taken back
    assert not c.vote(m["id"], "u-wictor", 5)


async def test_pin_and_delete_unpins(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    m = await c.post("person.lilly", "Wifi-kode: 1234")
    assert c.pin(m["id"]) and c.pinned == m["id"]
    await c.delete(m["id"], "u-lilly", False)
    assert c.pinned is None


async def test_a_reminder_comes_back_at_the_time(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    m = await c.post("person.wictor", "mind mig om at tage vasketøjet om 20 min")
    await hass.async_block_till_done()
    assert m.get("remind") and len(c.reminders) == 1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=21))
    await hass.async_block_till_done()
    last = c.msgs[-1]
    assert last["from"] == HOUSE and "Tage vasketøjet" in last["text"] and last["to"] == ["person.wictor"]
    assert not c.reminders


async def test_deleting_the_message_cancels_the_reminder(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    m = await c.post("person.wictor", "mind mig om tandlæge i morgen kl. 8")
    await c.delete(m["id"], "u-wictor", False)
    assert not c.reminders


async def test_buy_goes_on_the_shopping_list(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.states.async_set("todo.shopping_list", "0", {"friendly_name": "Indkøbsliste"})
    added = async_mock_service(hass, "todo", "add_item")
    m = await c.post("person.lilly", "køb mælk og æg")
    await hass.async_block_till_done()
    assert [x.data["item"] for x in added] == ["Mælk", "Æg"] and m["shop"] == ["Mælk", "Æg"]


async def test_on_my_way_and_home(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.states.async_set("person.wictor", "not_home", {"friendly_name": "Wictor", "user_id": "u-wictor", "latitude": 55.70, "longitude": 12.40})
    hass.config.latitude, hass.config.longitude = 55.6761, 12.5683
    m = await c.on_my_way("person.wictor")
    assert m["text"].startswith("🚗") and "kl." in m["text"] or "about" in m["text"]
    hass.states.async_set("person.wictor", "home", {"friendly_name": "Wictor", "user_id": "u-wictor"})
    await hass.async_block_till_done()
    assert c.msgs[-1]["from"] == HOUSE and "Wictor" in c.msgs[-1]["text"]


async def test_house_messages_read_aloud(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.states.async_set("tts.google", "idle")
    hass.states.async_set("media_player.stue", "idle", {"friendly_name": "Stue"})
    spoke = async_mock_service(hass, "tts", "speak")
    c.set_speak(True, "media_player.stue")
    with patch("custom_components.hus_chat.chat.dt_util.now", return_value=dt_util.now().replace(hour=15)):
        await c.post(HOUSE, "Vaskemaskinen er færdig", kind="house", to="all")
        await hass.async_block_till_done()
    assert spoke and spoke[0].data["media_player_entity_id"] == "media_player.stue" and "Vaskemaskinen" in spoke[0].data["message"]
    spoke.clear()
    with patch("custom_components.hus_chat.chat.dt_util.now", return_value=dt_util.now().replace(hour=23)):
        await c.post(HOUSE, "Tørretumbleren er færdig", kind="house", to="all")
        await hass.async_block_till_done()
    assert not spoke  # not at night
