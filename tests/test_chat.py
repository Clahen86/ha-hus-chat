"""House Chat: messages reach the right phones, "I'll take it", quiet hours, answers from the notification."""

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.hus_chat.const import DOMAIN, HOUSE


async def _family(hass: HomeAssistant) -> dict[str, list]:
    """Lilly (at home) and Wictor (away) have a person; Claus has only the app on his phone, no person."""
    calls = {}
    for name, user, home, person in (("Lilly", "u-lilly", True, True), ("Wictor", "u-wictor", False, True), ("Claus", "u-claus", True, False)):
        phone = MockConfigEntry(domain="mobile_app", data={"user_id": user, "device_name": f"{name} phone"})
        phone.add_to_hass(hass)
        dev = dr.async_get(hass).async_get_or_create(config_entry_id=phone.entry_id, identifiers={("mobile_app", name)}, name=f"{name} phone")
        tracker = er.async_get(hass).async_get_or_create("device_tracker", "mobile_app", name, device_id=dev.id, config_entry=phone,
                                                          suggested_object_id=name.lower())
        hass.states.async_set(tracker.entity_id, "home" if home else "not_home")
        calls[name] = async_mock_service(hass, "notify", f"mobile_app_{name.lower()}_phone")
        if person:
            hass.states.async_set(f"person.{name.lower()}", "home" if home else "not_home",
                                  {"friendly_name": name, "user_id": user, "device_trackers": [tracker.entity_id]})
    return calls


@pytest.fixture
async def chat(hass: HomeAssistant):
    calls = await _family(hass)
    entry = MockConfigEntry(domain=DOMAIN, title="House Chat")
    entry.add_to_hass(hass)
    with patch("custom_components.hus_chat.support.Support.async_setup"), patch("custom_components.hus_chat.support.Support.unload"):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entry.runtime_data.users = {"u-lilly": "Lilly", "u-wictor": "Wictor", "u-claus": "Claus"}
        yield entry.runtime_data, calls


async def test_finds_the_family_and_their_phones(chat) -> None:
    c, _ = chat
    people = {p["name"]: p for p in c.people()}
    assert people["Lilly"]["phones"] == ["mobile_app_lilly_phone"] and people["Lilly"]["home"]
    assert people["Wictor"]["home"] is False


async def test_a_message_goes_to_the_others(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    await c.post("person.lilly", "Kan nogen købe mælk?")
    await hass.async_block_till_done()
    assert not calls["Lilly"] and len(calls["Wictor"]) == 1
    data = calls["Wictor"][0].data
    assert data["title"] == "Lilly" and data["message"] == "Kan nogen købe mælk?"
    assert any(a["action"] == "REPLY" for a in data["data"]["actions"])


async def test_house_message_to_those_at_home_and_take(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    await hass.services.async_call(DOMAIN, "send", {"message": "Vaskemaskinen er færdig", "take": True}, blocking=True)
    await hass.async_block_till_done()
    assert len(calls["Lilly"]) == 1 and len(calls["Claus"]) == 1 and not calls["Wictor"]
    m = c.msgs[-1]
    assert m["from"] == HOUSE and m["take"]
    await c.take(m["id"], "person.lilly")
    await hass.async_block_till_done()
    assert m["taken"]["name"] == "Lilly"
    assert calls["Lilly"][-1].data["message"] == "clear_notification"  # gone from the phones


async def test_nobody_home_goes_to_everyone(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    hass.states.async_set("person.lilly", "not_home", {**hass.states.get("person.lilly").attributes})
    hass.states.async_set("device_tracker.claus", "not_home")
    await c.post(HOUSE, "Døren er åben", kind="house", to="home")
    await hass.async_block_till_done()
    assert len(calls["Lilly"]) == 1 and len(calls["Wictor"]) == 1


async def test_quiet_hours_but_urgent_comes_through(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    c.set_prefs("u-wictor", {"quiet": True, "quiet_from": "00:00", "quiet_to": "23:59"})
    await c.post("person.lilly", "Godnat")
    await c.post(HOUSE, "Vand i kælderen", kind="house", to="all", urgent=True)
    await hass.async_block_till_done()
    assert [x.data["message"] for x in calls["Wictor"]] == ["Vand i kælderen"]


async def test_answer_from_the_notification(hass: HomeAssistant, chat) -> None:
    c, _ = chat
    hass.bus.async_fire("mobile_app_notification_action", {"action": "REPLY", "reply_text": "Jeg tager den", "tag": "huschat-x"},
                        context=Context(user_id="u-wictor"))
    await hass.async_block_till_done()
    assert c.msgs[-1]["from"] == "person.wictor" and c.msgs[-1]["text"] == "Jeg tager den"
    hass.bus.async_fire("mobile_app_notification_action", {"action": "REPLY", "reply_text": "ikke vores", "tag": "andet"},
                        context=Context(user_id="u-wictor"))
    await hass.async_block_till_done()
    assert c.msgs[-1]["text"] == "Jeg tager den"  # another integration's reply is left alone


async def test_websocket(hass: HomeAssistant, chat, hass_ws_client, hass_admin_user) -> None:
    c, _ = chat
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "hus_chat/subscribe"})
    assert (await client.receive_json())["success"]
    init = (await client.receive_json())["event"]
    assert init["type"] == "init" and init["prefs"]["bubble"] is True
    await client.send_json_auto_id({"type": "hus_chat/send", "text": "Hej"})
    ev = await client.receive_json()
    res = await client.receive_json()
    got = {ev.get("type"): ev, res.get("type"): res}
    assert got["event"]["event"]["message"]["text"] == "Hej" and got["result"]["success"]
    await client.send_json_auto_id({"type": "hus_chat/prefs", "quiet": True})
    r = await client.receive_json()
    assert r["result"]["quiet"] is True


async def test_notify_entity(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    ent = next(e.entity_id for e in er.async_entries_for_config_entry(er.async_get(hass), hass.config_entries.async_entries(DOMAIN)[0].entry_id))
    await hass.services.async_call("notify", "send_message", {"entity_id": ent, "message": "Hej fra huset"}, blocking=True)
    await hass.async_block_till_done()
    assert c.msgs[-1]["text"] == "Hej fra huset" and len(calls["Lilly"]) == 1


async def test_nobody_took_it_goes_to_everyone_after_10_minutes(hass: HomeAssistant, chat) -> None:
    from datetime import timedelta

    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    from homeassistant.util import dt as dt_util

    c, calls = chat
    await c.post(HOUSE, "Vaskemaskinen er færdig", kind="house", to="home", take=True)
    await hass.async_block_till_done()
    assert len(calls["Lilly"]) == 1 and not calls["Wictor"]
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()
    assert len(calls["Wictor"]) == 1 and "Ingen har reageret" in calls["Wictor"][0].data["message"] or "Nobody" in calls["Wictor"][0].data["message"]


async def test_someone_with_only_the_app_is_in_it(hass: HomeAssistant, chat) -> None:
    """No person in Home Assistant: found from the app on the phone, at home from the phone's own location."""
    c, calls = chat
    claus = next(p for p in c.people() if p["name"] == "Claus")
    assert claus["id"] == "user.u-claus" and claus["phones"] == ["mobile_app_claus_phone"] and claus["home"]
    await c.post("person.lilly", "Hej Claus")
    await hass.async_block_till_done()
    assert calls["Claus"][0].data["title"] == "Lilly"
    hass.bus.async_fire("mobile_app_notification_action", {"action": "REPLY", "reply_text": "Hej!", "tag": "huschat-x"},
                        context=Context(user_id="u-claus"))
    await hass.async_block_till_done()
    assert c.msgs[-1]["from"] == "user.u-claus" and c.msgs[-1]["name"] == "Claus"
