"""The chat: messages, who is in the family, and getting each message to the right phones.

- Everyone with a person in Home Assistant is in the chat. Their phones are found by themselves (the person's
  device trackers that come from the companion app).
- A message from one of you goes to the others' phones; a message from the house goes to those at home (if nobody
  is home, to everyone). "I'll take it" removes it from the others' phones, and a house message nobody took goes to
  everyone after 10 minutes.
- Quiet hours per person: only urgent messages (smoke, water …) come through then.
- Write "to the house" and Assist answers - "Is the front door locked?", "Turn off the lights".
- Answers written in the phone's notification land in the chat.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta
import asyncio
import logging
from pathlib import Path
import re
import secrets
import time
from typing import Any
import uuid

from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify

from .const import AI_RETRY_S, AI_TIMEOUT_S, BUILTIN_AGENT, DOMAIN, ESCALATE_S, HOUSE, MAX_MESSAGES, NOTE_FALLBACK, SIGNAL, STALE_S, TEXT, UNSURE_S

_LOGGER = logging.getLogger(__name__)
GUARD_DOMAINS = ("lock", "alarm_control_panel")
GUARD_COVERS = ("garage", "gate", "door")
# a safety net before Assist even looks: locks, alarms, garage and gate - in the languages the chat speaks
GUARD_WORDS = re.compile(r"\b(lås|låse|låst|låsen|låsene|lock|locks|locked|unlock|alarm|alarmen|tyverialarm|garage|garagen|garageport|garageporten|port|porten|gate|schloss|tor|slot|serrure|portail)\b", re.I)
MEDIA_NAME = re.compile(r"^[a-f0-9]{32}\.(jpg|jpeg|png|webp|gif|webm|ogg|mp4|m4a|mp3|aac)$")


def _t(hass: HomeAssistant) -> dict[str, str]:
    return TEXT.get((hass.config.language or "en").split("-")[0], TEXT["en"])


class Chat:
    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store = Store(hass, 1, f"{DOMAIN}.messages")
        self.msgs: list[dict[str, Any]] = []
        self.read: dict[str, float] = {}  # user id -> last read message time
        self.prefs: dict[str, dict[str, Any]] = {}  # user id -> quiet hours, push, bubble
        self.conversations: dict[str, str] = {}  # user id -> Assist conversation id
        self.media_dir = Path(hass.config.path("hus_chat"))
        self._timers: dict[str, Any] = {}
        self.users: dict[str, str] = {}
        self.rules: dict[str, dict[str, Any]] = {}  # what the house writes by itself, and to whom (watch.py)
        self.agent: str | None = None  # the AI that answers for the house - None: the one Assist uses
        self._ai_down: dict[str, float] = {}  # an AI that failed (used up, offline) -> not tried again before this time
        self.seen: dict[str, float] = {}  # phone -> last time its location was there (not unavailable)
        self.phones_of: dict[str, list[dict[str, Any]]] = {}  # user id -> their phones, for "My phones"
        self.active: dict[str, float] = {}  # user id -> last time the chat was open and in front (no push then)
        # The chat as an app from a secret link (no Home Assistant account): link id -> name, person, token, browsers
        self.links: dict[str, dict[str, Any]] = {}
        self.pinned: str | None = None  # the message shown on top of the chat
        self.reminders: list[dict[str, Any]] = []  # "remind me ...": when, what, to whom
        self.speak: dict[str, Any] = {"on": False, "player": None}  # the house's messages read aloud on a speaker
        self.onway: dict[str, float] = {}  # person -> when they wrote "on my way home" (to say when they are home)
        self.vapid: Any = None  # the key web push is signed with (webpush.py)
        self.dinner: dict[str, Any] = {}  # today's dinner poll: {"date", "msg"} (watch.py)
        self.cooks: dict[str, dict[str, Any]] = {}  # "kid|date" -> who cooks what (Madplan), and whether it was said (watch.py)

    # ---------- storage ----------
    async def async_load(self) -> None:
        d = await self.store.async_load() or {}
        self.msgs = d.get("msgs", [])
        self.read = d.get("read", {})
        self.prefs = d.get("prefs", {})
        self.seen = d.get("seen", {})
        self.rules = d.get("rules", {})
        self.agent = d.get("agent")
        self.links = d.get("links", {})
        self.pinned = d.get("pinned")
        self.reminders = [r for r in d.get("reminders", []) if r.get("when", 0) > time.time() - 3600]
        self.speak = {"on": False, "player": None, **d.get("speak", {})}
        self.cooks = d.get("cooks", {})
        self.dinner = d.get("dinner", {})
        from .webpush import Vapid

        self.vapid = Vapid(d.get("vapid"))
        if not d.get("vapid"):
            self._save()
        await self.async_refresh_users()
        await self.hass.async_add_executor_job(lambda: self.media_dir.mkdir(exist_ok=True))
        self._rearm()
        # Pictures nobody sent (an upload that was cancelled) go once a day.
        from datetime import timedelta

        for r in self.reminders:
            self._arm_reminder(r)
        from homeassistant.const import EVENT_STATE_CHANGED

        self._timers["_home"] = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._arrived, event_filter=callback(lambda d: str(d.get("entity_id", "")).startswith("person.")))
        await self._tidy_media()
        self._timers["_tidy"] = async_track_time_interval(self.hass, self._tidy_media, timedelta(hours=24))

    async def _tidy_media(self, _now: Any = None) -> None:
        used = {n for m in self.msgs for n in (m.get("image"), m.get("audio")) if n}

        def tidy() -> None:
            cut = time.time() - 86400
            for f in self.media_dir.glob("*"):
                if MEDIA_NAME.match(f.name) and f.name not in used and f.stat().st_mtime < cut:
                    f.unlink(missing_ok=True)

        await self.hass.async_add_executor_job(tidy)

    def _rearm(self) -> None:
        """After a restart: house messages nobody took yet still go to everyone after 10 minutes."""
        now = time.time()
        for m in self.msgs:
            if m["kind"] == "house" and m.get("take") and m.get("to") == "home" and not m.get("taken") \
                    and not m.get("escalated") and now - m["t"] < 6 * ESCALATE_S:
                self._arm(m, set(m.get("sent") or []), max(5.0, ESCALATE_S - (now - m["t"])))

    def _save(self) -> None:
        self.store.async_delay_save(lambda: {"msgs": self.msgs, "read": self.read, "prefs": self.prefs, "seen": self.seen, "rules": self.rules, "agent": self.agent,
                                                  "links": self.links, "vapid": self.vapid.pem if self.vapid else None,
                                                  "pinned": self.pinned, "reminders": self.reminders, "speak": self.speak,
                                                  "cooks": self.cooks, "dinner": self.dinner}, 2)

    def stop(self) -> None:
        for cancel in self._timers.values():
            cancel()
        self._timers.clear()

    # ---------- the family ----------
    async def async_refresh_users(self) -> None:
        """The names of those who can sign in - for anyone with the app but no person in Home Assistant."""
        self.users = {u.id: u.name or "?" for u in await self.hass.auth.async_get_users() if not u.system_generated and u.is_active}

    def people(self) -> list[dict[str, Any]]:
        """Everyone with a person, and everyone with the Home Assistant app on a phone - a person isn't needed.

        At home: the person's state when there is one (it puts several devices together), otherwise the phone's own.
        """
        out: dict[str, dict[str, Any]] = {}
        for st in self.hass.states.async_all("person"):
            out[st.entity_id] = {"id": st.entity_id, "name": st.attributes.get("friendly_name") or st.entity_id.split(".")[1],
                                 "user_id": st.attributes.get("user_id"), "picture": st.attributes.get("entity_picture"),
                                 "home": st.state == "home", "unsure": self._unsure(st, st.attributes.get("device_trackers") or []),
                                 "phones": [], "_trackers": set(st.attributes.get("device_trackers") or [])}
        by_user = {p["user_id"]: p for p in out.values() if p["user_id"]}
        ents = er.async_get(self.hass)
        now, phones_of, changed = time.time(), {}, False
        for entry in self.hass.config_entries.async_entries("mobile_app"):
            name, uid = entry.data.get("device_name"), entry.data.get("user_id")
            svc = f"mobile_app_{slugify(name or '')}"
            if not name or not self.hass.services.has_service("notify", svc):
                continue  # no push on this device (e.g. a tablet without notifications)
            tracker = next((e.entity_id for e in er.async_entries_for_config_entry(ents, entry.entry_id) if e.domain == "device_tracker"), None)
            p = by_user.get(uid) or next((x for x in out.values() if tracker and tracker in x["_trackers"]), None)
            if p is None:
                if uid not in self.users:
                    continue
                st = self.hass.states.get(tracker) if tracker else None
                p = out[f"user.{uid}"] = {"id": f"user.{uid}", "name": self.users[uid], "user_id": uid, "picture": None,
                                          "home": bool(st and st.state == "home"), "unsure": self._unsure(st, [tracker] if tracker else []),
                                          "phones": [], "_trackers": set()}
                by_user[uid] = p
            # An old phone: turned off under "My phones", or its location gone for 30 days.
            tst = self.hass.states.get(tracker) if tracker else None
            if tst and tst.state not in ("unavailable", "unknown") and now - self.seen.get(svc, 0) > 3600:
                self.seen[svc], changed = now, True
            self.seen.setdefault(svc, now)
            stale = now - self.seen[svc] > STALE_S
            off = svc in (self.prefs.get(uid or "", {}).get("phones_off") or [])
            phones_of.setdefault(uid, []).append({"svc": svc, "name": name, "on": not off, "stale": stale})
            if svc not in p["phones"] and not off and not stale:
                p["phones"].append(svc)
        # The app from a link: as the person it belongs to, or on its own (a child without an account)
        for lid, link in self.links.items():
            p = out.get(link.get("person") or "")
            if p is None:
                p = out[f"link.{lid}"] = {"id": f"link.{lid}", "name": link.get("name") or "?", "user_id": f"link:{lid}", "picture": None,
                                          "home": False, "phones": [], "_trackers": set()}
            elif not p["user_id"]:
                p["user_id"] = f"link:{lid}"
            p.setdefault("web", []).append(lid)
        self.phones_of = phones_of
        if changed:
            self._save()
        return sorted(({k: v for k, v in p.items() if k != "_trackers"} for p in out.values()), key=lambda p: p["name"].lower())

    def _unsure(self, st: Any, trackers: list[str]) -> bool:
        """Away, but not sure of it: no location, or none of the phones has reported for UNSURE_S (asleep, or the app
        stopped by battery saving). Such a person gets messages "to those at home" too - in doubt, included."""
        if st is None or st.state in ("unknown", "unavailable"):
            return True
        if st.state == "home":
            return False
        times = [t.last_updated.timestamp() for x in trackers if (t := self.hass.states.get(x)) and t.state not in ("unknown", "unavailable")]
        return not times or time.time() - max(times) > UNSURE_S

    # ---------- dinner: who is home to eat (the poll at the chosen time) ----------
    def dinner_people(self) -> list[str] | None:
        """Those who answered yes in today's dinner poll, or None when there's no poll today or nobody said yes."""
        d = self.dinner or {}
        if d.get("date") != dt_util.now().date().isoformat():
            return None
        m = self.find(d.get("msg") or "")
        yes = list(m["poll"][0]["votes"]) if m and m.get("poll") else []
        return yes or None

    def person_of(self, user_id: str | None) -> dict[str, Any] | None:
        if user_id and user_id.startswith("link:"):  # the app from a link: whoever the link belongs to
            return next((p for p in self.people() if user_id[5:] in (p.get("web") or [])), None)
        return next((p for p in self.people() if user_id and p["user_id"] == user_id), None)

    def sender_of(self, user_id: str | None, user_name: str | None = None) -> str:
        p = self.person_of(user_id)
        return p["id"] if p else f"user:{user_id or 'unknown'}:{user_name or ''}"

    # ---------- who sees what ----------
    def is_mine(self, m: dict[str, Any], user_id: str, me: str | None = None) -> bool:
        """Written by this user - also before a person was linked to them (then it was "user:<id>:<name>")."""
        f = m.get("from") or ""
        return f == (me or self.sender_of(user_id)) or f == f"user.{user_id}" or f.startswith(f"user:{user_id}:")

    def member(self, user_id: str, admin: bool = False) -> bool:
        """In the family: a person, or the Home Assistant app on a phone - or an admin. A wall tablet's or a guest's
        account is not, and sees no messages."""
        if user_id.startswith("link:"):
            return user_id[5:] in self.links
        return admin or any(p["user_id"] == user_id for p in self.people())

    def can_see(self, m: dict[str, Any], user_id: str, me: str | None = None) -> bool:
        """A message to some of you is seen by them and its writer only; one to all (or those at home) by everyone.
        A question to the house and its answer are the asker's own."""
        me = me or self.sender_of(user_id)
        if self.is_mine(m, user_id, me):
            return True
        to = m.get("to") or "all"
        return me in to if isinstance(to, list) else True

    def visible(self, user_id: str, admin: bool = False) -> list[dict[str, Any]]:
        if not self.member(user_id, admin):
            return []
        me = self.sender_of(user_id)
        return [m for m in self.msgs if self.can_see(m, user_id, me)]

    def reads(self) -> dict[str, float]:
        """Who has read up to when (for "seen by"): person or user id -> time."""
        out = {}
        for uid, t in self.read.items():
            out[self.sender_of(uid)] = t
        return out

    # ---------- messages ----------
    async def post(self, sender: str, text: str = "", *, image: str | None = None, audio: str | None = None,
                   kind: str = "chat", take: bool = False, to: str | list[str] = "all", urgent: bool = False,
                   title: str | None = None, push: bool = True, topic: str | None = None, note: str | None = None,
                   cid: str | None = None, reply: str | None = None, machine: str | None = None,
                   mtype: str | None = None, poll: list[str] | None = None) -> dict[str, Any]:
        if cid and (same := next((m for m in reversed(self.msgs[-200:]) if m.get("cid") == cid and m["from"] == sender), None)):
            return same  # sent again after a lost connection: it was already here
        msg = {"id": uuid.uuid4().hex[:12], "t": time.time(), "from": sender, "name": self._name(sender), "text": str(text or "")[:4000], "kind": kind,
               "image": image, "audio": audio, "take": bool(take), "taken": None, "to": to, "urgent": bool(urgent), "title": title, "topic": topic}
        if note:
            msg["note"] = note
        if cid:
            msg["cid"] = cid[:40]
        if poll:
            msg["poll"] = [{"t": str(o)[:80], "votes": []} for o in poll[:6]]
        if machine:
            msg["machine"] = machine  # kept with the message, so "emptied" finds it also after a restart
        if mtype:
            msg["mtype"] = mtype  # washer, dryer, dishwasher or other - to match the machine in other apps (Pligt-pilot)
        if reply and (r := self.find(reply)):
            msg["reply"] = {"id": r["id"], "name": r.get("name") or "", "text": (r.get("text") or r.get("title") or
                            (_t(self.hass)["image"] if r.get("image") else _t(self.hass)["audio"] if r.get("audio") else ""))[:140]}
        self.msgs.append(msg)
        if len(self.msgs) > MAX_MESSAGES:
            gone, self.msgs = self.msgs[:-MAX_MESSAGES], self.msgs[-MAX_MESSAGES:]
            await self.hass.async_add_executor_job(self._remove_media, gone)
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "message", msg)
        if push:
            await self._deliver(msg)
        if kind == "house" and self.speak.get("on"):
            self.hass.async_create_task(self._say(msg))
        if kind == "chat" and sender != HOUSE and msg["text"]:
            await self._understand(msg)
        return msg

    def _remove_media(self, gone: list[dict[str, Any]]) -> None:
        for m in gone:
            for name in (m.get("image"), m.get("audio")):
                if name and MEDIA_NAME.match(name):
                    (self.media_dir / name).unlink(missing_ok=True)

    def find(self, msg_id: str) -> dict[str, Any] | None:
        return next((m for m in reversed(self.msgs) if m["id"] == msg_id), None)

    async def take(self, msg_id: str, sender: str, name: str | None = None, tell: bool = True) -> dict[str, Any] | None:
        """Taken - from the chat, the phone or the house. A machine taken here is told to other apps (Pligt-pilot),
        unless it came from them (tell=False)."""
        m = self.find(msg_id)
        if not m or m.get("taken"):
            return m
        m["taken"] = {"by": sender, "name": name or self._name(sender), "t": time.time()}
        if cancel := self._timers.pop(msg_id, None):
            cancel()
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "update", m)
        if tell and sender != HOUSE and (kind := self.machine_kind(m)):
            self.hass.bus.async_fire("hus_chat_machine", {"kind": "taken", "machine": kind, "name": m["taken"]["name"]})
        await self._clear_phones(msg_id)  # gone from everyone's phone
        return m

    async def pligt_link(self, m: dict[str, Any] | None, name: str) -> str | None:
        """A child's link to the machine chore in Pligt-pilot, so children take it there (and get paid) instead of in
        the chat. None: not a free machine message, Pligt-pilot isn't installed, or the name isn't one of its children."""
        if not m or m.get("taken") or not (kind := self.machine_kind(m)):
            return None
        find = getattr(self.hass.data.get("pligt_pilot"), "kid_link", None)
        if not find:
            return None
        try:
            return await find(name, kind)
        except Exception:  # noqa: BLE001 - Pligt-pilot is a guest here: never break the chat
            _LOGGER.debug("No Pligt-pilot link for %s", name, exc_info=True)
            return None

    def machine_message(self, key: str) -> dict[str, Any] | None:
        return next((m for m in reversed(self.msgs) if m.get("machine") == key and not m.get("taken")), None)

    def machine_kind(self, m: dict[str, Any]) -> str | None:
        """The machine's type on a machine message - also on one from before the type was kept (from its name in
        Appliance Watch). None: not a machine (a freezer's alert, any other message)."""
        if m.get("mtype"):
            return m["mtype"]
        key = m.get("machine") or ""
        entry = self.hass.config_entries.async_get_entry(key) if key and not key.startswith("aw:") else None
        if not entry or entry.domain != "appliance_watch":
            return None
        from .watch import machine_type

        return machine_type(entry.title)

    async def delete(self, msg_id: str, user_id: str, admin: bool) -> bool:
        """Your own message - or any, for an admin. Its picture or voice message goes too."""
        m = self.find(msg_id)
        if not m or not (admin or self.is_mine(m, user_id)):
            return False
        self.msgs.remove(m)
        self.cancel_reminders(msg_id)
        if self.pinned == msg_id:
            self.pin(None)
        await self.hass.async_add_executor_job(self._remove_media, [m])
        if cancel := self._timers.pop(msg_id, None):
            cancel()
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "delete", {"id": msg_id})
        await self._clear_phones(msg_id)
        return True

    async def clear_all(self) -> None:
        """An admin empties the chat: every message, picture and voice message."""
        gone, self.msgs = self.msgs, []
        await self.hass.async_add_executor_job(self._remove_media, gone)
        for key in [k for k in self._timers if k != "_tidy"]:
            self._timers.pop(key)()
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "clear", {})

    def edit(self, msg_id: str, user_id: str, text: str) -> bool:
        m = self.find(msg_id)
        if not m or m["kind"] not in ("chat",) or not self.is_mine(m, user_id) or not text.strip():
            return False
        m["text"], m["edited"] = text.strip()[:4000], time.time()
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "update", m)
        return True

    def react(self, msg_id: str, user_id: str, emoji: str) -> bool:
        m = self.find(msg_id)
        if not m or not self.can_see(m, user_id):
            return False
        me = self.sender_of(user_id)
        who = (m.setdefault("reactions", {})).setdefault(emoji, [])
        who.remove(me) if me in who else who.append(me)
        m["reactions"] = {k: v for k, v in m["reactions"].items() if v}
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "update", m)
        return True

    def mark_read(self, user_id: str, t: float) -> None:
        old = self.read.get(user_id, 0)
        if t > old:
            self.read[user_id] = t
            self._save()
            async_dispatcher_send(self.hass, SIGNAL, "read", {"who": self.sender_of(user_id), "t": t})
            # Read here: gone from this person's phones too.
            me = self.sender_of(user_id)
            ids = [m["id"] for m in self.msgs if old < m["t"] <= t and not self.is_mine(m, user_id, me)][-30:]
            if ids:
                self.hass.async_create_task(self._clear_phones(*ids, user_id=user_id))

    async def _clear_phones(self, *msg_ids: str, user_id: str | None = None) -> None:
        for p in self.people():
            if user_id is not None and p["user_id"] != user_id:
                continue
            for svc in p["phones"]:
                for msg_id in msg_ids:
                    await self._notify(svc, {"message": "clear_notification", "data": {"tag": f"huschat-{msg_id}"}})

    def unread(self, user_id: str, admin: bool = False) -> int:
        """Messages to you that you haven't read - not your own, not those meant for others."""
        me, last = self.sender_of(user_id), self.read.get(user_id, 0)
        return sum(1 for m in self.visible(user_id, admin) if m["t"] > last and not self.is_mine(m, user_id, me))

    def set_active(self, user_id: str, on: bool) -> None:
        if on:
            self.active[user_id] = time.time()
        else:
            self.active.pop(user_id, None)

    def set_prefs(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        cur = {"quiet": False, "quiet_from": "22:00", "quiet_to": "07:00", "push": True, "bubble": True, "closed": 0, "phones_off": [], "muted": [], **self.prefs.get(user_id, {})}
        cur.update({k: v for k, v in prefs.items() if k in cur})
        self.prefs[user_id] = cur
        self._save()
        return cur

    def get_prefs(self, user_id: str) -> dict[str, Any]:
        return {"quiet": False, "quiet_from": "22:00", "quiet_to": "07:00", "push": True, "bubble": True, "closed": 0, "phones_off": [], "muted": [],
                **self.prefs.get(user_id, {})}

    def set_rules(self, rules: dict[str, Any]) -> dict[str, Any]:
        from .watch import DEFAULT_RULES

        for topic, r in rules.items():
            if topic in DEFAULT_RULES:
                cur = {**DEFAULT_RULES[topic], **self.rules.get(topic, {})}
                cur.update({k: v for k, v in r.items() if k in ("on", "to") or (k == "at" and "at" in DEFAULT_RULES[topic])})
                self.rules[topic] = cur
        self._save()
        return self.get_rules()

    # ---------- who answers for the house (any AI set up in Home Assistant) ----------
    def assist_agent(self) -> str | None:
        """The conversation agent of the preferred Assist pipeline - what answers when nothing is chosen."""
        try:
            from homeassistant.components.assist_pipeline import async_get_pipeline

            return async_get_pipeline(self.hass).conversation_engine
        except Exception:  # noqa: BLE001 - no Assist pipeline: Home Assistant's own agent
            return None

    def agents(self) -> dict[str, Any]:
        found = [{"id": s.entity_id, "name": s.name} for s in self.hass.states.async_all("conversation")]
        return {"chosen": self.agent, "assist": self.assist_agent(), "list": sorted(found, key=lambda a: a["name"].lower())}

    def set_agent(self, agent: str | None) -> dict[str, Any]:
        self.agent = agent or None
        self._save()
        return self.agents()

    def get_rules(self) -> dict[str, Any]:
        from .watch import DEFAULT_RULES

        return {t: {**d, **self.rules.get(t, {})} for t, d in DEFAULT_RULES.items()}

    # ---------- to the phones ----------
    def _quiet(self, user_id: str | None) -> bool:
        p = self.prefs.get(user_id or "", {})
        if not p.get("quiet"):
            return False
        try:
            a, b = dtime.fromisoformat(p.get("quiet_from") or "22:00"), dtime.fromisoformat(p.get("quiet_to") or "07:00")
        except ValueError:
            return False
        now = dt_util.now().time()
        return a <= now or now < b if a > b else a <= now < b

    def _recipients(self, msg: dict[str, Any], everyone: bool = False) -> list[dict[str, Any]]:
        people = [p for p in self.people() if (p["phones"] or p.get("web")) and p["id"] != msg["from"]]
        to = msg.get("to") or "all"
        if isinstance(to, list):
            people = [p for p in people if p["id"] in to]
        elif to == "home" and not everyone:
            home = [p for p in people if p["home"] or p.get("unsure")]  # in doubt: included
            people = home or people  # nobody home: everyone
        from .watch import ALWAYS

        def wants(p: dict[str, Any]) -> bool:
            pr = self.prefs.get(p["user_id"] or "", {})
            if msg.get("topic") in ALWAYS:
                return True  # smoke, water, CO: always, also in quiet hours and with messages off
            if msg.get("topic") and msg["topic"] in (pr.get("muted") or []):
                return False
            seen = max([self.active.get(p["user_id"] or "", 0)] + [self.active.get(f"link:{x}", 0) for x in p.get("web") or []])
            if not msg.get("urgent") and time.time() - seen < 90:
                return False  # has the chat open right now: sees it there
            return (msg.get("urgent") or not self._quiet(p["user_id"])) and pr.get("push", True) is not False

        return [p for p in people if wants(p)]

    def _name(self, sender: str) -> str:
        if sender == HOUSE:
            return _t(self.hass)["house"]
        if sender.startswith("person."):
            st = self.hass.states.get(sender)
            return (st and st.attributes.get("friendly_name")) or sender.split(".")[1]
        if sender.startswith("user."):
            return self.users.get(sender[5:], "?")
        if sender.startswith("link."):
            return (self.links.get(sender[5:]) or {}).get("name") or "?"
        return sender.split(":")[2] or "?" if sender.count(":") >= 2 else "?"

    def _push_data(self, msg: dict[str, Any], extra: str = "", kid_url: str | None = None) -> dict[str, Any]:
        t = _t(self.hass)
        body = (extra + "\n" if extra else "") + (msg["text"] or (t["image"] if msg.get("image") else t["audio"] if msg.get("audio") else ""))
        title = msg.get("title") or (f"{self._name(msg['from'])}" if msg["kind"] == "chat" else f"🏠 {t['house']}")
        actions = []
        if msg.get("take") and not msg.get("taken"):
            actions.append({"action": "URI", "title": t["take_pligt"], "uri": kid_url} if kid_url
                           else {"action": f"HUSCHAT_TAKE_{msg['id']}", "title": t["take"]})
        if msg.get("poll"):  # answer from the notification (Android shows three buttons)
            actions += [{"action": f"HUSCHAT_VOTE_{msg['id']}_{i}", "title": o["t"]} for i, o in enumerate(msg["poll"][:3])]
        else:
            actions.append({"action": "REPLY", "title": t["reply"], "behavior": "textInput"})
        data: dict[str, Any] = {"tag": f"huschat-{msg['id']}", "group": "hus-chat", "url": "/hus-chat", "clickAction": "/hus-chat",
                                "actions": actions, "channel": "Hus-chat urgent" if msg.get("urgent") else "Hus-chat"}
        if msg.get("image"):
            data["image"] = f"/api/hus_chat/media/{msg['image']}"
        if msg.get("urgent"):
            # Rings like an alarm, also on silent: a critical alert on iPhone, the alarm stream on Android.
            data.update({"priority": "high", "ttl": 0, "channel": "alarm_stream", "importance": "high",
                         "push": {"interruption-level": "critical", "sound": {"name": "default", "critical": 1, "volume": 1.0}}})
        return {"title": title, "message": body, "data": data}

    async def _notify(self, svc: str, payload: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call("notify", svc, payload, blocking=False)
        except Exception:  # noqa: BLE001 - one phone failing doesn't stop the others
            _LOGGER.debug("Push to %s failed", svc, exc_info=True)

    async def _deliver(self, msg: dict[str, Any]) -> None:
        sent = set()
        for p in self._recipients(msg):
            kid_url = await self.pligt_link(msg, p["name"]) if p["phones"] and msg.get("take") else None
            for svc in p["phones"]:
                await self._notify(svc, self._push_data(msg, kid_url=kid_url))
            for lid in p.get("web") or []:
                await self._webpush(lid, msg)
            sent.add(p["id"])
        if msg["kind"] == "house" and msg.get("take") and msg.get("to") == "home":
            msg["sent"] = sorted(sent)  # kept, so a restart can still send it to the others (_rearm)
            self._save()
            self._arm(msg, sent, ESCALATE_S)

    def _arm(self, msg: dict[str, Any], sent: set[str], delay: float) -> None:
        @callback
        def _escalate(_now: Any) -> None:
            self._timers.pop(msg["id"], None)
            if not msg.get("taken") and msg in self.msgs:
                msg["escalated"] = True
                self._save()
                self.hass.async_create_task(self._escalate(msg, sent))

        self._timers[msg["id"]] = async_call_later(self.hass, delay, _escalate)

    async def _escalate(self, msg: dict[str, Any], sent: set[str]) -> None:
        for p in self._recipients(msg, everyone=True):
            if p["id"] in sent:
                continue
            kid_url = await self.pligt_link(msg, p["name"]) if p["phones"] else None
            for svc in p["phones"]:
                await self._notify(svc, self._push_data(msg, _t(self.hass)["nobody"], kid_url))
            for lid in p.get("web") or []:
                await self._webpush(lid, msg, _t(self.hass)["nobody"])

    # ---------- what the chat understands, and the little extras ----------
    async def _understand(self, msg: dict[str, Any]) -> None:
        """ "køb mælk og brød" goes on the shopping list; "mind mig om ... i morgen kl. 8" becomes a reminder."""
        from . import smart

        if items := smart.shop_items(msg["text"]):
            entity = self.shop_entity()
            if entity:
                for item in items:
                    try:
                        await self.hass.services.async_call("todo", "add_item", {"entity_id": entity, "item": item}, blocking=True)
                    except Exception:  # noqa: BLE001 - a list that refuses: the message stays a message
                        _LOGGER.debug("Could not add %s to %s", item, entity, exc_info=True)
                        return
                msg["shop"] = items
                self._save()
                async_dispatcher_send(self.hass, SIGNAL, "update", msg)
            return
        r = smart.reminder(msg["text"], dt_util.now().replace(tzinfo=None))
        if not r:
            return
        when = dt_util.as_utc(r["when"].replace(tzinfo=dt_util.get_default_time_zone())).timestamp()
        rem = {"id": uuid.uuid4().hex[:10], "when": when, "what": r["what"], "to": "all" if r["all"] else [msg["from"]], "by": msg["from"], "msg": msg["id"]}
        self.reminders.append(rem)
        self._arm_reminder(rem)
        msg["remind"] = when
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "update", msg)

    def _arm_reminder(self, rem: dict[str, Any]) -> None:
        @callback
        def _due(_now: Any) -> None:
            self._timers.pop(f"rem-{rem['id']}", None)
            if rem in self.reminders:
                self.reminders.remove(rem)
                self._save()
                self.hass.async_create_task(self.post(HOUSE, f"⏰ {rem['what']}", kind="house", to=rem["to"]))

        self._timers[f"rem-{rem['id']}"] = async_call_later(self.hass, max(1.0, rem["when"] - time.time()), _due)

    def cancel_reminders(self, msg_id: str) -> None:
        for rem in [r for r in self.reminders if r.get("msg") == msg_id]:
            self.reminders.remove(rem)
            if cancel := self._timers.pop(f"rem-{rem['id']}", None):
                cancel()
        self._save()

    def shop_entity(self) -> str | None:
        """Home Assistant's shopping list - or a to-do list called something like it."""
        lists = [s for s in self.hass.states.async_all("todo")]
        for st in lists:
            if st.entity_id == "todo.shopping_list":
                return st.entity_id
        word = re.compile(r"indkøb|indkob|handle|shopping|grocer|einkauf|inköp|innkjøp|boodschap|courses", re.I)
        return next((st.entity_id for st in lists if word.search(st.entity_id + " " + str(st.attributes.get("friendly_name")))), None)

    async def shop_list(self, add: str | None = None, done: str | None = None) -> dict[str, Any]:
        entity = self.shop_entity()
        if not entity:
            return {"entity": None, "items": []}
        if add and add.strip():
            await self.hass.services.async_call("todo", "add_item", {"entity_id": entity, "item": add.strip()[:60]}, blocking=True)
        if done:
            await self.hass.services.async_call("todo", "update_item", {"entity_id": entity, "item": done, "status": "completed"}, blocking=True)
        res = await self.hass.services.async_call("todo", "get_items", {"entity_id": entity, "status": "needs_action"}, blocking=True, return_response=True)
        items = (res or {}).get(entity, {}).get("items", [])
        st = self.hass.states.get(entity)
        return {"entity": entity, "name": st.name if st else entity, "items": [{"uid": i.get("uid"), "summary": i.get("summary")} for i in items]}

    async def _say(self, msg: dict[str, Any]) -> None:
        """A house message read aloud: on the chosen speaker, not at night (unless urgent), only with somebody home."""
        player = self.speak.get("player")
        if not player or not self.hass.states.get(player):
            return
        hour = dt_util.now().hour
        if not msg.get("urgent") and (hour >= 22 or hour < 7 or not any(p["home"] for p in self.people())):
            return
        await self.say(" ".join(x for x in (msg.get("title"), msg.get("text")) if x))

    async def say(self, text: str) -> bool:
        tts = next((s.entity_id for s in self.hass.states.async_all("tts")), None)
        player = self.speak.get("player")
        if not tts or not player or not text:
            return False
        try:
            await self.hass.services.async_call("tts", "speak", {"entity_id": tts, "media_player_entity_id": player, "message": text[:400]}, blocking=False)
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Could not read aloud", exc_info=True)
            return False
        return True

    def set_speak(self, on: bool | None = None, player: str | None = None) -> dict[str, Any]:
        if on is not None:
            self.speak["on"] = bool(on)
        if player is not None:
            self.speak["player"] = player or None
        self._save()
        return self.speak_info()

    def speak_info(self) -> dict[str, Any]:
        players = [{"id": s.entity_id, "name": s.name} for s in self.hass.states.async_all("media_player")]
        return {**self.speak, "players": sorted(players, key=lambda x: x["name"].lower()),
                "tts": bool(self.hass.states.async_all("tts"))}

    async def on_my_way(self, sender: str) -> dict[str, Any]:
        """ "On my way home - home about 17:40" from where the phone is; the house says so when they arrive."""
        from . import smart

        p = next((x for x in self.people() if x["id"] == sender), None)
        st = self.hass.states.get(sender) if sender.startswith("person.") else None
        lat, lon = (st.attributes.get("latitude"), st.attributes.get("longitude")) if st else (None, None)
        mins = smart.eta_minutes(lat, lon, self.hass.config.latitude, self.hass.config.longitude) if not (p and p["home"]) else None
        t = TEXT.get((self.hass.config.language or "en").split("-")[0], TEXT["en"])
        text = t["onway"] + (f" – {t['eta'].format(t=(dt_util.now() + timedelta(minutes=mins)).strftime('%H:%M'))}" if mins else "")
        self.onway[sender] = time.time()
        return await self.post(sender, f"🚗 {text}")

    @callback
    def _arrived(self, event: Event) -> None:
        new, old = event.data.get("new_state"), event.data.get("old_state")
        who = event.data.get("entity_id")
        if not new or new.state != "home" or (old and old.state == "home") or who not in self.onway:
            return
        if time.time() - self.onway.pop(who) > 4 * 3600:
            return
        t = TEXT.get((self.hass.config.language or "en").split("-")[0], TEXT["en"])
        self.hass.async_create_task(self.post(HOUSE, f"🏠 {t['arrived'].format(name=self._name(who))}", kind="house", to="all"))

    def vote(self, msg_id: str, user_id: str, option: int, keep: bool = False) -> bool:
        """A tap on your own answer takes it back - unless keep (a button in the notification: pressed twice, still yes)."""
        m = self.find(msg_id)
        if not m or not m.get("poll") or not self.can_see(m, user_id) or not 0 <= option < len(m["poll"]):
            return False
        me = self.sender_of(user_id)
        mine = me in m["poll"][option]["votes"]
        if mine and keep:
            return True
        for o in m["poll"]:
            if me in o["votes"]:
                o["votes"].remove(me)
        if not mine:
            m["poll"][option]["votes"].append(me)
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "update", m)
        return True

    def pin(self, msg_id: str | None) -> bool:
        if msg_id and not self.find(msg_id):
            return False
        self.pinned = msg_id or None
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "pin", {"id": self.pinned})
        return True

    # ---------- the chat as an app from a link ----------
    def link_by_token(self, token: str) -> str | None:
        for lid, link in self.links.items():
            if secrets.compare_digest(str(link.get("token") or ""), str(token or "")):
                return lid
        return None

    def add_link(self, name: str, person: str | None) -> dict[str, Any]:
        lid = uuid.uuid4().hex[:10]
        self.links[lid] = {"name": name.strip()[:40], "person": person or None, "token": secrets.token_urlsafe(24),
                           "created": time.time(), "subs": [], "house": False}
        self._save()
        return self.links[lid]

    def set_link_house(self, lid: str, on: bool) -> bool:
        """May this link talk to the house? Off from the start: a link has no login."""
        if lid not in self.links:
            return False
        self.links[lid]["house"] = bool(on)
        self._save()
        return True

    def remove_link(self, lid: str) -> bool:
        if self.links.pop(lid, None) is None:
            return False
        self.read.pop(f"link:{lid}", None)
        self.prefs.pop(f"link:{lid}", None)
        self._save()
        return True

    def add_sub(self, lid: str, sub: dict[str, Any]) -> None:
        subs = [x for x in self.links[lid].setdefault("subs", []) if x.get("endpoint") != sub["endpoint"]]
        self.links[lid]["subs"] = (subs + [{"endpoint": sub["endpoint"], "keys": sub["keys"]}])[-5:]
        self._save()

    async def _webpush(self, lid: str, msg: dict[str, Any], extra: str = "") -> None:
        link = self.links.get(lid)
        if not link or not link.get("subs") or not self.vapid:
            return
        from homeassistant.helpers.aiohttp_client import async_get_clientsession

        from . import webpush

        d = self._push_data(msg, extra)
        data = {"title": d["title"], "body": d["message"], "tag": d["data"]["tag"], "url": f"/hus_chat_app/{link['token']}",
                "image": d["data"].get("image"), "urgent": bool(msg.get("urgent"))}
        session, gone = async_get_clientsession(self.hass), []
        for sub in list(link["subs"]):
            if not await webpush.send(session, self.vapid, sub, data, urgent=bool(msg.get("urgent"))):
                gone.append(sub)
        if gone:
            link["subs"] = [x for x in link["subs"] if x not in gone]
            self._save()

    # ---------- answers from the phone's notification ----------
    async def on_action(self, event: Event) -> None:
        action = str(event.data.get("action") or "")
        user = event.context.user_id
        if action.startswith("HUSCHAT_TAKE_"):
            await self.take(action.removeprefix("HUSCHAT_TAKE_"), self.sender_of(user))
        elif action.startswith("HUSCHAT_VOTE_") and user:
            msg_id, _, option = action.removeprefix("HUSCHAT_VOTE_").rpartition("_")
            if option.isdigit():
                self.vote(msg_id, user, int(option), keep=True)
        elif action in ("REPLY", "HUSCHAT_REPLY") and (text := str(event.data.get("reply_text") or "").strip()):
            tag = str(event.data.get("tag") or "")
            if tag and not tag.startswith("huschat-"):
                return  # another integration's reply
            await self.post(self.sender_of(user), text)

    # ---------- the house answers (Assist) ----------
    async def ask_house(self, user_id: str | None, text: str) -> dict[str, Any]:
        if user_id and user_id.startswith("link:"):
            return await self._ask_from_link(user_id, text)
        return await self._ask_house(user_id, text)

    async def _ask_from_link(self, uid: str, text: str) -> dict[str, Any]:
        """A link may talk to the house only when an admin allowed it, only through Home Assistant's own Assist (no AI
        with tools), and never about locks, alarms or garage doors and gates - a link has no login."""
        if not (self.links.get(uid[5:]) or {}).get("house"):
            return await self.post(HOUSE, _t(self.hass)["house_off"], kind="assist", push=False, to=[self.sender_of(uid)])
        if await self._guarded(text):
            return await self.post(HOUSE, _t(self.hass)["house_guarded"], kind="assist", push=False, to=[self.sender_of(uid)])
        answer = await self._converse(None, text, uid, builtin=True)
        return await self.post(HOUSE, answer or "🤷", kind="assist", push=False, to=[self.sender_of(uid)])

    async def _guarded(self, text: str) -> bool:
        """True when the sentence would touch a lock, an alarm, or a garage door or gate - or can't be checked."""
        if GUARD_WORDS.search(text):
            return True
        try:
            import dataclasses

            from homeassistant.components import conversation
            from homeassistant.helpers import intent

            agent = conversation.async_get_agent(self.hass, BUILTIN_AGENT)
            fields = {f.name for f in dataclasses.fields(conversation.ConversationInput)}
            args = {"text": text, "context": Context(), "conversation_id": None, "device_id": None, "satellite_id": None,
                    "language": self.hass.config.language, "agent_id": BUILTIN_AGENT}
            result = await agent.async_recognize_intent(conversation.ConversationInput(**{k: v for k, v in args.items() if k in fields}))
        except Exception:  # noqa: BLE001 - can't be checked: not allowed
            _LOGGER.debug("Could not check a sentence from a link", exc_info=True)
            return True
        if result is None or not getattr(result, "intent", None):
            return False  # not understood: Assist does nothing either
        ent = {k: getattr(v, "value", v) for k, v in (result.entities or {}).items()}
        dom = ent.get("domain")
        cls = ent.get("device_class")
        match = intent.async_match_targets(self.hass, intent.MatchTargetsConstraints(
            name=ent.get("name") if isinstance(ent.get("name"), str) else None,
            area_name=ent.get("area") if isinstance(ent.get("area"), str) else None,
            floor_name=ent.get("floor") if isinstance(ent.get("floor"), str) else None,
            domains=[dom] if isinstance(dom, str) else (list(dom) if isinstance(dom, (list, tuple, set)) else None),
            device_classes=[cls] if isinstance(cls, str) else (list(cls) if isinstance(cls, (list, tuple, set)) else None),
            assistant="conversation"))
        for st in match.states if match.is_match else []:
            domain = st.entity_id.split(".", 1)[0]
            if domain in GUARD_DOMAINS or (domain == "cover" and st.attributes.get("device_class") in GUARD_COVERS):
                return True
        return False

    async def _ask_house(self, user_id: str | None, text: str) -> dict[str, Any]:
        """Like Assist with "prefer local commands": Home Assistant's own Assist first - "turn off the lights" is done at
        once - and only what it doesn't understand goes to the chosen AI. If the AI can't answer (quota used up, offline,
        no answer in 45 s), Home Assistant's answer is used with a small note, and the AI rests for 30 minutes."""
        agent = self.agent or self.assist_agent()  # the chosen AI, or the one Assist uses
        if agent and not self.hass.states.get(agent) and agent != BUILTIN_AGENT:
            agent = None  # removed since: Home Assistant's own
        note = None
        if not agent or agent == BUILTIN_AGENT:
            answer = await self._converse(None, text, user_id, builtin=True)
        elif (answer := await self._converse(None, text, user_id)) is None:  # not a command Home Assistant knows
            if time.time() >= self._ai_down.get(agent, 0):
                answer = await self._converse(agent, text, user_id, timeout=AI_TIMEOUT_S)
                if answer is None:
                    self._ai_down[agent] = time.time() + AI_RETRY_S
            if answer is None:
                st = self.hass.states.get(agent)
                note = NOTE_FALLBACK.get((self.hass.config.language or "en").split("-")[0], NOTE_FALLBACK["en"]).format(name=st.name if st else agent)
                answer = await self._converse(None, text, user_id, builtin=True)
        return await self.post(HOUSE, answer or "🤷", kind="assist", push=False, note=note, to=[self.sender_of(user_id)])

    async def _converse(self, agent: str | None, text: str, user_id: str | None, builtin: bool = False,
                        timeout: float | None = None) -> str | None:
        """One question to one agent (None: Home Assistant's own). None when it can't answer - unless builtin, then
        Home Assistant's answer is given whatever it is ("Sorry, I didn't understand")."""
        from homeassistant.components import conversation

        key = f"{user_id or ''}|{agent or ''}"  # a conversation goes on with the same AI
        try:
            res = await asyncio.wait_for(conversation.async_converse(
                self.hass, text, self.conversations.get(key), Context(user_id=None if (user_id or "").startswith("link:") else user_id), language=self.hass.config.language,
                agent_id=agent), timeout)
        except Exception:  # noqa: BLE001 - also a timeout
            _LOGGER.warning("Assist did not answer (%s)", agent or "Home Assistant", exc_info=True)
            return "🤷" if builtin else None
        if res.conversation_id:
            self.conversations[key] = res.conversation_id
        kind = getattr(res.response, "response_type", None)
        speech = ((res.response.speech or {}).get("plain") or {}).get("speech")
        if not builtin and getattr(kind, "value", kind) == "error":
            _LOGGER.debug("%s could not answer: %s", agent or "Home Assistant", speech)
            return None
        return speech or "✓"

    # ---------- pictures and voice messages ----------
    def save_media(self, data: bytes, ext: str) -> str:
        name = f"{uuid.uuid4().hex}.{ext}"
        (self.media_dir / name).write_bytes(data)
        return name

    def to_m4a(self, name: str) -> str:
        """A voice message recorded as WebM (Android, Chrome) is made M4A so iPhones can play it too - if ffmpeg is there."""
        import shutil
        import subprocess

        if not name.endswith((".webm", ".ogg")) or not shutil.which("ffmpeg"):
            return name
        new = name.rsplit(".", 1)[0] + ".m4a"
        try:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(self.media_dir / name), "-c:a", "aac", "-b:a", "64k",
                            str(self.media_dir / new)], check=True, timeout=60)
            (self.media_dir / name).unlink(missing_ok=True)
            return new
        except Exception:  # noqa: BLE001
            return name

    def setup_info(self, support: Any) -> dict[str, Any]:
        """How House Chat is set up - for the developer (support.py, once a day, names cleaned unless the user shares
        them): which AI answers for the house, how many phones and persons, which house messages are on. Never names,
        messages or who wrote what."""
        reg = er.async_get(self.hass)
        devices = []
        chosen = self.agent or self.assist_agent()
        if chosen:
            ent = reg.async_get(chosen)
            devices.append({"kind": "ai", "platform": ent.platform if ent else ("builtin" if chosen == BUILTIN_AGENT else chosen.split(".")[0]),
                            **support.device(ent.device_id if ent else None),
                            "ok": time.time() >= self._ai_down.get(chosen, 0),
                            "entities": [support.entity(chosen, "chosen" if self.agent else "assist")] if self.hass.states.get(chosen) else [],
                            "extra": {"own_choice": bool(self.agent), "builtin": chosen == BUILTIN_AGENT}})
        try:
            from homeassistant.components.assist_pipeline import async_get_pipeline

            pl = async_get_pipeline(self.hass)
            for kind, eng in (("stt", pl.stt_engine), ("tts", pl.tts_engine)):
                if eng:
                    ent = reg.async_get(eng) if "." in str(eng) else None
                    devices.append({"kind": kind, "platform": ent.platform if ent else str(eng).split(".")[0][:40]})
        except Exception:  # noqa: BLE001 - no Assist pipeline
            pass
        people, rules = self.people(), self.get_rules()
        return {"devices": devices,
                "counts": {"persons": sum(1 for p in people if p["id"].startswith("person.")), "people": len(people),
                           "phones": sum(len(p["phones"]) for p in people), "quiet_users": sum(1 for p in self.prefs.values() if p.get("quiet"))},
                "features": {**{f"msg_{k}": bool(v.get("on")) for k, v in rules.items()},
                             **{f"to_{k}": (v.get("to") if v.get("to") in ("home", "all", "everyone") else "persons") for k, v in rules.items()},  # never a person's id
                             "own_ai": bool(self.agent)}}

    def summary(self) -> dict[str, Any]:
        people = self.people()
        return {"people": len(people), "with_phone": sum(1 for p in people if p["phones"]), "messages": len(self.msgs),
                "house_messages": sum(1 for m in self.msgs if m["kind"] == "house")}
