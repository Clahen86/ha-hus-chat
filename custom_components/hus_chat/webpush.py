"""Web push to the chat app opened from a link (no Home Assistant app): VAPID (RFC 8292) and aes128gcm (RFC 8291).

The browser gives a subscription (an endpoint at Google, Apple or Mozilla and two keys); a message is encrypted for
that browser only and handed to its push service, which wakes the app's service worker even when it is closed.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import struct
import time
from typing import Any
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_LOGGER = logging.getLogger(__name__)
SUBJECT = "https://github.com/Clahen86/ha-hus-chat"


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def _raw(pub: ec.EllipticCurvePublicKey) -> bytes:
    return pub.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


class Vapid:
    """The integration's own key pair: push services know the messages come from the same sender as the subscription."""

    def __init__(self, pem: str | None = None) -> None:
        self.key = serialization.load_pem_private_key(pem.encode(), None) if pem else ec.generate_private_key(ec.SECP256R1())

    @property
    def pem(self) -> str:
        return self.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()

    @property
    def public(self) -> str:
        return b64u(_raw(self.key.public_key()))

    def header(self, endpoint: str) -> str:
        u = urlsplit(endpoint)
        head = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
        body = b64u(json.dumps({"aud": f"{u.scheme}://{u.netloc}", "exp": int(time.time()) + 12 * 3600, "sub": SUBJECT},
                               separators=(",", ":")).encode())
        r, s = decode_dss_signature(self.key.sign(f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256())))
        return f"vapid t={head}.{body}.{b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}, k={self.public}"


def encrypt(sub: dict[str, Any], payload: bytes) -> bytes:
    """aes128gcm for one browser: its public key and auth secret, a fresh key of ours and a fresh salt."""
    ua_pub = b64d(sub["keys"]["p256dh"])
    auth = b64d(sub["keys"]["auth"])
    ours = ec.generate_private_key(ec.SECP256R1())
    as_pub = _raw(ours.public_key())
    shared = ours.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_pub))
    ikm = _hkdf(auth, shared, b"WebPush: info\x00" + ua_pub + as_pub, 32)
    salt = os.urandom(16)
    cek = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    body = AESGCM(cek).encrypt(nonce, payload + b"\x02", None)
    return salt + struct.pack(">IB", 4096, len(as_pub)) + as_pub + body


async def send(session: Any, vapid: Vapid, sub: dict[str, Any], data: dict[str, Any], urgent: bool = False) -> bool:
    """Hand one message to the browser's push service. False: the subscription is gone (uninstalled, blocked)."""
    try:
        body = encrypt(sub, json.dumps(data).encode()[:3000])
        async with session.post(sub["endpoint"], data=body, timeout=15, headers={
                "Authorization": vapid.header(sub["endpoint"]), "Content-Encoding": "aes128gcm", "TTL": "86400",
                "Urgency": "high" if urgent else "normal", "Content-Type": "application/octet-stream"}) as r:
            if r.status in (404, 410):
                return False
            if r.status >= 400:
                _LOGGER.debug("Web push refused (%s): %s", r.status, (await r.text())[:200])
    except Exception:  # noqa: BLE001 - one browser failing doesn't stop the others
        _LOGGER.debug("Web push failed", exc_info=True)
    return True
