"""The house's own questions by voice: Assist on the phone or a speaker answers them from House Chat first.

House Chat gives Home Assistant's own Assist a few sentences ("hvornår har Lilly fri på onsdag", "hvad skal vi spise",
"hvornår kommer skraldet"). A pipeline with "prefer handling commands locally" (on by default) then answers them right
away from House Chat - the school timetables, the meal plan, the bins - and everything else goes on to the AI as before.
Nothing to set up. Only these sentences: a question that isn't one of them never reaches House Chat.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)

# hassil sentences: (a|b) one of, [x] may be left out. No open "{x}" anywhere: a question only reaches House Chat when
# it is exactly one of these - with one of the family's own names and, at most, a day after it. The answer is worked
# out from the whole sentence by smart.question.
DAY = "[[på|næste|on|next] (i dag|idag|i morgen|imorgen|i overmorgen|mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag|today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)]"
KIDS = "børnene|ungerne|pigerne|drengene"


def sentences(names: list[str]) -> list[str]:
    """The sentences for this family - the school ones only with its own first names."""
    who = "|".join(sorted({n for n in names if re.fullmatch(r"[\wæøåÆØÅ-]{2,}", n)} | set(KIDS.split("|"))))
    out = [
        f"hvornår har ({who}) fri {DAY}",
        f"hvornår (slutter|stopper) ({who}) [i skole[n]] {DAY}",
        f"hvornår (er|bliver) ({who}) færdig[e] [i skole[n]|med skole[n]] {DAY}",
        f"har ({who}) skole {DAY}",
        f"[hvornår] skal ({who}) hentes {DAY}",
        f"when (is|are) ({who}) out of school {DAY}",
        f"(does|do) ({who}) have school {DAY}",
    ]
    return out + [
        f"hvad skal vi [have] [at] spise {DAY} [i aften]",
        f"hvad (er der|får vi) til (aftensmad|middag) {DAY} [i aften]",
        f"hvad får vi at spise {DAY} [i aften]",
        f"hvad skal vi have til (aftensmad|middag) {DAY} [i aften]",
        "hvornår (er der|kommer) (skrald|skraldet|skraldemanden|affald|affaldet)",
        "hvornår (skal|bliver) (skraldet|affaldet|spanden|skraldespanden) [tømt|hentet|ud]",
        "hvilken spand skal ud",
        "hvornår er (strømmen|el|strøm) billig[st|est] [i dag|i morgen]",
        f"what's for dinner {DAY} [tonight]",
        f"what is for dinner {DAY} [tonight]",
        "when (are|is) the (bins|bin|garbage|rubbish) collected",
        "when is power cheapest [today|tomorrow]",
    ]


UNKNOWN = {"da": "Det kan jeg ikke se lige nu.", "en": "I can't see that right now."}


def spoken(text: str) -> str:
    """Said aloud: without the emoji, one line after the other."""
    lines = [re.sub(r"^[^\w]+", "", line).strip() for line in (text or "").splitlines()]
    return ". ".join(x for x in lines if x)


def setup(hass: HomeAssistant, chat: Any) -> CALLBACK_TYPE | None:
    """Give Assist the sentences. None when this Home Assistant has no way for it (then nothing happens). The family's
    names are read again once a day (a new person)."""
    try:
        from homeassistant.components.conversation.agent_manager import get_agent_manager
    except ImportError:
        return None

    async def answer(user_input: Any, _result: Any) -> str:
        uid = getattr(getattr(user_input, "context", None), "user_id", None)
        # A speaker in the house (a voice satellite) is like the timetable on the fridge; text without anyone signed in
        # isn't.
        speaker = uid is None and bool(getattr(user_input, "satellite_id", None) or getattr(user_input, "device_id", None))
        try:
            got = await chat.local_answer(uid, user_input.text, speaker=speaker)
        except Exception:  # noqa: BLE001 - never stops Assist
            _LOGGER.debug("Could not answer %s", user_input.text, exc_info=True)
            got = None
        lang = (hass.config.language or "en").split("-")[0]
        # Never handed on from here: the sentence was meant for the house, and handing it on could come back here.
        return spoken(got) if got else UNKNOWN.get(lang, UNKNOWN["en"])

    from datetime import timedelta

    from homeassistant.helpers.event import async_track_time_interval

    state: dict[str, Any] = {"names": None, "unreg": None}

    @callback
    def register(_now: Any = None) -> None:
        names = sorted(p["name"].split(" ")[0] for p in chat.people() if p.get("name"))
        if names == state["names"]:
            return
        if state["unreg"]:
            state["unreg"]()
        try:
            state["unreg"], state["names"] = get_agent_manager(hass).register_trigger(sentences(names), answer), names
        except Exception:  # noqa: BLE001 - an Assist without sentence triggers: the chat still answers
            _LOGGER.debug("Assist sentences not registered", exc_info=True)
            state["unreg"] = None

    register()
    if state["unreg"] is None:
        return None
    stop_timer = async_track_time_interval(hass, register, timedelta(hours=24))

    def unregister() -> None:
        stop_timer()
        if state["unreg"]:
            state["unreg"]()

    return unregister
