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
                ws_presence):
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
        "rules": chat.get_rules(), "agents": chat.agents()}))


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
