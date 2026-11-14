"""Pictures and voice messages: uploaded by the chat (signed in), fetched by their long random name."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .chat import MEDIA_NAME, Chat
from .const import DOMAIN

MAX_UPLOAD = 15 * 1024 * 1024
TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif", "audio/webm": "webm",
         "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/aac": "aac", "audio/mpeg": "mp3", "video/mp4": "m4a",
         "video/webm": "webm"}


def _chat(hass: HomeAssistant) -> Chat | None:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    return entries[0].runtime_data if entries else None


class UploadView(HomeAssistantView):
    url = "/api/hus_chat/upload"
    name = "api:hus_chat:upload"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        chat = _chat(self.hass)
        if not chat:
            return self.json_message("Not set up", HTTPStatus.SERVICE_UNAVAILABLE)
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


class MediaView(HomeAssistantView):
    url = "/api/hus_chat/media/{name}"
    name = "api:hus_chat:media"
    requires_auth = False  # the phone's notification fetches the picture; the name is 128 random bits

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request: web.Request, name: str) -> web.StreamResponse:
        chat = _chat(self.hass)
        if not chat or not MEDIA_NAME.match(name):
            return web.Response(status=HTTPStatus.NOT_FOUND)
        path = chat.media_dir / name
        if not path.is_file():
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable"})
