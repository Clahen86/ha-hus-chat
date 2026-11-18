"""The chat as an app from a secret link: who it is, what it may do, web push, and the pages."""

import base64
import json
import os
from unittest.mock import AsyncMock, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.hus_chat import webpush
from custom_components.hus_chat.chat import GUARD_WORDS
from custom_components.hus_chat.const import HOUSE

from .test_chat import chat  # noqa: F401 - the family fixture


def _sub():
    key = ec.generate_private_key(ec.SECP256R1())
    auth = os.urandom(16)
    pub = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return key, auth, {"endpoint": "https://push.example/abc", "keys": {"p256dh": webpush.b64u(pub), "auth": webpush.b64u(auth)}}


def test_web_push_is_readable_by_the_browser_only():
    key, auth, sub = _sub()
    body = webpush.encrypt(sub, b'{"title":"Hej"}')
    salt, idlen = body[:16], body[20]
    as_pub, ct = body[21:21 + idlen], body[21 + idlen:]
    shared = key.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_pub))
    ua_pub = webpush.b64d(sub["keys"]["p256dh"])
    h = lambda s, i, info, n: HKDF(algorithm=hashes.SHA256(), length=n, salt=s, info=info).derive(i)  # noqa: E731
    ikm = h(auth, shared, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    plain = AESGCM(h(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)).decrypt(h(salt, ikm, b"Content-Encoding: nonce\x00", 12), ct, None)
    assert plain == b'{"title":"Hej"}\x02'
    v = webpush.Vapid()
    assert webpush.Vapid(v.pem).public == v.public and v.header(sub["endpoint"]).startswith("vapid t=")


async def test_a_child_without_an_account_is_in_the_chat(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, calls = chat
    link = c.add_link("Silas", None)
    lid = c.link_by_token(link["token"])
    assert lid and c.link_by_token("wrong") is None
    uid = f"link:{lid}"
    assert c.member(uid) and c.sender_of(uid) == f"link.{lid}"
    assert any(p["id"] == f"link.{lid}" and p["name"] == "Silas" for p in c.people())
    c.add_sub(lid, _sub()[2])
    with patch("custom_components.hus_chat.webpush.send", AsyncMock(return_value=True)) as send:
        await c.post("person.lilly", "Aftensmad!")
        await hass.async_block_till_done()
    assert send.await_count == 1 and send.await_args.args[3]["body"] == "Aftensmad!"
    with patch("custom_components.hus_chat.webpush.send", AsyncMock(return_value=True)) as send:
        await c.post(f"link.{lid}", "Kommer nu")  # the child's own message isn't pushed back to them
        await hass.async_block_till_done()
    assert send.await_count == 0 and len(calls["Lilly"]) == 1  # Lilly gets it on her phone


async def test_a_link_for_a_person_writes_as_that_person(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    lid = c.link_by_token(c.add_link("Wictor", "person.wictor")["token"])
    assert c.sender_of(f"link:{lid}") == "person.wictor"
    private = await c.post("person.lilly", "Kun til Claus", to=["user.u-claus"])
    assert not c.can_see(private, f"link:{lid}")
    assert c.remove_link(lid) and not c.member(f"link:{lid}")


async def test_gone_subscriptions_are_dropped(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    lid = c.link_by_token(c.add_link("Silas", None)["token"])
    c.add_sub(lid, _sub()[2])
    with patch("custom_components.hus_chat.webpush.send", AsyncMock(return_value=False)):
        await c.post(HOUSE, "Vasken er færdig", kind="house", to="all")
        await hass.async_block_till_done()
    assert c.links[lid]["subs"] == []


async def test_the_app_pages_and_api(hass: HomeAssistant, hass_client_no_auth, chat) -> None:  # noqa: F811
    c, _ = chat
    assert await async_setup_component(hass, "http", {})
    token = c.add_link("Silas", None)["token"]
    client = await hass_client_no_auth()
    r = await client.get(f"/hus_chat_app/{token}/")
    assert r.status == 200 and "hus-chat-view" in await r.text()
    assert (await client.get(f"/hus_chat_app/{token}/manifest.webmanifest")).status == 200
    assert (await client.get(f"/hus_chat_app/{token}/sw.js")).status == 200
    assert (await client.get("/hus_chat_app/nope/")).status == 404
    r = await client.post(f"/api/hus_chat/app/{token}/ws", json={"type": "hus_chat/send", "text": "Hej fra Silas"})
    assert r.status == 200 and (await r.json())["id"]
    assert c.msgs[-1]["text"] == "Hej fra Silas" and c.msgs[-1]["name"] == "Silas"
    # never the house's commands, never an admin's
    r = await client.post(f"/api/hus_chat/app/{token}/ws", json={"type": "hus_chat/send", "text": "Tænd lyset", "to_house": True})
    await hass.async_block_till_done()
    assert c.msgs[-2]["kind"] == "to_house" and c.msgs[-1]["from"] == HOUSE and "Settings" in c.msgs[-1]["text"]  # not allowed
    assert (await (await client.post(f"/api/hus_chat/app/{token}/ws", json={"type": "hus_chat/clear"})).json())["error"] == "unsupported"
    assert (await client.post("/api/hus_chat/app/nope/ws", json={"type": "hus_chat/send", "text": "x"})).status == 404
    r = await client.post(f"/api/hus_chat/app/{token}/push", json={"subscription": _sub()[2]})
    assert r.status == 200 and len(next(iter(c.links.values()))["subs"]) == 1
    # live: the first event is everything the chat needs
    async with client.get(f"/api/hus_chat/app/{token}/events") as ev:
        line = await ev.content.readline()
        init = json.loads(line.decode()[6:])
    assert init["type"] == "init" and init["me"]["name"] == "Silas" and init["push_key"]
    assert any(m["text"] == "Hej fra Silas" for m in init["messages"])


async def test_a_link_may_talk_to_the_house_when_allowed_but_never_to_locks(hass: HomeAssistant, chat, monkeypatch) -> None:  # noqa: F811
    c, _ = chat
    lid = c.link_by_token(c.add_link("Silas", None)["token"])
    assert c.links[lid]["house"] is False
    asked = []

    async def converse(agent, text, user_id, builtin=False, timeout=None):
        asked.append((agent, text, user_id, builtin))
        return "Lyset er tændt"

    async def guarded(text):
        return "hoveddør" in text.lower() or bool(GUARD_WORDS.search(text))

    monkeypatch.setattr(c, "_converse", converse)
    monkeypatch.setattr(c, "_guarded", guarded)
    assert c.set_link_house(lid, True) and not c.set_link_house("nope", True)
    m = await c.ask_house(f"link:{lid}", "Tænd lyset i stuen")
    assert m["text"] == "Lyset er tændt" and asked == [(None, "Tænd lyset i stuen", f"link:{lid}", True)]  # only Assist, no AI
    for text in ("Lås hoveddøren op", "Slå alarmen fra", "Åbn garageporten", "Åbn hoveddøren"):
        m = await c.ask_house(f"link:{lid}", text)
        assert "garage" in m["text"].lower() and len(asked) == 1, text
    c.set_link_house(lid, False)
    m = await c.ask_house(f"link:{lid}", "Tænd lyset i stuen")
    assert len(asked) == 1 and "Settings" in m["text"]


async def test_the_guard_finds_a_lock_by_its_name(hass: HomeAssistant, chat) -> None:  # noqa: F811
    c, _ = chat
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "conversation", {})
    hass.config.language = "en"
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front door"})
    hass.states.async_set("light.kitchen", "off", {"friendly_name": "Kitchen light"})
    from homeassistant.components.homeassistant.exposed_entities import async_expose_entity

    for entity_id in ("lock.front_door", "light.kitchen"):
        async_expose_entity(hass, "conversation", entity_id, True)
    assert await c._guarded("Unlock the front door") and await c._guarded("open the garage")
    assert await c._guarded("Turn off the front door")   # no lock word: found by its name
    assert not await c._guarded("Turn on the kitchen light")
