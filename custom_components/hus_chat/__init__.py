"""House Chat (Hus-chat): the family's chat in Home Assistant - and the house writes along.

A chat bubble on every page of Home Assistant (like Messenger), answers from the phone's notification, "I'll take it",
messages only to those at home, quiet hours, pictures and voice messages, and the house answers through Assist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from . import websocket
from .chat import Chat
from .const import DEFAULT_TITLE, DOMAIN, HOUSE, PANEL, STATIC, TITLES
from .http import MediaView, UploadView

type HusChatConfigEntry = ConfigEntry[Chat]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.NOTIFY]

SEND_SCHEMA = vol.Schema({
    vol.Required("message"): cv.string,
    vol.Optional("title"): cv.string,
    vol.Optional("to", default="home"): vol.Any(vol.In(["home", "all", "dinner"]), cv.entity_ids),
    vol.Optional("take", default=False): cv.boolean,
    vol.Optional("urgent", default=False): cv.boolean,
    vol.Optional("camera"): cv.entity_id,
})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    websocket.async_setup(hass)
    hass.http.register_view(UploadView(hass))
    hass.http.register_view(MediaView(hass))
    from .app import AppApiView, AppIconView, AppPageView

    hass.http.register_view(AppPageView(hass))  # the chat as an app from a secret link (no login)
    hass.http.register_view(AppIconView())
    hass.http.register_view(AppApiView(hass))
    # Files under a new address for every change (newest file time), so a browser never mixes old and new files.
    folder = Path(__file__).parent / "frontend"
    stamp = await hass.async_add_executor_job(lambda: int(max(p.stat().st_mtime for p in folder.glob("*.js"))))
    hass.data[f"{DOMAIN}_static"] = base = f"{STATIC}/{stamp}"
    await hass.http.async_register_static_paths([StaticPathConfig(base, str(folder), cache_headers=False)])
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HusChatConfigEntry) -> bool:
    chat = Chat(hass)
    await chat.async_load()
    entry.runtime_data = chat
    entry.async_on_unload(chat.stop)
    entry.async_on_unload(hass.bus.async_listen("mobile_app_notification_action", chat.on_action))
    from .watch import Watch

    watch = Watch(hass, chat)  # what the house writes by itself
    watch.start()
    entry.async_on_unload(watch.stop)
    from . import voice

    if unregister := voice.setup(hass, chat):  # the house's own questions by voice, before the AI
        entry.async_on_unload(unregister)

    async def send(call: ServiceCall) -> ServiceResponse:
        image = None
        if cam := call.data.get("camera"):
            try:
                from homeassistant.components import camera

                img = await camera.async_get_image(hass, cam)
                image = await hass.async_add_executor_job(chat.save_media, img.content, "jpg")
            except Exception:  # noqa: BLE001 - the message goes without the picture
                image = None
        to = call.data["to"]
        if to == "dinner":  # those who said yes in today's dinner poll - without a poll or a yes: those at home
            to = chat.dinner_people() or "home"
        m = await chat.post(HOUSE, call.data["message"], kind="house", title=call.data.get("title"), to=to,
                            take=call.data["take"], urgent=call.data["urgent"], image=image)
        return {"id": m["id"]}

    hass.services.async_register(DOMAIN, "send", send, schema=SEND_SCHEMA, supports_response=SupportsResponse.OPTIONAL)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    version = (await async_get_integration(hass, DOMAIN)).version
    js = Path(__file__).parent / "frontend" / "hus-chat.js"
    version = f"{version}-{int(await hass.async_add_executor_job(lambda: js.stat().st_mtime))}"
    url = f"{hass.data[f'{DOMAIN}_static']}/hus-chat.js?v={version}"
    hass.data[f"{DOMAIN}_js"] = url
    frontend.add_extra_js_url(hass, url)  # the chat bubble on every page
    entry.async_on_unload(lambda: frontend.remove_extra_js_url(hass, url))
    await panel_custom.async_register_panel(
        hass, frontend_url_path=PANEL, webcomponent_name="hus-chat-panel",
        sidebar_title=TITLES.get(hass.config.language.split("-")[0], DEFAULT_TITLE), sidebar_icon="mdi:forum",
        module_url=url, require_admin=False,
    )

    from .support import Support

    support = Support(hass, DOMAIN, "hus-chat", TITLES.get(hass.config.language.split("-")[0], DEFAULT_TITLE), summary=chat.summary)
    support.setup = lambda: chat.setup_info(support)  # how it is set up, for the developer (names cleaned)
    await support.async_setup()
    entry.async_on_unload(support.unload)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HusChatConfigEntry) -> bool:
    frontend.async_remove_panel(hass, PANEL)
    hass.services.async_remove(DOMAIN, "send")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
