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
    said = await _ask(hass, "hvornår har Lilly fri på onsdag", device="speaker_kitchen")  # a speaker in the house
    assert "Lilly har fri" in said and "13:50" in said and "🎒" not in said  # spoken: no emoji
    assert "13:50" in await _ask(hass, "har Lilly skole onsdag", device="speaker_kitchen")
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
