"""0.14: tasks that go when they're done, "Lige nu" on top, quiet machines at night, smarter shopping, the fixes."""

from datetime import timedelta
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.hus_chat import now, smart
from custom_components.hus_chat.const import HOUSE

from .test_chat import chat  # noqa: F401


async def test_emptied_after_taken_is_done_and_leaves_lige_nu(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e1", "name": "Opvasker", "kind": "dishwasher"})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    assert [x["msg"] for x in c.now] == [m["id"]] and "venter" in c.now[0]["text"] or "waiting" in c.now[0]["text"]
    await c.take(m["id"], "person.lilly")
    assert "Lilly" in c.now[0]["text"] and not m.get("done")
    hass.bus.async_fire("appliance_watch_emptied", {"entry_id": "e1", "name": "Opvasker"})
    await hass.async_block_till_done()
    assert m["done"] and m["taken"]["name"] == "Lilly"  # who took it is kept
    assert c.now == []
    hass.bus.async_fire("appliance_watch_emptied", {"entry_id": "e1", "name": "Opvasker"})  # twice: nothing more
    await hass.async_block_till_done()
    assert m["done"]["name"]


async def test_a_machine_done_at_night_rings_no_phone_and_is_in_good_morning(hass: HomeAssistant, chat, monkeypatch) -> None:  # noqa: F811
    c, calls = chat
    monkeypatch.setattr("custom_components.hus_chat.watch.NIGHT_FROM", 0)  # it's night all day here
    monkeypatch.setattr("custom_components.hus_chat.watch.NIGHT_TO", 24)
    hass.bus.async_fire("appliance_watch_finished", {"entry_id": "e1", "name": "Vaskemaskine", "kind": "washing_machine"})
    await hass.async_block_till_done()
    assert not calls["Lilly"] and c.msgs[-1]["take"] and c.msgs[-1]["night"]
    from custom_components.hus_chat import morning

    with patch.object(morning, "weather_line", return_value=None):
        got = await morning.build(hass, chat=c)
    assert got and "Vaskemaskine" in got[1]


async def test_the_doorbell_goes_from_the_phones_after_five_minutes(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    hass.states.async_set("event.doerklokke", "2026-11-14T10:00:00", {"device_class": "doorbell"})
    await hass.async_block_till_done()
    hass.states.async_set("event.doerklokke", "2026-11-14T10:05:00", {"device_class": "doorbell"})
    await hass.async_block_till_done()
    m = c.msgs[-1]
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=6))
    await hass.async_block_till_done()
    assert m["done"] and calls["Lilly"][-1].data["message"] == "clear_notification"


async def test_on_the_way_home_and_dinner_on_lige_nu(hass: HomeAssistant, chat, monkeypatch) -> None:  # noqa: F811
    c, _ = chat
    monkeypatch.setattr(now, "DINNER_UNTIL", 25)  # any time of day
    hass.states.async_set("person.wictor", "not_home", {"friendly_name": "Wictor", "user_id": "u-wictor", "latitude": 55.70, "longitude": 12.40})
    hass.config.latitude, hass.config.longitude = 55.6761, 12.5683
    await c.on_my_way("person.wictor")
    assert any(x["key"] == "o:person.wictor" and "Wictor" in x["text"] for x in c.now)
    hass.states.async_set("person.wictor", "home", {"friendly_name": "Wictor", "user_id": "u-wictor"})
    await hass.async_block_till_done()
    assert not any(x["key"].startswith("o:") for x in c.now)
    m = await c.post(HOUSE, "", kind="house", title="Hjemme til aftensmad?", poll=["Ja", "Nej"], topic="dinner")
    c.dinner = {"date": dt_util.now().date().isoformat(), "msg": m["id"], "dish": "Kyllingewok"}
    c.vote(m["id"], "u-wictor", 0)
    c.vote(m["id"], "u-lilly", 0)
    card = next(x for x in now.cards(c) if x["key"] == "dinner")
    assert "Kyllingewok" in card["text"] and "2" in card["text"]


async def test_lige_nu_only_shows_what_you_may_see(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    private = await c.post(HOUSE, "", kind="house", title="Kun Wictor", take=True, to=["person.wictor"], machine="x1")
    cards = now.cards(c)
    assert any(x["msg"] == private["id"] for x in cards)
    assert any(x["msg"] == private["id"] for x in now.cards_for(c, cards, "u-wictor"))
    assert not any(x["msg"] == private["id"] for x in now.cards_for(c, cards, "u-lilly"))


async def test_an_app_link_keeps_its_own_quiet_hours(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    lid = c.link_by_token(c.add_link("Wictor", "person.wictor")["token"])
    c.links[lid]["subs"] = [{"endpoint": "https://push.example/x", "keys": {}}]
    c.set_prefs(f"link:{lid}", {"push": False})  # turned off in the app
    sent = []

    async def fake(lid_, msg, extra=""):
        sent.append(lid_)
    c._webpush = fake
    await c.post("person.lilly", "Hej")
    await hass.async_block_till_done()
    assert not sent and len(calls["Wictor"]) == 1  # the phone still under Wictor's own settings


async def test_an_edited_reminder_rings_at_the_new_time(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    m = await c.post("person.wictor", "mind mig om madpakken om 30 min")
    await hass.async_block_till_done()
    first = m["remind"]
    assert c.edit(m["id"], "u-wictor", "mind mig om madpakken om 10 min")
    assert len(c.reminders) == 1 and m["remind"] < first
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=11))
    await hass.async_block_till_done()
    assert c.msgs[-1]["from"] == HOUSE and "Madpakken" in c.msgs[-1]["text"] and not c.reminders


def test_we_need_is_shopping_but_not_people() -> None:
    assert smart.shop_items("vi mangler mælk og brød") == ["Mælk", "Brød"]
    assert smart.shop_items("Vi er løbet tør for kaffe") == ["Kaffe"]
    assert smart.shop_items("tom for bleer!") == ["Bleer"]
    assert smart.shop_items("we're out of milk") == ["Milk"]
    assert smart.shop_items("vi mangler dig til fodbold") == []
    assert smart.shop_items("vi mangler nogen der kan hente Silas") == []
    assert smart.shop_items("mangler vi mælk?") == []


async def test_madplan_gets_it_when_it_is_there(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    mad = async_mock_service(hass, "madplan", "egen_vare")
    added = async_mock_service(hass, "todo", "add_item")
    hass.states.async_set("todo.shopping_list", "0", {"friendly_name": "Indkøbsliste"})
    m = await c.post("person.lilly", "vi mangler mælk")
    await hass.async_block_till_done()
    assert [x.data["tekst"] for x in mad] == ["Mælk"] and not added and m["shop"] == ["Mælk"]


async def test_madplan_with_several_shops_uses_the_one_with_a_plan(hass: HomeAssistant, chat) -> None:  # noqa: F811
    from datetime import timedelta

    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import dt as dt_util

    c, _ = chat
    reg = er.async_get(hass)
    old = (dt_util.now().date() - timedelta(days=9)).isoformat()
    soon = (dt_util.now().date() + timedelta(days=1)).isoformat()
    for shop, dato in (("netto", old), ("rema", soon)):
        main = reg.async_get_or_create("sensor", "madplan", f"{shop}_main")
        day = reg.async_get_or_create("sensor", "madplan", f"{shop}_dag")
        hass.states.async_set(main.entity_id, "1", {"varer_entitet": f"todo.{shop}"})
        hass.states.async_set(day.entity_id, "Suppe", {"dato": dato})
    with patch.object(er.RegistryEntry, "config_entry_id", property(lambda self: self.unique_id.split("_")[0])):
        store = c.madplan_store()
    assert store == reg.async_get_entity_id("sensor", "madplan", "rema_main")
    mad = async_mock_service(hass, "madplan", "egen_vare")
    with patch.object(type(c), "madplan_store", return_value="sensor.rema"):
        assert await c.add_to_shopping(["Toiletpapir"])
    assert mad[0].data == {"tekst": "Toiletpapir", "entity_id": "sensor.rema"}


async def test_no_doubles_on_the_home_assistant_list(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.states.async_set("todo.shopping_list", "1", {"friendly_name": "Indkøbsliste"})
    added = async_mock_service(hass, "todo", "add_item")
    with patch.object(type(c), "shop_list", return_value={"items": [{"summary": "mælk"}]}):
        await c.post("person.lilly", "køb mælk og æg")
        await hass.async_block_till_done()
    assert [x.data["item"] for x in added] == ["Æg"]


async def test_remind_me_when_i_come_home(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.states.async_set("person.wictor", "not_home", {"friendly_name": "Wictor", "user_id": "u-wictor"})
    await hass.async_block_till_done()
    m = await c.post("person.wictor", "mind mig om at tage pakken ind når jeg kommer hjem")
    await hass.async_block_till_done()
    assert m.get("remind_home") and len(c.reminders) == 1
    hass.states.async_set("person.lilly", "not_home", {"friendly_name": "Lilly", "user_id": "u-lilly"})
    await hass.async_block_till_done()
    hass.states.async_set("person.lilly", "home", {"friendly_name": "Lilly", "user_id": "u-lilly"})
    await hass.async_block_till_done()
    assert len(c.reminders) == 1  # Lilly coming home is not Wictor
    hass.states.async_set("person.wictor", "home", {"friendly_name": "Wictor", "user_id": "u-wictor"})
    await hass.async_block_till_done()
    assert not c.reminders and c.msgs[-1]["from"] == HOUSE and "Tage pakken ind" in c.msgs[-1]["text"] and c.msgs[-1]["to"] == ["person.wictor"]


async def test_every_week_comes_back(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    m = await c.post("person.wictor", "mind os om skrald hver tirsdag kl 18")
    await hass.async_block_till_done()
    first = m["remind"]
    assert m["remind_every"] == 7 and c.reminders[0]["every"] == 7
    async_fire_time_changed(hass, dt_util.utc_from_timestamp(first + 60))
    await hass.async_block_till_done()
    assert c.msgs[-1]["from"] == HOUSE and "Skrald" in c.msgs[-1]["text"]
    assert len(c.reminders) == 1 and 6.9 * 86400 < c.reminders[0]["when"] - first < 7.1 * 86400


async def test_who_is_home_is_left_to_assist(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    assert await c.local_answer("u-claus", "Hvem er hjemme?") is None  # presence isn't reliable: not answered by the house
    assert await c.local_answer("u-claus", "Tænd lyset i stuen") is None  # Assist's job


def test_many_ways_to_ask() -> None:
    names = ["Lilly", "Holly", "Silas"]
    for q in ("hvornår har Lilly fri på onsdag?", "Lilly fri onsdag?", "hvornår slutter Lilly i morgen", "skal lilly hentes i dag?",
              "har Lilly skole fredag", "hvornår har lily fri", "Hvornår er Lillys skole færdig?"):
        assert smart.question(q, names) == ("school", "Lilly"), q
    assert smart.question("hvornår har børnene fri på fredag", names) == ("school", "all")
    for q in ("hvad skal vi spise?", "hvad er der til aftensmad", "hvad får vi at spise i aften", "mad i aften?"):
        assert smart.question(q, names) == ("dinner", None), q
    for q in ("hvornår er der skrald", "hvilken spand skal ud?", "hvornår kommer skraldemanden"):
        assert smart.question(q, names) == ("waste", None), q
    assert smart.question("hvornår er strømmen billigst", names) == ("cheap", None)
    assert smart.question("er døren låst?", names) is None


def test_the_day_asked_about() -> None:
    from datetime import datetime

    sat = datetime(2026, 11, 28, 15, 0)  # a Saturday
    assert smart.which_day("hvornår har Lilly fri på onsdag", sat).date().isoformat() == "2026-12-02"
    assert smart.which_day("i morgen", sat).date().isoformat() == "2026-11-29"
    assert smart.which_day("hvornår har Lilly fri", sat) is None


def test_a_name_wins_over_they_and_two_alike_are_not_guessed() -> None:
    from datetime import datetime

    assert smart.question("hvornår har Lilly fri de dage hun har idræt", ["Lilly", "Holly"]) == ("school", "Lilly")
    assert smart.question("hvornår har Lill fri", ["Lilli", "Lilly"]) is None
    wed = datetime(2026, 12, 2, 9, 0)
    assert smart.which_day("hvornår har Lilly fri næste onsdag", wed).date().isoformat() == "2026-12-09"
    assert smart.which_day("hvornår har Lilly fri onsdag", wed).date().isoformat() == "2026-12-02"
