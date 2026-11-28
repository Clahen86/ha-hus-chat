"""What the house writes by itself - found in Home Assistant, nothing to set up.

- machines: Appliance Watch (Maskiner) says a dishwasher, washing machine or dryer is done -> "I'll take it". When it's
  emptied, the message is done by itself and goes from the phones.
- safety: a smoke, gas, CO or water sensor goes on -> urgent, rings like an alarm on the phones (also on silent).
- doorbell: a doorbell rings -> with a picture from a camera on the same device or in the same area.
- alarm: the alarm goes off (urgent) or is armed / disarmed.
- dinner: at the chosen time a poll "Home for dinner today?" - hus_chat.send with to: dinner reaches those who said yes.
- morning: good morning at 7 - weather, dinner, chores and the cheapest power (morning.py). Off until switched on.

Together with Pligt-pilot and Madplan, when they are there (nothing to set up; without them nothing happens):
- a machine taken in the chat or emptied is told on the bus (hus_chat_machine); a child taking it in Pligt-pilot
  (pligt_pilot_task) marks the message taken here.
- "Dinner is ready" when a child marks a meal done in Pligt-pilot, and "<kid> is cooking today" at 7 in the morning
  of the day Madplan gives them (madplan_cook) - once per child and day, also over a restart.

Who gets each kind is chosen under Settings (admins), and each person can turn a kind off for themselves - except safety.
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta
import logging
import time
from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_point_in_time, async_track_time_change
from homeassistant.util import dt as dt_util

from .const import HOUSE, TEXT

_LOGGER = logging.getLogger(__name__)

SAFETY_CLASSES = {"smoke": "🔥", "gas": "⚠️", "carbon_monoxide": "⚠️", "moisture": "💧"}
DEFAULT_RULES = {
    "machines": {"on": True, "to": "home"},
    "safety": {"on": True, "to": "all"},
    "doorbell": {"on": True, "to": "home"},
    "alarm": {"on": False, "to": "all"},
    "morning": {"on": False, "to": "all"},
    "dinner": {"on": False, "to": "all", "at": "15:00"},
    "waste": {"on": True, "to": "home"},
}
WASTE_AT = 18  # the evening before the bins are emptied
WASTE_UNTIL = 12  # the message goes at noon on the day
ALWAYS = {"safety"}  # nobody can turn these off for themselves

WORDS = {
    "da": {"dinner_q": "🍽️ Hjemme til aftensmad i dag?", "dinner_yes": "🙋 Ja", "dinner_no": "Nej", "dinner_dish": "Der er {dish}", "done": "{icon} {name} er færdig", "emptied": "Tømt", "smoke": "Røgalarm", "gas": "Gasalarm", "carbon_monoxide": "CO-alarm",
           "moisture": "Vand", "in": "i {area}", "door": "🔔 Det ringer på døren", "alarm_triggered": "🚨 Alarmen går!",
           "armed": "🔒 Alarmen er slået til", "disarmed": "🔓 Alarmen er slået fra", "stopped": "✓ {name} er stoppet",
           "aw_stopped": "Har ikke kørt i timevis – tjek den, før maden tør op.", "aw_nonstop": "Kører uden pause – står døren åben?",
           "aw_lost": "Ingen måling – har den mistet strømmen?", "aw_tank": "Stoppet – tanken er nok fuld.", "aw_ok": "Virker igen",
           "waste": "🗑️ {list} hentes i morgen", "waste_s": "Stil spanden ud i aften"},
    "en": {"dinner_q": "🍽️ Home for dinner today?", "dinner_yes": "🙋 Yes", "dinner_no": "No", "dinner_dish": "It's {dish}", "done": "{icon} {name} is done", "emptied": "Emptied", "smoke": "Smoke alarm", "gas": "Gas alarm", "carbon_monoxide": "CO alarm",
           "moisture": "Water", "in": "in {area}", "door": "🔔 Someone is at the door", "alarm_triggered": "🚨 The alarm is going off!",
           "armed": "🔒 The alarm is armed", "disarmed": "🔓 The alarm is disarmed", "stopped": "✓ {name} has stopped",
           "aw_stopped": "Hasn't run for hours – check it before the food thaws.", "aw_nonstop": "Runs without a break – is the door open?",
           "aw_lost": "No reading – has it lost power?", "aw_tank": "Stopped – the tank is probably full.", "aw_ok": "Works again",
           "waste": "🗑️ {list} collected tomorrow", "waste_s": "Put the bin out tonight"},
}
MACHINE_ICON = {"dishwasher": "🍽️", "washing_machine": "🧺", "washer": "🧺", "dryer": "🌀"}
MACHINE_WORDS = (("dishwasher", ("opvask", "dish")), ("dryer", ("tørre", "tumbl", "dryer", "trockner", "tork")),
                 ("washer", ("vask", "wash", "wasch", "tvätt")))
COOK_AT = dtime(7)  # "<kid> is cooking today" is said at 7 in the morning
NIGHT_FROM, NIGHT_TO = 22, 7  # a machine done at night rings no phone - it's in the chat and in good morning
DOOR_CLEAR_S = 5 * 60


def machine_type(name: str | None) -> str:
    """washer, dryer, dishwasher or other - from the machine's name, the same way in every app (Pligt-pilot)."""
    n = str(name or "").lower()
    return next((kind for kind, words in MACHINE_WORDS if any(w in n for w in words)), "other")


class Watch:
    def __init__(self, hass: HomeAssistant, chat: Any) -> None:
        self.hass, self.chat = hass, chat
        self._unsubs: list[Any] = []
        self._last: dict[str, float] = {}
        self._cook_timers: dict[str, Any] = {}

    @property
    def w(self) -> dict[str, str]:
        return WORDS.get((self.hass.config.language or "en").split("-")[0], WORDS["en"])

    @property
    def t(self) -> dict[str, str]:
        return TEXT.get((self.hass.config.language or "en").split("-")[0], TEXT["en"])

    def rule(self, topic: str) -> dict[str, Any]:
        return {**DEFAULT_RULES[topic], **(self.chat.rules.get(topic) or {})}

    def start(self) -> None:
        self._unsubs.append(self.hass.bus.async_listen("appliance_watch_finished", self._machine_done))
        self._unsubs.append(self.hass.bus.async_listen("appliance_watch_emptied", self._machine_emptied))
        self._unsubs.append(self.hass.bus.async_listen("appliance_watch_alert", self._machine_alert))
        self._unsubs.append(self.hass.bus.async_listen("state_changed", self._state))
        self._unsubs.append(self.hass.bus.async_listen("pligt_pilot_task", self._task))
        self._unsubs.append(self.hass.bus.async_listen("madplan_cook", self._cook))
        from .morning import AT_HOUR

        self._unsubs.append(async_track_time_change(self.hass, self._morning, hour=AT_HOUR, minute=0, second=0))
        self._unsubs.append(async_track_time_change(self.hass, self._dinner_poll, second=0))  # at the chosen minute
        self._unsubs.append(async_track_time_change(self.hass, self._waste, hour=WASTE_AT, minute=0, second=0))
        self._unsubs.append(async_track_time_change(self.hass, self._waste_over, minute=5, second=0))
        for key in list(self.chat.cooks):  # after a restart
            self._plan_cook(key)
        for m in self.chat.msgs[-100:]:  # a doorbell rung just before a restart still goes from the phones
            if m.get("topic") == "doorbell" and not m.get("done"):
                left = DOOR_CLEAR_S - (time.time() - m["t"])
                self._cook_timers[f"door:{m['id']}"] = async_call_later(self.hass, max(1.0, left), callback(lambda _n, i=m["id"]: self._door_done(i)))

    def stop(self) -> None:
        for u in [*self._unsubs, *self._cook_timers.values()]:
            u()
        self._unsubs.clear()
        self._cook_timers.clear()

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

    # ---------- good morning ----------
    async def _morning(self, _now: Any = None) -> None:
        """The day ahead at 7 (morning.py) - only when switched on, and only when there's something to say."""
        r = self.rule("morning")
        today = dt_util.now().date().isoformat()
        if not r["on"]:
            return
        done = set(self.chat.sent_days.get("morning_to") or []) if self.chat.sent_days.get("morning") == today else set()
        from . import morning

        people = [p for p in self.chat.people() if (p["user_id"] or p.get("web")) and p["id"] not in done]  # also read in the panel
        if isinstance(r["to"], list):
            people = [p for p in people if p["id"] in r["to"]]
        try:
            each = await morning.for_everyone(self.hass, self.chat, people)
        except Exception:  # noqa: BLE001 - never in the way of the rest
            _LOGGER.warning("Good morning could not be put together", exc_info=True)
            return
        for p, title, text in each:  # one each, with only what is theirs - nobody sees another's
            done.add(p["id"])  # once a day each, also over a restart in the middle
            self.chat.sent_days.update({"morning": today, "morning_to": sorted(done)})
            await self.chat.post(HOUSE, text, kind="house", title=title, to=[p["id"]], topic="morning")

    # ---------- waste: the bins out the evening before ----------
    async def _waste(self, _now: Any = None) -> None:
        """At 18: what is emptied tomorrow (the waste calendar) - one "I'll take it" to those at home, gone when it's
        taken or at noon the day after."""
        from . import calendars

        r = self.rule("waste")
        tomorrow = (dt_util.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if not r["on"] or self.chat.sent_days.get("waste") == tomorrow.date().isoformat():
            return
        kinds: list[str] = []
        for c in (c for c in calendars.find(self.hass, self.chat.people()) if c["kind"] == "waste"):
            kinds += [e["summary"] for e in await calendars.events(self.hass, c["entity_id"], tomorrow, tomorrow + timedelta(days=1)) if e["summary"]]
        if not kinds:
            return
        self.chat.sent_days["waste"] = tomorrow.date().isoformat()
        m = await self._post("waste", self.w["waste"].format(list=", ".join(dict.fromkeys(kinds))), self.w["waste_s"], take=True)
        if m:
            m["until"] = tomorrow.replace(hour=WASTE_UNTIL).timestamp()
        self.chat._save()

    async def _waste_over(self, _now: Any = None) -> None:
        for m in self.chat.msgs[-200:]:
            if m.get("topic") == "waste" and not m.get("done") and time.time() >= m.get("until", m["t"] + 30 * 3600):
                await self.chat.finish(m["id"])

    # ---------- dinner: who is home to eat ----------
    async def _dinner_poll(self, now: Any = None) -> None:
        """At the chosen time: "Home for dinner today?" - those who say yes get "dinner is ready" (hus_chat.send to: dinner)."""
        r = self.rule("dinner")
        now = dt_util.as_local(now) if isinstance(now, datetime) else dt_util.now()
        today = now.date().isoformat()
        if not r["on"] or now.strftime("%H:%M") != r.get("at") or (self.chat.dinner or {}).get("date") == today:
            return
        from . import morning

        dish = morning.dinner_line(self.hass, {**morning.words(self.hass), "dinner": "{dish}"}, today)
        self.chat.dinner = {"date": today, "msg": None}  # once a day, also when posting fails
        m = await self._post("dinner", self.w["dinner_q"], self.w["dinner_dish"].format(dish=dish) if dish else "",
                             poll=[self.w["dinner_yes"], self.w["dinner_no"]])
        self.chat.dinner = {"date": today, "msg": m["id"] if m else None, "dish": dish or ""}
        self.chat._save()

    # ---------- machines ----------
    async def _machine_done(self, event: Event) -> None:
        """Done: "I'll take it" to those at home. At night (22-7) no phone rings - it waits in the chat and in good
        morning."""
        d = event.data
        icon = MACHINE_ICON.get(str(d.get("kind") or ""), "✅")
        hour = dt_util.now().hour
        night = hour >= NIGHT_FROM or hour < NIGHT_TO
        m = await self._post("machines", self.w["done"].format(icon=icon, name=d.get("name") or "?"), "", take=True,
                             machine=str(d.get("entry_id") or "") or None, mtype=machine_type(d.get("name")), push=not night)
        if m and night:
            m["night"] = True  # for good morning (morning.night_line)
            self.chat._save()

    async def _machine_emptied(self, event: Event) -> None:
        # The machine is kept on its message, so this works after a restart too.
        if m := self.chat.machine_open(str(event.data.get("entry_id") or "")):
            await self.chat.finish(m["id"], self.w["emptied"])  # also when somebody had taken it
        self.hass.bus.async_fire("hus_chat_machine", {"kind": "emptied", "machine": machine_type(event.data.get("name")), "name": ""})

    async def _machine_alert(self, event: Event) -> None:
        """A freezer or a dehumidifier in trouble (Appliance Watch); a freezer that stopped is urgent - the food thaws."""
        d, w = event.data, self.w
        key = f"aw:{d.get('entry_id')}"
        if d.get("ok"):
            if m := self.chat.machine_open(key):
                await self.chat.finish(m["id"], w["aw_ok"])
            return
        reason = str(d.get("reason") or "")
        urgent = d.get("kind") == "freezer" and reason in ("stopped", "nonstop", "lost")
        await self._post("machines", f"⚠️ {d.get('name') or '?'}", w.get(f"aw_{reason}", ""), take=True, urgent=urgent,
                         machine=key)

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
        if not self.rule("doorbell")["on"]:
            return  # no picture taken for a message that won't be sent
        image = None
        if cam := self._camera_for(entity_id):
            try:
                from homeassistant.components import camera

                img = await camera.async_get_image(self.hass, cam)
                image = await self.hass.async_add_executor_job(self.chat.save_media, img.content, "jpg")
            except Exception:  # noqa: BLE001 - the message goes without the picture
                image = None
        m = await self._post("doorbell", self.w["door"], "", image=image)
        if m:  # answered or not: gone from the phones after a few minutes (the message stays in the chat)
            self._cook_timers[f"door:{m['id']}"] = async_call_later(self.hass, DOOR_CLEAR_S, callback(lambda _n, i=m["id"]: self._door_done(i)))

    @callback
    def _door_done(self, msg_id: str) -> None:
        self._cook_timers.pop(f"door:{msg_id}", None)
        self.hass.async_create_task(self.chat.finish(msg_id))

    async def _alarm(self, state: str) -> None:
        if state == "triggered":
            await self._post("alarm", self.w["alarm_triggered"], "", urgent=True, take=True)
        elif state.startswith("armed_") and state != "armed_custom_bypass":
            await self._post("alarm", self.w["armed"])
        elif state == "disarmed":
            await self._post("alarm", self.w["disarmed"])

    # ---------- Pligt-pilot and Madplan ----------
    async def _task(self, event: Event) -> None:
        """A child took a machine in Pligt-pilot (taken here too, not told back), or made dinner (said to those at home)."""
        d = event.data
        kid = str(d.get("kid") or "").strip()
        if d.get("kind") == "taken" and d.get("source") == "machine":
            kind = str(d.get("machine") or "")
            m = next((x for x in reversed(self.chat.msgs) if x.get("take") and not x.get("taken")
                      and kind != "other" and self.chat.machine_kind(x) == kind), None)
            if m:
                who = next((p["id"] for p in self.chat.people() if kid and p["name"].lower() == kid.lower()), HOUSE)
                await self.chat.take(m["id"], who, name=kid or None, tell=False)
        elif d.get("kind") == "done" and d.get("source") == "meal":
            text = self.t["meal_ready"].format(meal=str(d.get("meal") or d.get("title") or "?"), kid=kid or "?")
            await self.chat.post(HOUSE, f"🍽️ {text}", kind="house", to=self.chat.dinner_people() or "home")  # yes in the dinner poll

    async def _cook(self, event: Event) -> None:
        """Madplan gave a child a dinner day: said to the family at 7 that morning (at once if later) - once per child and day."""
        d = event.data
        kid, meal = str(d.get("kid") or "").strip(), str(d.get("meal") or "").strip()
        try:
            day = date.fromisoformat(str(d.get("date") or ""))
        except ValueError:
            return
        if not kid or not meal or day < dt_util.now().date():
            return
        today = dt_util.now().date().isoformat()
        self.chat.cooks = {k: c for k, c in self.chat.cooks.items() if c["date"] >= today}  # days gone by
        key = f"{kid.lower()}|{day.isoformat()}"
        if (self.chat.cooks.get(key) or {}).get("sent"):
            return
        self.chat.cooks[key] = {"kid": kid, "meal": meal, "time": str(d.get("time") or "")[:5], "date": day.isoformat(), "sent": False}
        self.chat._save()
        self._plan_cook(key)

    def _plan_cook(self, key: str) -> None:
        if cancel := self._cook_timers.pop(key, None):
            cancel()
        c = self.chat.cooks[key]
        day = date.fromisoformat(c["date"])
        if day < dt_util.now().date():
            del self.chat.cooks[key]  # a day gone by: nothing to say or keep
            self.chat._save()
            return
        if c["sent"]:
            return
        at = datetime.combine(day, COOK_AT, tzinfo=dt_util.get_default_time_zone())
        if at <= dt_util.now():
            self.hass.async_create_task(self._say_cook(key))
            return

        async def _due(_now: Any) -> None:
            self._cook_timers.pop(key, None)
            await self._say_cook(key)

        self._cook_timers[key] = async_track_point_in_time(self.hass, _due, at)

    async def _say_cook(self, key: str) -> None:
        c = self.chat.cooks.get(key)
        if not c or c["sent"]:
            return
        c["sent"] = True
        self.chat._save()
        text = self.t["cook"].format(kid=c["kid"], meal=c["meal"]) + (self.t["cook_at"].format(t=c["time"]) if c["time"] else "")
        await self.chat.post(HOUSE, f"🍳 {text}", kind="house", to="all")
