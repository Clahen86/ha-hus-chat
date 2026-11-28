"""0.14.2: the house's own questions by voice - Assist answers them from House Chat before the AI."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.hus_chat import voice

from .test_calendars import _calendars
from .test_chat import chat  # noqa: F401


async def _ask(hass: HomeAssistant, text: str, user: str | None = None, device: str | None = None) -> str:
    res = await conversation.async_converse(hass, text, None, Context(user_id=user), language="da", agent_id="conversation.home_assistant",
                                            device_id=device)
    return res.response.speech["plain"]["speech"]


async def test_school_by_voice_on_the_day_asked(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.config.language = "da"
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    unreg = voice.setup(hass, c)
    now = dt_util.now()
    wed = (now + timedelta(days=(2 - now.weekday()) % 7 or 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    _calendars(hass, {"calendar.skema_lilly": [{"summary": "Dansk", "start": (wed + timedelta(hours=8)).isoformat(),
                                               "end": (wed + timedelta(hours=13, minutes=50)).isoformat()}]})
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    sat_entry = MockConfigEntry(domain="esphome")
    sat_entry.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(config_entry_id=sat_entry.entry_id, identifiers={("esphome", "kitchen")})
    er.async_get(hass).async_get_or_create("assist_satellite", "esphome", "kitchen", device_id=dev.id, config_entry=sat_entry)
    said = await _ask(hass, "hvornår har Lilly fri på onsdag", device=dev.id)  # a speaker in the house
    assert "Lilly har fri" in said and "13:50" in said and "🎒" not in said  # spoken: no emoji
    assert "13:50" in await _ask(hass, "har Lilly skole onsdag", device=dev.id)
    assert "13:50" not in await _ask(hass, "har Lilly skole onsdag", device="some_other_device")  # not a speaker
    unreg()


async def test_other_sentences_go_on_as_before(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.config.language = "da"
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    unreg = voice.setup(hass, c)
    with patch.object(type(c), "local_answer") as la:
        await _ask(hass, "tænd lyset i stuen")
        await _ask(hass, "hvornår stopper vaskemaskinen")  # not a family name: Google's question, not House Chat's
        await _ask(hass, "hvad skal vi spise og sluk lyset")
    assert not la.called
    unreg()


async def test_text_without_a_user_is_no_speaker(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.config.language = "da"
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    unreg = voice.setup(hass, c)
    with patch.object(type(c), "local_answer", return_value=None) as la:
        await _ask(hass, "hvornår har Lilly fri")
    assert la.call_args.kwargs["speaker"] is False
    unreg()


def test_spoken_without_emoji() -> None:
    assert voice.spoken("🎒 Lilly har fri onsdag kl. 13:50\n🎒 Holly har fri onsdag kl. 14:00") == "Lilly har fri onsdag kl. 13:50. Holly har fri onsdag kl. 14:00"


async def test_the_ai_tool(hass: HomeAssistant, chat) -> None:  # noqa: F811
    from homeassistant.helpers import llm

    c, _ = chat
    now = dt_util.now()
    wed = (now + timedelta(days=(2 - now.weekday()) % 7 or 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    _calendars(hass, {"calendar.skema_lilly": [{"summary": "Dansk", "start": (wed + timedelta(hours=8)).isoformat(),
                                               "end": (wed + timedelta(hours=13, minutes=50)).isoformat()}]})
    ctx = llm.LLMContext(platform="test", context=Context(user_id="u-lilly"), language="da", assistant="conversation", device_id=None)
    api = await llm.async_get_api(hass, "hus_chat", ctx)
    r = await api.async_call_tool(llm.ToolInput(tool_name="hus_chat_family_day", tool_args={"topic": "school", "child": "Lilly", "day": "wednesday"}))
    assert "13:50" in getattr(r, "data", r)["answer"]
    ctx2 = llm.LLMContext(platform="test", context=Context(user_id="u-wictor"), language="da", assistant="conversation", device_id=None)
    api2 = await llm.async_get_api(hass, "hus_chat", ctx2)
    r2 = await api2.async_call_tool(llm.ToolInput(tool_name="hus_chat_family_day", tool_args={"topic": "school", "child": "Lilly", "day": "wednesday"}))
    assert "13:50" not in str(getattr(r2, "data", r2))  # another child: not theirs


async def test_when_school_starts_by_voice(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    hass.config.language = "da"
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    unreg = voice.setup(hass, c)
    now = dt_util.now()
    mon = (now + timedelta(days=(0 - now.weekday()) % 7 or 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    _calendars(hass, {"calendar.skema_lilly": [{"summary": "DAN", "start": (mon + timedelta(hours=8)).isoformat(), "end": (mon + timedelta(hours=13, minutes=5)).isoformat()}]})
    said = await _ask(hass, "hvornår møder Lilly på mandag", user="u-lilly")
    assert "møder" in said and "8:00" in said
    unreg()


async def test_shopping_by_voice_goes_to_madplan(hass: HomeAssistant, chat) -> None:  # noqa: F811
    from pytest_homeassistant_custom_component.common import async_mock_service

    c, _ = chat
    hass.config.language = "da"
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    mad = async_mock_service(hass, "madplan", "egen_vare")  # (the sentences are already there from House Chat's own setup)
    assert await _ask(hass, "Vi mangler toiletpapir") == "Toiletpapir er sat på indkøbslisten"
    assert "Mælk og brød" in await _ask(hass, "sæt mælk og brød på indkøbslisten")
    assert [x.data["tekst"] for x in mad] == ["Toiletpapir", "Mælk", "Brød"]
    assert await _ask(hass, "vi mangler dig") == "Hvad skal på listen?"
