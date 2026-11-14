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

from datetime import datetime, time as dtime
import logging
from pathlib import Path
import re
import time
from typing import Any
import uuid

from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN, ESCALATE_S, HOUSE, MAX_MESSAGES, SIGNAL, TEXT

_LOGGER = logging.getLogger(__name__)
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

    # ---------- storage ----------
    async def async_load(self) -> None:
        d = await self.store.async_load() or {}
        self.msgs = d.get("msgs", [])
        self.read = d.get("read", {})
        self.prefs = d.get("prefs", {})
        await self.async_refresh_users()
        await self.hass.async_add_executor_job(lambda: self.media_dir.mkdir(exist_ok=True))

    def _save(self) -> None:
        self.store.async_delay_save(lambda: {"msgs": self.msgs, "read": self.read, "prefs": self.prefs}, 2)

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
                                 "home": st.state == "home", "phones": [], "_trackers": set(st.attributes.get("device_trackers") or [])}
        by_user = {p["user_id"]: p for p in out.values() if p["user_id"]}
        ents = er.async_get(self.hass)
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
                                          "home": bool(st and st.state == "home"), "phones": [], "_trackers": set()}
                by_user[uid] = p
            if svc not in p["phones"]:
                p["phones"].append(svc)
        return sorted(({k: v for k, v in p.items() if k != "_trackers"} for p in out.values()), key=lambda p: p["name"].lower())

    def person_of(self, user_id: str | None) -> dict[str, Any] | None:
        return next((p for p in self.people() if user_id and p["user_id"] == user_id), None)

    def sender_of(self, user_id: str | None, user_name: str | None = None) -> str:
        p = self.person_of(user_id)
        return p["id"] if p else f"user:{user_id or 'unknown'}:{user_name or ''}"

    # ---------- messages ----------
    async def post(self, sender: str, text: str = "", *, image: str | None = None, audio: str | None = None,
                   kind: str = "chat", take: bool = False, to: str | list[str] = "all", urgent: bool = False,
                   title: str | None = None, push: bool = True) -> dict[str, Any]:
        msg = {"id": uuid.uuid4().hex[:12], "t": time.time(), "from": sender, "name": self._name(sender), "text": str(text or "")[:4000], "kind": kind,
               "image": image, "audio": audio, "take": bool(take), "taken": None, "to": to, "urgent": bool(urgent), "title": title}
        self.msgs.append(msg)
        if len(self.msgs) > MAX_MESSAGES:
            gone, self.msgs = self.msgs[:-MAX_MESSAGES], self.msgs[-MAX_MESSAGES:]
            await self.hass.async_add_executor_job(self._remove_media, gone)
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "message", msg)
        if push:
            await self._deliver(msg)
        return msg

    def _remove_media(self, gone: list[dict[str, Any]]) -> None:
        for m in gone:
            for name in (m.get("image"), m.get("audio")):
                if name and MEDIA_NAME.match(name):
                    (self.media_dir / name).unlink(missing_ok=True)

    def find(self, msg_id: str) -> dict[str, Any] | None:
        return next((m for m in reversed(self.msgs) if m["id"] == msg_id), None)

    async def take(self, msg_id: str, sender: str) -> dict[str, Any] | None:
        m = self.find(msg_id)
        if not m or m.get("taken"):
            return m
        m["taken"] = {"by": sender, "name": self._name(sender), "t": time.time()}
        if cancel := self._timers.pop(msg_id, None):
            cancel()
        self._save()
        async_dispatcher_send(self.hass, SIGNAL, "update", m)
        for p in self.people():  # gone from everyone's phone
            for svc in p["phones"]:
                await self._notify(svc, {"message": "clear_notification", "data": {"tag": f"huschat-{msg_id}"}})
        return m

    def mark_read(self, user_id: str, t: float) -> None:
        if t > self.read.get(user_id, 0):
            self.read[user_id] = t
            self._save()

    def unread(self, user_id: str) -> int:
        me = self.sender_of(user_id)
        last = self.read.get(user_id, 0)
        return sum(1 for m in self.msgs if m["t"] > last and m["from"] != me)

    def set_prefs(self, user_id: str, prefs: dict[str, Any]) -> dict[str, Any]:
        cur = {"quiet": False, "quiet_from": "22:00", "quiet_to": "07:00", "push": True, "bubble": True, **self.prefs.get(user_id, {})}
        cur.update({k: v for k, v in prefs.items() if k in cur})
        self.prefs[user_id] = cur
        self._save()
        return cur

    def get_prefs(self, user_id: str) -> dict[str, Any]:
        return {"quiet": False, "quiet_from": "22:00", "quiet_to": "07:00", "push": True, "bubble": True, **self.prefs.get(user_id, {})}

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
        people = [p for p in self.people() if p["phones"] and p["id"] != msg["from"]]
        to = msg.get("to") or "all"
        if isinstance(to, list):
            people = [p for p in people if p["id"] in to]
        elif to == "home" and not everyone:
            home = [p for p in people if p["home"]]
            people = home or people  # nobody home: everyone
        return [p for p in people if (msg.get("urgent") or not self._quiet(p["user_id"]))
                and self.prefs.get(p["user_id"] or "", {}).get("push", True) is not False]

    def _name(self, sender: str) -> str:
        if sender == HOUSE:
            return _t(self.hass)["house"]
        if sender.startswith("person."):
            st = self.hass.states.get(sender)
            return (st and st.attributes.get("friendly_name")) or sender.split(".")[1]
        if sender.startswith("user."):
            return self.users.get(sender[5:], "?")
        return sender.split(":")[2] or "?" if sender.count(":") >= 2 else "?"

    def _push_data(self, msg: dict[str, Any], extra: str = "") -> dict[str, Any]:
        t = _t(self.hass)
        body = (extra + "\n" if extra else "") + (msg["text"] or (t["image"] if msg.get("image") else t["audio"] if msg.get("audio") else ""))
        title = msg.get("title") or (f"{self._name(msg['from'])}" if msg["kind"] == "chat" else f"🏠 {t['house']}")
        actions = []
        if msg.get("take") and not msg.get("taken"):
            actions.append({"action": f"HUSCHAT_TAKE_{msg['id']}", "title": t["take"]})
        actions.append({"action": "REPLY", "title": t["reply"], "behavior": "textInput"})
        data: dict[str, Any] = {"tag": f"huschat-{msg['id']}", "group": "hus-chat", "url": "/hus-chat", "clickAction": "/hus-chat",
                                "actions": actions, "channel": "Hus-chat urgent" if msg.get("urgent") else "Hus-chat"}
        if msg.get("image"):
            data["image"] = f"/api/hus_chat/media/{msg['image']}"
        if msg.get("urgent"):
            data.update({"priority": "high", "ttl": 0, "push": {"interruption-level": "time-sensitive"}})
        return {"title": title, "message": body, "data": data}

    async def _notify(self, svc: str, payload: dict[str, Any]) -> None:
        try:
            await self.hass.services.async_call("notify", svc, payload, blocking=False)
        except Exception:  # noqa: BLE001 - one phone failing doesn't stop the others
            _LOGGER.debug("Push to %s failed", svc, exc_info=True)

    async def _deliver(self, msg: dict[str, Any]) -> None:
        sent = set()
        for p in self._recipients(msg):
            for svc in p["phones"]:
                await self._notify(svc, self._push_data(msg))
            sent.add(p["id"])
        if msg["kind"] == "house" and msg.get("take") and msg.get("to") == "home":
            @callback
            def _escalate(_now: Any) -> None:
                self._timers.pop(msg["id"], None)
                if not msg.get("taken"):
                    self.hass.async_create_task(self._escalate(msg, sent))

            self._timers[msg["id"]] = async_call_later(self.hass, ESCALATE_S, _escalate)

    async def _escalate(self, msg: dict[str, Any], sent: set[str]) -> None:
        for p in self._recipients(msg, everyone=True):
            if p["id"] in sent:
                continue
            for svc in p["phones"]:
                await self._notify(svc, self._push_data(msg, _t(self.hass)["nobody"]))

    # ---------- answers from the phone's notification ----------
    async def on_action(self, event: Event) -> None:
        action = str(event.data.get("action") or "")
        user = event.context.user_id
        if action.startswith("HUSCHAT_TAKE_"):
            await self.take(action.removeprefix("HUSCHAT_TAKE_"), self.sender_of(user))
        elif action in ("REPLY", "HUSCHAT_REPLY") and (text := str(event.data.get("reply_text") or "").strip()):
            tag = str(event.data.get("tag") or "")
            if tag and not tag.startswith("huschat-"):
                return  # another integration's reply
            await self.post(self.sender_of(user), text)

    # ---------- the house answers (Assist) ----------
    async def ask_house(self, user_id: str | None, text: str) -> dict[str, Any]:
        from homeassistant.components import conversation

        try:
            res = await conversation.async_converse(self.hass, text, self.conversations.get(user_id or ""), Context(user_id=user_id),
                                                    language=self.hass.config.language)
            if res.conversation_id:
                self.conversations[user_id or ""] = res.conversation_id
            answer = ((res.response.speech or {}).get("plain") or {}).get("speech") or "✓"
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Assist did not answer", exc_info=True)
            answer = "🤷"
        return await self.post(HOUSE, answer, kind="assist", push=False)

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

    def summary(self) -> dict[str, Any]:
        people = self.people()
        return {"people": len(people), "with_phone": sum(1 for p in people if p["phones"]), "messages": len(self.msgs),
                "house_messages": sum(1 for m in self.msgs if m["kind"] == "house")}
