"""What the house writes by itself - found in Home Assistant, nothing to set up.

- machines: Appliance Watch (Maskiner) says a dishwasher, washing machine or dryer is done -> "I'll take it". When it's
  emptied, the message is done by itself and goes from the phones.
- safety: a smoke, gas, CO or water sensor goes on -> urgent, rings like an alarm on the phones (also on silent).
- doorbell: a doorbell rings -> with a picture from a camera on the same device or in the same area.
- alarm: the alarm goes off (urgent) or is armed / disarmed.

Who gets each kind is chosen under Settings (admins), and each person can turn a kind off for themselves - except safety.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .const import HOUSE

_LOGGER = logging.getLogger(__name__)

SAFETY_CLASSES = {"smoke": "🔥", "gas": "⚠️", "carbon_monoxide": "⚠️", "moisture": "💧"}
DEFAULT_RULES = {
    "machines": {"on": True, "to": "home"},
    "safety": {"on": True, "to": "all"},
    "doorbell": {"on": True, "to": "home"},
    "alarm": {"on": False, "to": "all"},
}
ALWAYS = {"safety"}  # nobody can turn these off for themselves

WORDS = {
    "da": {"done": "{icon} {name} er færdig", "emptied": "Tømt", "smoke": "Røgalarm", "gas": "Gasalarm", "carbon_monoxide": "CO-alarm",
           "moisture": "Vand", "in": "i {area}", "door": "🔔 Det ringer på døren", "alarm_triggered": "🚨 Alarmen går!",
           "armed": "🔒 Alarmen er slået til", "disarmed": "🔓 Alarmen er slået fra", "stopped": "✓ {name} er stoppet"},
    "en": {"done": "{icon} {name} is done", "emptied": "Emptied", "smoke": "Smoke alarm", "gas": "Gas alarm", "carbon_monoxide": "CO alarm",
           "moisture": "Water", "in": "in {area}", "door": "🔔 Someone is at the door", "alarm_triggered": "🚨 The alarm is going off!",
           "armed": "🔒 The alarm is armed", "disarmed": "🔓 The alarm is disarmed", "stopped": "✓ {name} has stopped"},
}
MACHINE_ICON = {"dishwasher": "🍽️", "washing_machine": "🧺", "washer": "🧺", "dryer": "🌀"}


class Watch:
    def __init__(self, hass: HomeAssistant, chat: Any) -> None:
        self.hass, self.chat = hass, chat
        self._unsubs: list[Any] = []
        self._machine_msg: dict[str, str] = {}  # Appliance Watch entry -> message
        self._last: dict[str, float] = {}

    @property
    def w(self) -> dict[str, str]:
        return WORDS.get((self.hass.config.language or "en").split("-")[0], WORDS["en"])

    def rule(self, topic: str) -> dict[str, Any]:
        return {**DEFAULT_RULES[topic], **(self.chat.rules.get(topic) or {})}

    def start(self) -> None:
        self._unsubs.append(self.hass.bus.async_listen("appliance_watch_finished", self._machine_done))
        self._unsubs.append(self.hass.bus.async_listen("appliance_watch_emptied", self._machine_emptied))
        self._unsubs.append(self.hass.bus.async_listen("state_changed", self._state))

    def stop(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()

    def _often(self, key: str, seconds: float) -> bool:
        now = time.time()
        if now - self._last.get(key, 0) < seconds:
            return True
        self._last[key] = now
        return False

    async def _post(self, topic: str, title: str, text: str = "", **kw: Any) -> dict[str, Any] | None:
        r = self.rule(topic)
        if not r["on"]:
            return None
        return await self.chat.post(HOUSE, text, kind="house", title=title, to=r["to"], topic=topic, **kw)

    # ---------- machines ----------
    async def _machine_done(self, event: Event) -> None:
        d = event.data
        icon = MACHINE_ICON.get(str(d.get("kind") or ""), "✅")
        m = await self._post("machines", self.w["done"].format(icon=icon, name=d.get("name") or "?"), "", take=True)
        if m and d.get("entry_id"):
            self._machine_msg[d["entry_id"]] = m["id"]

    async def _machine_emptied(self, event: Event) -> None:
        msg_id = self._machine_msg.pop(str(event.data.get("entry_id") or ""), None)
        if msg_id:
            await self.chat.take(msg_id, HOUSE, name=self.w["emptied"])

    # ---------- safety, doorbell, alarm ----------
    @callback
    def _state(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None or old is None or new.state == old.state:
            return
        domain = new.entity_id.split(".")[0]
        dc = new.attributes.get("device_class")
        if domain == "binary_sensor" and dc in SAFETY_CLASSES and new.state == STATE_ON and old.state != "unavailable":
            if not self._often(new.entity_id, 600):
                self.hass.async_create_task(self._safety(new.entity_id, dc, new.name))
        elif domain == "event" and dc == "doorbell" and old.state != "unavailable":
            if not self._often(new.entity_id, 30):
                self.hass.async_create_task(self._doorbell(new.entity_id))
        elif domain == "binary_sensor" and dc == "doorbell" and new.state == STATE_ON:
            if not self._often(new.entity_id, 30):
                self.hass.async_create_task(self._doorbell(new.entity_id))
        elif domain == "alarm_control_panel" and old.state != "unavailable":
            self.hass.async_create_task(self._alarm(new.state))

    def _area(self, entity_id: str) -> str | None:
        e = er.async_get(self.hass).async_get(entity_id)
        area_id = e.area_id if e else None
        if e and not area_id and e.device_id:
            dev = dr.async_get(self.hass).async_get(e.device_id)
            area_id = dev.area_id if dev else None
        a = ar.async_get(self.hass).async_get_area(area_id) if area_id else None
        return a.name if a else None

    async def _safety(self, entity_id: str, dc: str, name: str) -> None:
        area = self._area(entity_id)
        title = f"{SAFETY_CLASSES[dc]} {self.w[dc]}" + (f" {self.w['in'].format(area=area)}" if area else "")
        await self._post("safety", title, name, urgent=True, take=True)

    def _camera_for(self, entity_id: str) -> str | None:
        ents = er.async_get(self.hass)
        e = ents.async_get(entity_id)
        if e and e.device_id:
            cam = next((x.entity_id for x in er.async_entries_for_device(ents, e.device_id) if x.domain == "camera"), None)
            if cam:
                return cam
        area = self._area(entity_id)
        if area:
            for st in self.hass.states.async_all("camera"):
                if self._area(st.entity_id) == area:
                    return st.entity_id
        return None

    async def _doorbell(self, entity_id: str) -> None:
        image = None
        if cam := self._camera_for(entity_id):
            try:
                from homeassistant.components import camera

                img = await camera.async_get_image(self.hass, cam)
                image = await self.hass.async_add_executor_job(self.chat.save_media, img.content, "jpg")
            except Exception:  # noqa: BLE001 - the message goes without the picture
                image = None
        await self._post("doorbell", self.w["door"], "", image=image)

    async def _alarm(self, state: str) -> None:
        if state == "triggered":
            await self._post("alarm", self.w["alarm_triggered"], "", urgent=True, take=True)
        elif state.startswith("armed_") and state != "armed_custom_bypass":
            await self._post("alarm", self.w["armed"])
        elif state == "disarmed":
            await self._post("alarm", self.w["disarmed"])
