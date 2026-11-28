"""House Chat for your AI: tools an assistant (Google, ChatGPT, Claude, a local one) can look the family's day up with.

"When is Lilly out of school on Thursday?", "what's for dinner this week?", "when are the bins collected?" - asked in
your own words; the AI asks House Chat (the timetables, Madplan, the waste calendar). Turned on once in the AI's settings
("House Chat" under the tools it may use). Without an AI nothing changes. Only reads. A child's school day goes only to
that child, a grown-up, or a speaker in the house - the same rules as in the chat.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

try:  # newer Home Assistant
    import probatio as vol
except ImportError:  # pragma: no cover - older Home Assistant
    import voluptuous as vol

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
API_ID = "hus_chat"
PROMPT = ("House Chat knows the family's day: school timetables per child, dinner from the meal plan, the waste collection "
          "and the family's calendars. Use its tool for when a child is out of school, what's for dinner (any day), when "
          "the bins are collected and what's on today. Answer short, in the user's language.")
ASK = {  # the question House Chat answers itself (chat.local_answer) - in the language its words know
    "school": "hvornår har {who} fri {day}", "dinner": "hvad skal vi spise {day}", "bins": "hvornår kommer skraldet",
    "cheap_power": "hvornår er strømmen billigst", "my_day": "hvad skal jeg i dag",
}
DAYS = {"today": "i dag", "tomorrow": "i morgen", "monday": "mandag", "tuesday": "tirsdag", "wednesday": "onsdag", "thursday": "torsdag",
        "friday": "fredag", "saturday": "lørdag", "sunday": "søndag"}


def is_speaker(hass: HomeAssistant, device_id: str | None) -> bool:
    """A voice speaker in the house (a device with an Assist satellite) - not any device that calls without a user."""
    if not device_id:
        return False
    from homeassistant.helpers import entity_registry as er

    return any(e.domain == "assist_satellite" for e in er.async_entries_for_device(er.async_get(hass), device_id))


class Family(llm.Tool):
    name = "hus_chat_family_day"
    integration = DOMAIN
    description = ("The family's day from House Chat. topic: school (when a child is out of school - give the child's first "
                   "name, or 'all'), dinner (from the meal plan), bins (next waste collection), my_day (the asker's own day). "
                   "day: today, tomorrow or a weekday (optional).")
    parameters = vol.Schema({
        vol.Required("topic", description="school, dinner, bins or my_day"): vol.In(["school", "dinner", "bins", "my_day"]),
        vol.Optional("child", description="The child's first name, or 'all' (for school)"): str,
        vol.Optional("day", description="today, tomorrow, monday … sunday"): str,
    })

    async def async_call(self, hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext) -> dict[str, Any]:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if not entries:
            return {"error": "House Chat isn't set up"}
        chat = entries[0].runtime_data
        a = tool_input.tool_args or {}
        day = DAYS.get(str(a.get("day") or "").lower().strip(), str(a.get("day") or ""))
        who = str(a.get("child") or "").strip()
        who = "børnene" if who.lower() in ("all", "alle", "kids", "børnene") else who
        if a.get("topic") == "school" and not who:
            return {"error": "Which child? Give the first name, or 'all'."}
        text = ASK[a.get("topic", "dinner")].format(who=who, day=day).strip()
        uid = getattr(llm_context.context, "user_id", None) if llm_context.context else None
        speaker = uid is None and is_speaker(hass, getattr(llm_context, "device_id", None))
        try:
            got = await chat.local_answer(uid, text, speaker=speaker)
        except Exception as err:  # noqa: BLE001 - a tool never breaks the conversation
            _LOGGER.debug("House Chat tool failed", exc_info=True)
            return {"error": str(err)[:200]}
        return {"answer": got} if got else {"answer": None, "note": "Nothing found for that"}


class ChatAPI(llm.API):
    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(hass=hass, id=API_ID, name="House Chat")

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        return llm.APIInstance(api=self, api_prompt=PROMPT, llm_context=llm_context, tools=[Family()])


def register(hass: HomeAssistant) -> Any:
    try:
        return llm.async_register_api(hass, ChatAPI(hass))
    except Exception:  # noqa: BLE001
        _LOGGER.debug("House Chat tools not registered", exc_info=True)
        return None
