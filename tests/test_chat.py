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
    got = {}
    while "result" not in got or "message" not in got:  # the message, "read" (seen by) and the answer, in any order
        x = await client.receive_json()
        got[x["event"]["type"] if x.get("type") == "event" else x["type"]] = x
    assert got["message"]["event"]["message"]["text"] == "Hej" and got["result"]["success"]
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


async def test_an_old_phone_can_be_turned_off_and_one_gone_for_30_days_is_skipped(hass: HomeAssistant, chat) -> None:
    import time as _time

    c, calls = chat
    c.set_prefs("u-claus", {"phones_off": ["mobile_app_claus_phone"]})
    assert next(p for p in c.people() if p["name"] == "Claus")["phones"] == []
    assert c.phones_of["u-claus"][0]["on"] is False
    c.set_prefs("u-claus", {"phones_off": []})
    hass.states.async_set("device_tracker.wictor", "unavailable")
    c.seen["mobile_app_wictor_phone"] = _time.time() - 31 * 86400
    assert next(p for p in c.people() if p["name"] == "Wictor")["phones"] == []
    assert c.phones_of["u-wictor"][0]["stale"] is True
    await c.post("person.lilly", "Hej")
    await hass.async_block_till_done()
    assert not calls["Wictor"] and len(calls["Claus"]) == 1


async def test_machine_done_then_emptied(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e1", "name": "Vaskemaskine", "kind": "washing_machine"})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert m["topic"] == "machines" and "Vaskemaskine" in m["title"] and m["take"]
    assert len(calls["Lilly"]) == 1 and not calls["Wictor"]  # only those at home
    hass.bus.async_fire("appliance_watch_emptied", {"entry_id": "e1", "name": "Vaskemaskine"})
    await hass.async_block_till_done()
    assert m["taken"]["by"] == HOUSE
    assert calls["Lilly"][-1].data["message"] == "clear_notification"


async def test_smoke_rings_on_everyone_even_in_quiet_hours_and_muted(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    c.set_prefs("u-wictor", {"quiet": True, "quiet_from": "00:00", "quiet_to": "23:59", "muted": ["safety"], "push": False})
    hass.states.async_set("binary_sensor.roeg_koekken", "off", {"device_class": "smoke", "friendly_name": "Røg køkken"})
    await hass.async_block_till_done()
    hass.states.async_set("binary_sensor.roeg_koekken", "on", {"device_class": "smoke", "friendly_name": "Røg køkken"})
    await hass.async_block_till_done()
    assert c.msgs[-1]["urgent"] and c.msgs[-1]["topic"] == "safety"
    data = calls["Wictor"][-1].data["data"]
    assert data["channel"] == "alarm_stream" and data["push"]["sound"]["critical"] == 1  # rings like an alarm


async def test_who_gets_what_and_muting(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    c.set_rules({"doorbell": {"to": ["person.wictor"]}})
    hass.states.async_set("event.doerklokke", "2026-11-14T10:00:00", {"device_class": "doorbell"})
    await hass.async_block_till_done()
    hass.states.async_set("event.doerklokke", "2026-11-14T10:05:00", {"device_class": "doorbell"})
    await hass.async_block_till_done()
    assert len(calls["Wictor"]) == 1 and not calls["Lilly"] and not calls["Claus"]
    c.set_prefs("u-lilly", {"muted": ["machines"]})
    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e2", "name": "Opvasker", "kind": "dishwasher"})
    await hass.async_block_till_done()
    assert not calls["Lilly"] and len(calls["Claus"]) == 1
    c.set_rules({"machines": {"on": False}})
    n = len(c.msgs)
    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e3", "name": "Tørretumbler", "kind": "dryer"})
    await hass.async_block_till_done()
    assert len(c.msgs) == n  # turned off for the family


async def test_a_freezer_that_stopped_rings_everyone_and_clears(hass: HomeAssistant, chat) -> None:
    c, calls = chat
    hass.bus.async_fire("appliance_watch_alert", {"entry_id": "f1", "name": "Fryser", "kind": "freezer", "reason": "stopped", "ok": False})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert m["urgent"] and "Fryser" in m["title"] and calls["Lilly"][-1].data["data"]["channel"] == "alarm_stream"  # to those at home (the machines rule)
    hass.bus.async_fire("appliance_watch_alert", {"entry_id": "f1", "name": "Fryser", "kind": "freezer", "reason": "stopped", "ok": True})
    await hass.async_block_till_done()
    assert m["taken"]["by"] == HOUSE


def _reply(cid, kind, text):
    from types import SimpleNamespace

    return SimpleNamespace(conversation_id=cid, response=SimpleNamespace(response_type=SimpleNamespace(value=kind), speech={"plain": {"speech": text}}))


def _fake_conversation(fake):
    """Home Assistant's conversation swapped for a fake - also when the real one was imported by another test."""
    import contextlib
    import sys

    import homeassistant.components as components

    stack = contextlib.ExitStack()
    stack.enter_context(patch.dict(sys.modules, {"homeassistant.components.conversation": fake}))
    stack.enter_context(patch.object(components, "conversation", fake, create=True))
    return stack


async def test_the_chosen_ai_answers_for_the_house(hass: HomeAssistant, chat) -> None:
    """Home Assistant's own first (like "prefer local commands"); what it doesn't understand goes to the chosen AI -
    nothing chosen: the one Assist uses. A removed AI: Home Assistant's own answers."""
    import sys
    from types import SimpleNamespace

    c, _ = chat
    hass.states.async_set("conversation.google_ai", "unknown", {"friendly_name": "Google AI"})
    seen = []

    async def converse(_hass, text, conversation_id, context, language=None, agent_id=None):
        seen.append(agent_id)
        if agent_id is None:  # Home Assistant's own knows only "Sluk lyset"
            return _reply("h", "action_done", "Slukket") if text == "Sluk lyset" else _reply("h", "error", "Forstod ikke")
        return _reply("c1", "query_answer", "Ja")

    with _fake_conversation(SimpleNamespace(async_converse=converse)), \
            patch.object(type(c), "assist_agent", lambda self: "conversation.google_ai"):
        assert c.agents()["assist"] == "conversation.google_ai" and c.agents()["chosen"] is None
        m = await c.ask_house("u-claus", "Sluk lyset")
        assert m["text"] == "Slukket" and seen == [None]  # done at once, no AI
        m = await c.ask_house("u-claus", "Er døren låst?")
        assert m["text"] == "Ja" and seen[1:] == [None, "conversation.google_ai"]
        hass.states.async_set("conversation.openai", "unknown", {"friendly_name": "OpenAI"})
        assert c.set_agent("conversation.openai")["chosen"] == "conversation.openai"
        await c.ask_house("u-claus", "Og køkkenet?")
        assert seen[-1] == "conversation.openai"
        hass.states.async_remove("conversation.openai")
        seen.clear()
        m = await c.ask_house("u-claus", "Hej")
        assert seen == [None] and m["text"] == "Forstod ikke"


async def test_falls_back_to_home_assistant_when_the_ai_cant_answer(hass: HomeAssistant, chat) -> None:
    """A used-up AI: Home Assistant's own Assist answers with a note, and the AI isn't asked again for 30 minutes."""
    import sys
    from types import SimpleNamespace

    c, _ = chat
    hass.states.async_set("conversation.google_ai", "unknown", {"friendly_name": "Google AI"})
    c.set_agent("conversation.google_ai")
    seen = []

    async def converse(_hass, text, conversation_id, context, language=None, agent_id=None):
        seen.append(agent_id)
        if agent_id == "conversation.google_ai":
            return _reply("g", "error", "Quota exceeded")
        return _reply("h", "error", "Undskyld, det forstod jeg ikke")

    with _fake_conversation(SimpleNamespace(async_converse=converse)):
        m = await c.ask_house("u-claus", "Hvad skal vi have at spise?")
        assert seen == [None, "conversation.google_ai", None]
        assert m["text"] == "Undskyld, det forstod jeg ikke" and "Google AI" in m["note"]
        await c.ask_house("u-claus", "Og i morgen?")
        assert seen[3:] == [None, None]  # the AI isn't asked again within 30 minutes


async def test_an_ai_that_hangs_is_given_up(hass: HomeAssistant, chat) -> None:
    import asyncio
    import sys
    from types import SimpleNamespace

    c, _ = chat
    hass.states.async_set("conversation.google_ai", "unknown", {"friendly_name": "Google AI"})
    c.set_agent("conversation.google_ai")

    async def converse(_hass, text, conversation_id, context, language=None, agent_id=None):
        if agent_id:
            await asyncio.sleep(10)
        return _reply("h", "error", "Forstod ikke")

    with _fake_conversation(SimpleNamespace(async_converse=converse)), \
            patch("custom_components.hus_chat.chat.AI_TIMEOUT_S", 0.05):
        m = await c.ask_house("u-claus", "Fortæl en historie")
        assert m["note"] and m["text"] == "Forstod ikke"


async def test_setup_for_the_developer(hass: HomeAssistant, chat) -> None:
    """The daily setup: counts and which messages are on - never names."""
    from custom_components.hus_chat.support import Support

    c, _ = chat
    s = Support(hass, DOMAIN, "hus-chat", "House Chat")
    info = c.setup_info(s)
    assert info["counts"]["phones"] == 3 and info["counts"]["persons"] == 2
    assert info["features"]["msg_machines"] is True and info["features"]["msg_alarm"] is False
    text = str(info)
    assert "Lilly" not in text and "Wictor" not in text and "Claus" not in text


async def test_privacy_and_unread(hass: HomeAssistant, chat) -> None:
    c, _ = chat
    await c.post(HOUSE, "Kun til Lilly", kind="house", to=["person.lilly"])
    await c.post(HOUSE, "Til alle", kind="house", to="all")
    await c.post("person.wictor", "Hej")
    seen_w = [m["text"] for m in c.visible("u-wictor")]
    assert "Kun til Lilly" not in seen_w and "Til alle" in seen_w
    assert "Kun til Lilly" in [m["text"] for m in c.visible("u-lilly")]
    assert c.unread("u-wictor") == 1  # "Til alle" - not his own, not Lilly's
    assert c.visible("u-kiosk") == []  # no person, no phone: not in the family chat
    assert c.visible("u-kiosk", admin=True)  # an admin is


async def test_delete_edit_react_and_dedupe(hass: HomeAssistant, chat) -> None:
    c, _ = chat
    m = await c.post("person.lilly", "Hej", cid="abc")
    assert await c.post("person.lilly", "Hej", cid="abc") is m  # sent again after a lost connection
    assert c.edit(m["id"], "u-lilly", "Hej igen") and m["text"] == "Hej igen" and m["edited"]
    assert not c.edit(m["id"], "u-wictor", "nej")  # not his
    assert c.react(m["id"], "u-wictor", "👍") and m["reactions"] == {"👍": ["person.wictor"]}
    c.react(m["id"], "u-wictor", "👍")
    assert m["reactions"] == {}
    r = await c.post("person.wictor", "Svar", reply=m["id"])
    assert r["reply"]["text"] == "Hej igen"
    assert not await c.delete(m["id"], "u-wictor", admin=False)
    assert await c.delete(m["id"], "u-lilly", admin=False) and c.find(m["id"]) is None


async def test_machine_message_after_restart(hass: HomeAssistant, chat) -> None:
    c, _ = chat
    m = await c.post(HOUSE, "Opvasker færdig", kind="house", take=True, to="home", machine="entry1")
    assert c.machine_message("entry1") is m and m.get("sent") is not None
    c.stop()
    c._rearm()  # as after a restart
    assert m["id"] in c._timers
    await c.take(m["id"], HOUSE)
    assert c.machine_message("entry1") is None
