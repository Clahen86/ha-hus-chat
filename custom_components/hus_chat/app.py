"""The chat as an app from a secret link - for children and others without a Home Assistant account.

The link opens the same chat as in Home Assistant (hus-chat.js), on a page of its own that can be installed as an
app on the home screen. It talks to these views instead of Home Assistant's websocket; the link is the key, and it
only opens the chat - nothing else in Home Assistant. Through Nabu Casa it works at home and away.
"""

from __future__ import annotations

import asyncio
import json
import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .chat import MEDIA_NAME, Chat
from .const import DOMAIN, SHOWN, SIGNAL, TITLES, DEFAULT_TITLE
from .http import MAX_UPLOAD, TYPES

_LOGGER = logging.getLogger(__name__)
PAGE = "/hus_chat_app"
API = "/api/hus_chat/app"
REACTIONS = ("👍", "❤️", "😂", "😮", "😢", "🙏")


def _chat(hass: HomeAssistant) -> Chat | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _who(hass: HomeAssistant, token: str) -> tuple[Chat, str, str] | None:
    """The chat, the link's user id ("link:<id>") and the sender it writes as - or None for an unknown link."""
    chat = _chat(hass)
    lid = chat.link_by_token(token) if chat else None
    if not lid:
        return None
    uid = f"link:{lid}"
    return chat, uid, chat.sender_of(uid)


def _title(hass: HomeAssistant) -> str:
    return TITLES.get((hass.config.language or "en").split("-")[0], DEFAULT_TITLE)


def init_payload(chat: Chat, uid: str) -> dict[str, Any]:
    me = chat.sender_of(uid)
    lid = uid[5:]
    return {"type": "init", "messages": chat.visible(uid)[-SHOWN:], "people": chat.people(),
            "me": {"user_id": uid, "id": me, "name": chat._name(me), "admin": False, "app": True},
            "member": True, "reads": chat.reads(), "unread": chat.unread(uid), "read": chat.read.get(uid, 0),
            "prefs": chat.get_prefs(uid), "phones": [], "rules": chat.get_rules(), "agents": None,
            "push_key": chat.vapid.public if chat.vapid else None, "pinned": chat.pinned, "subs": len(chat.links.get(lid, {}).get("subs") or [])}


class AppPageView(HomeAssistantView):
    """The page itself, its manifest (to install it as an app) and its service worker (push when it's closed)."""

    url = PAGE + "/{token}/{file:.*}"
    extra_urls = [PAGE + "/{token}"]
    name = "hus_chat:app"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, token: str, file: str = "") -> web.StreamResponse:
        who = _who(self.hass, token)
        if not who:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="This link is no longer in use.")
        chat, uid, me = who
        base = f"{PAGE}/{token}"
        if file == "manifest.webmanifest":
            name = f"{_title(self.hass)} · {chat._name(me)}"
            return web.json_response({
                "name": name, "short_name": _title(self.hass), "start_url": f"{base}/", "scope": f"{base}/", "id": f"{base}/",
                "display": "standalone", "background_color": "#f4f2fb", "theme_color": "#7c5cff",
                "icons": [{"src": f"{PAGE}-icon/192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                          {"src": f"{PAGE}-icon/512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"}]},
                content_type="application/manifest+json")
        if file == "sw.js":
            return web.Response(text=SW, content_type="application/javascript", headers={"Service-Worker-Allowed": f"{base}/", "Cache-Control": "no-cache"})
        if file not in ("", "index.html"):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        js = f"{self.hass.data[f'{DOMAIN}_static']}/hus-chat.js"
        lang = (self.hass.config.language or "en").split("-")[0]
        html = PAGE_HTML.replace("{{title}}", _title(self.hass)).replace("{{base}}", base).replace("{{js}}", js) \
            .replace("{{lang}}", lang).replace("{{api}}", f"{API}/{token}")
        return web.Response(text=html, content_type="text/html", headers={"Cache-Control": "no-cache", "Referrer-Policy": "no-referrer"})


class AppIconView(HomeAssistantView):
    url = PAGE + "-icon/{size}.png"
    name = "hus_chat:app_icon"
    requires_auth = False

    async def get(self, request: web.Request, size: str) -> web.StreamResponse:
        icon = Path(__file__).parent / "brand" / ("icon@2x.png" if size == "512" else "icon.png")
        return web.FileResponse(icon, headers={"Cache-Control": "public, max-age=86400"})


class AppApiView(HomeAssistantView):
    """What the chat asks for, as over Home Assistant's websocket - as the link's own person."""

    url = API + "/{token}/{action}"
    name = "api:hus_chat:app"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, token: str, action: str) -> web.StreamResponse:
        who = _who(self.hass, token)
        if not who or action != "events":
            return web.Response(status=HTTPStatus.NOT_FOUND)
        chat, uid, _me = who
        # Live: everything the chat sends, as server-sent events (EventSource reconnects by itself).
        resp = web.StreamResponse(headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
        await resp.prepare(request)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)

        @callback
        def forward(kind: str, m: dict[str, Any]) -> None:
            if kind in ("message", "update") and not chat.can_see(m, uid):
                return
            if uid[5:] not in chat.links:  # the link was deleted: the app stops
                queue.put_nowait({"type": "gone"})
                return
            try:
                queue.put_nowait({"type": kind, "message": m, "unread": chat.unread(uid)})
            except asyncio.QueueFull:
                pass

        unsub = async_dispatcher_connect(self.hass, SIGNAL, forward)
        try:
            await chat.async_refresh_users()
            await resp.write(f"data: {json.dumps(init_payload(chat, uid))}\n\n".encode())
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), 25)
                except TimeoutError:
                    await resp.write(b": ping\n\n")  # keeps proxies (and Nabu Casa) from closing it
                    continue
                await resp.write(f"data: {json.dumps(ev)}\n\n".encode())
                if ev["type"] == "gone":
                    break
        except (ConnectionResetError, asyncio.CancelledError, RuntimeError):
            pass
        finally:
            unsub()
        return resp

    async def post(self, request: web.Request, token: str, action: str) -> web.Response:
        who = _who(self.hass, token)
        if not who:
            return self.json_message("This link is no longer in use", HTTPStatus.NOT_FOUND)
        chat, uid, me = who
        if action == "upload":
            return await self._upload(request, chat)
        try:
            msg = await request.json()
        except ValueError:
            return self.json_message("Bad request", HTTPStatus.BAD_REQUEST)
        if action == "push":  # this browser wants messages when the app is closed
            sub = msg.get("subscription") or {}
            if not (isinstance(sub.get("endpoint"), str) and sub["endpoint"].startswith("https://") and isinstance(sub.get("keys"), dict)
                    and sub["keys"].get("p256dh") and sub["keys"].get("auth")):
                return self.json_message("Bad subscription", HTTPStatus.BAD_REQUEST)
            chat.add_sub(uid[5:], sub)
            return self.json({"ok": True})
        if action != "ws":
            return self.json_message("Unknown", HTTPStatus.NOT_FOUND)
        return self.json(await self._handle(chat, uid, me, msg))

    async def _upload(self, request: web.Request, chat: Chat) -> web.Response:
        if (request.content_length or 0) > MAX_UPLOAD:
            return self.json_message("Too big", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        reader = await request.multipart()
        field = await reader.next()
        if field is None or field.name != "file":
            return self.json_message("No file", HTTPStatus.BAD_REQUEST)
        ctype = (field.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = TYPES.get(ctype)
        if not ext:
            return self.json_message("Not a picture or a voice message", HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        data = bytearray()
        while chunk := await field.read_chunk(256 * 1024):
            data.extend(chunk)
            if len(data) > MAX_UPLOAD:
                return self.json_message("Too big", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        name = await self.hass.async_add_executor_job(chat.save_media, bytes(data), ext)
        kind = "image" if ctype.startswith("image/") else "audio"
        if kind == "audio":
            name = await self.hass.async_add_executor_job(chat.to_m4a, name)
        return self.json({"name": name, "kind": kind})

    async def _handle(self, chat: Chat, uid: str, me: str, msg: dict[str, Any]) -> Any:
        """The same commands as websocket.py - without the admin ones, and without asking the house (a link that
        got out must never be able to unlock a door)."""
        kind = str(msg.get("type") or "").removeprefix(f"{DOMAIN}/")
        if kind == "send":
            text, media = str(msg.get("text") or "").strip()[:4000], msg.get("media")
            if media and not (isinstance(media, dict) and MEDIA_NAME.match(str(media.get("name"))) and media.get("kind") in ("image", "audio")):
                return {"error": "bad_media"}
            if not text and not media:
                return {"error": "empty"}
            m = await chat.post(me, text, image=media["name"] if media and media["kind"] == "image" else None,
                                audio=media["name"] if media and media["kind"] == "audio" else None,
                                cid=str(msg.get("cid") or "")[:40] or None, reply=msg.get("reply") if isinstance(msg.get("reply"), str) else None)
            chat.mark_read(uid, m["t"])
            return {"id": m["id"]}
        if kind == "take" and isinstance(msg.get("message"), str):
            await chat.take(msg["message"], me)
            return None
        if kind == "read":
            try:
                chat.mark_read(uid, float(msg.get("t")))
            except (TypeError, ValueError):
                pass
            return {"unread": chat.unread(uid)}
        if kind == "prefs":
            ok = {k: v for k, v in msg.items() if k in ("quiet", "quiet_from", "quiet_to", "push") and isinstance(v, (bool, str))}
            return {**chat.set_prefs(uid, ok), "phones": []}
        if kind == "rules":
            return chat.get_rules()
        if kind == "delete" and isinstance(msg.get("message"), str):
            return {"deleted": await chat.delete(msg["message"], uid, False)}
        if kind == "edit" and isinstance(msg.get("message"), str) and str(msg.get("text") or "").strip():
            return {"edited": chat.edit(msg["message"], uid, str(msg["text"])[:4000])}
        if kind == "react" and isinstance(msg.get("message"), str) and msg.get("emoji") in REACTIONS:
            return {"ok": chat.react(msg["message"], uid, msg["emoji"])}
        if kind == "extra":
            from .websocket import extra

            try:
                return await extra(chat, uid, me, msg)
            except Exception:  # noqa: BLE001
                return {"error": "failed"}
        if kind == "presence":
            chat.set_active(uid, bool(msg.get("open")))
            return None
        return {"error": "unsupported"}


SW = """// Hus-chat app: shows a message when the app is closed, opens the chat when it is tapped.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data.json(); } catch (x) { d = { title: "Hus-chat", body: e.data ? e.data.text() : "" }; }
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    if (list.some((c) => c.visibilityState === "visible") && !d.urgent) return;  // looking at the chat: no notification
    return self.registration.showNotification(d.title || "Hus-chat", { body: d.body || "", tag: d.tag, renotify: true,
      icon: "/hus_chat_app-icon/192.png", badge: "/hus_chat_app-icon/192.png", image: d.image || undefined,
      requireInteraction: !!d.urgent, data: { url: d.url } });
  }));
});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || self.registration.scope;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    for (const c of list) if (c.url.startsWith(self.registration.scope) && "focus" in c) return c.focus();
    return self.clients.openWindow(url + "/");
  }));
});
"""

PAGE_HTML = """<!doctype html>
<html lang="{{lang}}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,interactive-widget=resizes-content">
<title>{{title}}</title>
<link rel="manifest" href="{{base}}/manifest.webmanifest">
<link rel="icon" href="/hus_chat_app-icon/192.png"><link rel="apple-touch-icon" href="/hus_chat_app-icon/192.png">
<meta name="theme-color" content="#7c5cff"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{{title}}"><meta name="apple-mobile-web-app-status-bar-style" content="default">
<style>
html,body{margin:0;height:100%;background:#f4f2fb;font-family:-apple-system,"Inter",Roboto,sans-serif}
@media (prefers-color-scheme: dark){html,body{background:#12121a}}
body{display:flex;flex-direction:column;height:100vh;height:100dvh}
hus-chat-view{flex:1;min-height:0}
#tip{display:none;align-items:center;gap:10px;padding:10px 14px;padding-top:calc(10px + env(safe-area-inset-top));background:linear-gradient(135deg,#ff6b8a,#7c5cff);color:#fff;font-size:14px;line-height:1.3}
#tip span{flex:1}#tip button{border:0;border-radius:18px;padding:8px 14px;font:600 14px inherit;background:#fff;color:#5b3fd9;cursor:pointer}
#tip .x{background:transparent;color:#fff;padding:4px 6px;font-size:18px}
</style></head><body>
<div id="tip"><span></span><button class="go"></button><button class="x" aria-label="✕">✕</button></div>
<script>
// The chat talks to Home Assistant through a link instead of a login: a small stand-in for its connection.
(() => {
  const API = "{{api}}", BASE = "{{base}}";
  window.HUS_CHAT_APP = { api: API, base: BASE };
  const post = (action, body) => fetch(`${API}/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .then((r) => r.status === 404 ? (gone(), Promise.reject(new Error("gone"))) : r.json()).then((d) => d && d.error ? Promise.reject(new Error(d.error)) : d);
  const gone = () => { document.body.innerHTML = '<p style="padding:40px 24px;text-align:center;color:#888;font-size:16px">🔒 Dette link er ikke længere i brug.<br><small>This link is no longer in use.</small></p>'; };
  const conn = {
    subscribeMessage(cb, msg) {
      if (msg.type !== "hus_chat/subscribe") return Promise.reject(new Error("unsupported"));
      const es = new EventSource(`${API}/events`);
      es.onmessage = (e) => { const d = JSON.parse(e.data); if (d.type === "gone") { es.close(); gone(); return; }
        if (d.type === "init") window.HUS_CHAT_APP.init = d; cb(d); };
      return Promise.resolve(async () => es.close());
    },
    sendMessagePromise: (msg) => post("ws", msg),
    socket: null,
  };
  const dark = matchMedia("(prefers-color-scheme: dark)");
  window.HUS_CHAT_HASS = { connection: conn, language: "{{lang}}", states: {}, themes: { darkMode: dark.matches },
    fetchWithAuth: (url, opts) => fetch(url === "/api/hus_chat/upload" ? `${API}/upload` : url, opts) };
})();
</script>
<script type="module" src="{{js}}"></script>
<script type="module">
(() => {
  const A = window.HUS_CHAT_APP, da = "{{lang}}" === "da" || "{{lang}}" === "nb" || "{{lang}}" === "sv";
  const v = document.createElement("hus-chat-view");
  v.hass = window.HUS_CHAT_HASS;
  document.body.appendChild(v);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => { window.HUS_CHAT_HASS.themes = { darkMode: e.matches }; v.hass = window.HUS_CHAT_HASS; });
  // A tip on top: install it as an app, then turn on messages (both need a tap from the user)
  const tip = document.getElementById("tip"), txt = tip.querySelector("span"), go = tip.querySelector(".go");
  const standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  let later = false, prompt = null;
  try { later = localStorage.getItem("hc-tip-later") === "1"; } catch (e) { /* private */ }
  tip.querySelector(".x").onclick = () => { tip.style.display = "none"; try { localStorage.setItem("hc-tip-later", "1"); } catch (e) { /* private */ } };
  const show = (t, b, fn) => { if (later) return; txt.textContent = t; go.textContent = b; go.style.display = b ? "" : "none"; go.onclick = fn; tip.style.display = "flex"; };
  const T = da ? { install: "Læg chatten på hjemmeskærmen som en app.", iosInstall: "Tryk på Del ⬆︎ og vælg »Føj til hjemmeskærm«.", installB: "Installer",
    push: "Få besked, når nogen skriver.", pushB: "Slå til", denied: "Beskeder er slået fra i browseren." }
    : { install: "Put the chat on your home screen as an app.", iosInstall: "Tap Share ⬆︎ and choose “Add to Home Screen”.", installB: "Install",
    push: "Get a message when somebody writes.", pushB: "Turn on", denied: "Notifications are blocked in the browser." };
  const b64 = (s) => { const p = atob((s + "=".repeat((4 - s.length % 4) % 4)).replace(/-/g, "+").replace(/_/g, "/")); return Uint8Array.from(p, (c) => c.charCodeAt(0)); };
  async function subscribe(reg, key) {
    const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64(key) });
    await fetch(`${A.api}/push`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ subscription: sub.toJSON() }) });
  }
  async function pushSetup() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
    const reg = await navigator.serviceWorker.register(`${A.base}/sw.js`, { scope: `${A.base}/` });
    for (let i = 0; i < 40 && !A.init; i++) await new Promise((r) => setTimeout(r, 250));
    const key = A.init && A.init.push_key;
    if (!key) return false;
    if (Notification.permission === "granted") { await subscribe(reg, key).catch(() => {}); return true; }
    if (Notification.permission === "denied") { show(T.denied, "", null); return true; }
    show(T.push, T.pushB, async () => { tip.style.display = "none"; if (await Notification.requestPermission() === "granted") await subscribe(reg, key).catch(() => {}); });
    return true;
  }
  window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); prompt = e; if (!standalone) show(T.install, T.installB, async () => { tip.style.display = "none"; prompt.prompt(); }); });
  if (ios && !standalone) show(T.iosInstall, "", null);  // on iPhone, messages only work once it's on the home screen
  else pushSetup().catch(() => {});
})();
</script></body></html>
"""
