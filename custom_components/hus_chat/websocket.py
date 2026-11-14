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
    for cmd in (ws_subscribe, ws_send, ws_take, ws_read, ws_prefs):
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
    uid = connection.user.id
    await chat.async_refresh_users()

    @callback
    def forward(kind: str, m: dict[str, Any]) -> None:
        connection.send_message(websocket_api.event_message(msg["id"], {"type": kind, "message": m, "unread": chat.unread(uid)}))

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(hass, SIGNAL, forward)
    connection.send_result(msg["id"])
    connection.send_message(websocket_api.event_message(msg["id"], {
        "type": "init", "messages": chat.msgs[-SHOWN:], "people": chat.people(), "me": _me(chat, connection),
        "unread": chat.unread(uid), "read": chat.read.get(uid, 0), "prefs": chat.get_prefs(uid), "phones": chat.phones_of.get(uid, [])}))


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/send",
    vol.Optional("text", default=""): vol.All(str, vol.Length(max=4000)),
    vol.Optional("media"): {vol.Required("name"): str, vol.Required("kind"): vol.In(["image", "audio"])},
    vol.Optional("to_house", default=False): bool,
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
    me = chat.sender_of(connection.user.id, connection.user.name)
    m = await chat.post(me, text, image=media["name"] if media and media["kind"] == "image" else None,
                        audio=media["name"] if media and media["kind"] == "audio" else None,
                        kind="to_house" if msg["to_house"] else "chat", push=not msg["to_house"])
    chat.mark_read(connection.user.id, m["t"])
    connection.send_result(msg["id"], {"id": m["id"]})
    if msg["to_house"] and text:
        await chat.ask_house(connection.user.id, text)


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
    connection.send_result(msg["id"], {"unread": chat.unread(connection.user.id) if chat else 0})


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/prefs",
    vol.Optional("quiet"): bool,
    vol.Optional("quiet_from"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("quiet_to"): vol.Match(r"^\d{2}:\d{2}$"),
    vol.Optional("push"): bool,
    vol.Optional("bubble"): bool,
    vol.Optional("phones_off"): [str],
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
