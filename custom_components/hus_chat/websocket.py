"""The chat's websocket: open (and follow), send, take, read, settings."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .chat import MEDIA_NAME, Chat
from .const import DOMAIN, SHOWN, SIGNAL


def async_setup(hass: HomeAssistant) -> None:
    for cmd in (ws_subscribe, ws_send, ws_take, ws_read, ws_prefs, ws_rules, ws_agent, ws_delete, ws_clear, ws_edit, ws_react,
                ws_presence, ws_links, ws_extra, ws_speak):
        websocket_api.async_register_command(hass, cmd)


def _chat(hass: HomeAssistant) -> Chat | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


def _me(chat: Chat, connection: websocket_api.ActiveConnection) -> dict[str, Any]:
    u = connection.user
    return {"user_id": u.id, "id": chat.sender_of(u.id, u.name), "name": u.name, "admin": u.is_admin}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@websocket_api.async_response
async def ws_subscribe(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    uid, admin = connection.user.id, connection.user.is_admin
    await chat.async_refresh_users()

    @callback
    def forward(kind: str, m: dict[str, Any]) -> None:
        # Only what this person may see: a message to others never reaches their screen.
        if kind in ("message", "update") and not (chat.member(uid, admin) and chat.can_see(m, uid)):
            return
        connection.send_message(websocket_api.event_message(msg["id"], {"type": kind, "message": m, "unread": chat.unread(uid, admin)}))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL, forward)
    connection.send_result(msg["id"])
    connection.send_message(websocket_api.event_message(msg["id"], {
        "type": "init", "messages": chat.visible(uid, admin)[-SHOWN:], "people": chat.people(), "me": _me(chat, connection),
        "member": chat.member(uid, admin), "reads": chat.reads(),
        "unread": chat.unread(uid, admin), "read": chat.read.get(uid, 0), "prefs": chat.get_prefs(uid), "phones": chat.phones_of.get(uid, []),
        "rules": chat.get_rules(), "agents": chat.agents(), "pinned": chat.pinned,
        "speak": chat.speak_info() if admin else None}))


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/send",
    vol.Optional("text", default=""): vol.All(str, vol.Length(max=4000)),
    vol.Optional("media"): {vol.Required("name"): str, vol.Required("kind"): vol.In(["image", "audio"])},
    vol.Optional("to_house", default=False): bool,
    vol.Optional("cid"): vol.All(str, vol.Length(max=40)),  # the same id when sent again after a lost connection
    vol.Optional("reply"): str,
})
@websocket_api.async_response
async def ws_send(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    text, media = msg["text"].strip(), msg.get("media")
    if media and not MEDIA_NAME.match(media["name"]):
        connection.send_error(msg["id"], "bad_media", "Unknown picture or voice message")
        return
    if not text and not media:
        connection.send_error(msg["id"], "empty", "Nothing to send")
        return
    if not chat.member(connection.user.id, connection.user.is_admin):
        connection.send_error(msg["id"], "unauthorized", "Not in the family chat")
        return
    me = chat.sender_of(connection.user.id, connection.user.name)
    m = await chat.post(me, text, image=media["name"] if media and media["kind"] == "image" else None,
                        audio=media["name"] if media and media["kind"] == "audio" else None,
                        kind="to_house" if msg["to_house"] else "chat", push=not msg["to_house"],
                        to=[me] if msg["to_house"] else "all", cid=msg.get("cid"), reply=msg.get("reply"))
    chat.mark_read(connection.user.id, m["t"])
    connection.send_result(msg["id"], {"id": m["id"]})
    if msg["to_house"] and text:
        # On its own, not tied to this connection: a phone that sleeps or loses the network still gets the answer.
        hass.async_create_background_task(chat.ask_house(connection.user.id, text), f"{DOMAIN} ask the house")


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/take", vol.Required("message"): str})
@websocket_api.async_response
async def ws_take(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    if chat:
        await chat.take(msg["message"], chat.sender_of(connection.user.id, connection.user.name))
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/read", vol.Required("t"): vol.Coerce(float)})
@callback
def ws_read(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    if chat:
        chat.mark_read(connection.user.id, msg["t"])
    connection.send_result(msg["id"], {"unread": chat.unread(connection.user.id, connection.user.is_admin) if chat else 0})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/prefs",
    vol.Optional("quiet"): bool,
    vol.Optional("quiet_from"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("quiet_to"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("push"): bool,
    vol.Optional("bubble"): bool,
    vol.Optional("phones_off"): [str],
    vol.Optional("muted"): [str],
})
@callback
def ws_prefs(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    prefs = chat.set_prefs(connection.user.id, {k: v for k, v in msg.items() if k not in ("id", "type")})
    chat.people()  # "My phones" again
    connection.send_result(msg["id"], {**prefs, "phones": chat.phones_of.get(connection.user.id, [])})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/rules",
    vol.Optional("rules"): {str: {vol.Optional("on"): bool, vol.Optional("to"): vol.Any(vol.In(["home", "all"]), [str])}},
})
@callback
def ws_rules(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """What the house writes by itself, and to whom - everyone can see it, only admins change it."""
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    if msg.get("rules"):
        if not connection.user.is_admin:
            connection.send_error(msg["id"], "unauthorized", "Only admins choose this for the family")
            return
        connection.send_result(msg["id"], chat.set_rules(msg["rules"]))
        return
    connection.send_result(msg["id"], chat.get_rules())


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/agent", vol.Optional("agent"): vol.Any(None, str)})
@callback
def ws_agent(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Who answers for the house: any AI set up in Home Assistant - everyone can see it, only admins change it."""
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    if "agent" in msg:
        if not connection.user.is_admin:
            connection.send_error(msg["id"], "unauthorized", "Only admins choose this for the family")
            return
        agent = msg["agent"]
        if agent and not agent.startswith("conversation."):
            connection.send_error(msg["id"], "invalid", "Not an AI")
            return
        connection.send_result(msg["id"], chat.set_agent(agent))
        return
    connection.send_result(msg["id"], chat.agents())


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/delete", vol.Required("message"): str})
@websocket_api.async_response
async def ws_delete(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Your own message - or any, for an admin."""
    chat = _chat(hass)
    ok = bool(chat) and await chat.delete(msg["message"], connection.user.id, connection.user.is_admin)
    connection.send_result(msg["id"], {"deleted": ok})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/clear"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_clear(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """An admin empties the whole chat."""
    if chat := _chat(hass):
        await chat.clear_all()
    connection.send_result(msg["id"])


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/edit", vol.Required("message"): str,
                                  vol.Required("text"): vol.All(str, vol.Length(min=1, max=4000))})
@callback
def ws_edit(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    connection.send_result(msg["id"], {"edited": bool(chat) and chat.edit(msg["message"], connection.user.id, msg["text"])})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/react", vol.Required("message"): str,
                                  vol.Required("emoji"): vol.In(["👍", "❤️", "😂", "😮", "😢", "🙏"])})
@callback
def ws_react(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    connection.send_result(msg["id"], {"ok": bool(chat) and chat.react(msg["message"], connection.user.id, msg["emoji"])})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/presence", vol.Required("open"): bool})
@callback
def ws_presence(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """The chat is open and in front (or not): no phone notification while you're looking at it."""
    if chat := _chat(hass):
        chat.set_active(connection.user.id, msg["open"])
    connection.send_result(msg["id"])


def _app_url(hass: HomeAssistant) -> tuple[str, bool]:
    """Where a link opens: Nabu Casa (or your own outside address) first, so it works away from home too."""
    from homeassistant.helpers.network import NoURLAvailableError, get_url

    try:
        return get_url(hass, allow_internal=False, allow_ip=False, prefer_cloud=True), True
    except NoURLAvailableError:
        try:
            return get_url(hass, prefer_external=False), False
        except NoURLAvailableError:
            return "", False


def _links(hass: HomeAssistant, chat: Chat) -> dict[str, Any]:
    base, outside = _app_url(hass)
    from .app import PAGE

    return {"outside": outside, "links": [{"id": lid, "name": x.get("name"), "person": x.get("person"), "created": x.get("created"),
                                           "devices": len(x.get("subs") or []), "url": f"{base}{PAGE}/{x['token']}/"}
                                          for lid, x in sorted(chat.links.items(), key=lambda kv: kv[1].get("created", 0))]}


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/links",
    vol.Optional("create"): {vol.Required("name"): vol.All(str, vol.Length(min=1, max=40)), vol.Optional("person"): vol.Any(None, str)},
    vol.Optional("delete"): str,
})
@websocket_api.require_admin
@callback
def ws_links(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """The chat as an app from a link: made and removed by an admin - for children and others without an account."""
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    if c := msg.get("create"):
        person = c.get("person")
        if person and not (person.startswith("person.") and hass.states.get(person)):
            connection.send_error(msg["id"], "invalid", "Unknown person")
            return
        chat.add_link(c["name"], person)
    if lid := msg.get("delete"):
        chat.remove_link(lid)
        from homeassistant.helpers.dispatcher import async_dispatcher_send

        async_dispatcher_send(hass, SIGNAL, "links", {})  # an open app from that link stops at once
    connection.send_result(msg["id"], _links(hass, chat))


async def extra(chat: Chat, uid: str, me: str, msg: dict[str, Any]) -> Any:
    """The little extras - the same for Home Assistant's websocket and the app from a link: the shopping list, a poll,
    a vote, pin a message, and "on my way home"."""
    what = msg.get("what")
    if what == "shop":
        return await chat.shop_list(add=msg.get("add") if isinstance(msg.get("add"), str) else None,
                                    done=msg.get("done") if isinstance(msg.get("done"), str) else None)
    if what == "poll":
        q, opts = str(msg.get("question") or "").strip()[:200], [str(o).strip()[:80] for o in (msg.get("options") or []) if str(o).strip()]
        if not q or len(opts) < 2:
            return {"error": "invalid"}
        m = await chat.post(me, q, poll=opts[:6])
        return {"id": m["id"]}
    if what == "vote" and isinstance(msg.get("message"), str):
        try:
            return {"ok": chat.vote(msg["message"], uid, int(msg.get("option")))}
        except (TypeError, ValueError):
            return {"ok": False}
    if what == "pin":
        return {"ok": chat.pin(msg.get("message") if isinstance(msg.get("message"), str) else None)}
    if what == "onway":
        m = await chat.on_my_way(me)
        return {"id": m["id"]}
    return {"error": "unsupported"}


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/extra", vol.Required("what"): vol.In(["shop", "poll", "vote", "pin", "onway"]),
                                  vol.Optional("add"): str, vol.Optional("done"): str, vol.Optional("question"): str,
                                  vol.Optional("options"): [str], vol.Optional("message"): vol.Any(None, str), vol.Optional("option"): int})
@websocket_api.async_response
async def ws_extra(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    chat = _chat(hass)
    if not chat or not chat.member(connection.user.id, connection.user.is_admin):
        connection.send_error(msg["id"], "unauthorized", "Not in the family chat")
        return
    try:
        res = await extra(chat, connection.user.id, chat.sender_of(connection.user.id, connection.user.name), msg)
    except Exception as err:  # noqa: BLE001 - e.g. a to-do list that refuses
        connection.send_error(msg["id"], "failed", str(err))
        return
    connection.send_result(msg["id"], res)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/speak", vol.Optional("on"): bool, vol.Optional("player"): vol.Any(None, str),
                                  vol.Optional("test"): bool})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_speak(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """The house's messages read aloud on a speaker - chosen by an admin."""
    chat = _chat(hass)
    if not chat:
        connection.send_error(msg["id"], "not_loaded", "House Chat is not set up")
        return
    if "player" in msg and msg["player"] and not msg["player"].startswith("media_player."):
        connection.send_error(msg["id"], "invalid", "Not a speaker")
        return
    info = chat.set_speak(msg.get("on"), msg.get("player") if "player" in msg else None) if ("on" in msg or "player" in msg) else chat.speak_info()
    if msg.get("test"):
        from .const import DEFAULT_TITLE, TITLES

        await chat.say(TITLES.get((hass.config.language or "en").split("-")[0], DEFAULT_TITLE))
    connection.send_result(msg["id"], info)
