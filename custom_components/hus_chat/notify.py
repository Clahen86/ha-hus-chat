"""notify.hus_chat: send from any automation - it goes to those at home (everyone if nobody is)."""

from __future__ import annotations

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, HOUSE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add: AddConfigEntryEntitiesCallback) -> None:
    add([HusChatNotify(entry)])


class HusChatNotify(NotifyEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "chat"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": entry.title, "manufacturer": "Clahen86"}

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        await self._entry.runtime_data.post(HOUSE, message, kind="house", title=title, to="home")
