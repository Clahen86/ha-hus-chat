""""Lige nu": one line on top of the chat with what matters right now - it changes by itself and goes when it's over.

Built from what the chat already knows, nothing to set up:
- a machine that's done and waiting (until it's emptied or the alert is gone)
- someone on the way home, with when they'll be home (until they are home, or 3 hours)
- today's dinner and how many eat with (from the dinner poll, until 20:00)
Each card points at its message, so a tap finds it. Only what the person may see.
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.util import dt as dt_util

ONWAY_S = 3 * 3600
DINNER_UNTIL = 20

WORDS = {
    "da": {"waiting": "venter", "taken": "{name} tager den", "onway": "{name} er på vej hjem", "eta": "ca. {t}",
           "dinner": "Aftensmad", "eat": "{n} spiser med", "eat1": "1 spiser med"},
    "en": {"waiting": "waiting", "taken": "{name} takes it", "onway": "{name} is on the way home", "eta": "about {t}",
           "dinner": "Dinner", "eat": "{n} eat with", "eat1": "1 eats with"},
}


def words(hass: Any) -> dict[str, str]:
    return WORDS.get((hass.config.language or "en").split("-")[0], WORDS["en"])


def cards(chat: Any) -> list[dict[str, Any]]:
    """Everything on "Lige nu" for the whole family; each card names its message (cards_for filters per person)."""
    w, now, out = words(chat.hass), time.time(), []
    for m in reversed(chat.msgs[-300:]):
        old_done = (m.get("taken") or {}).get("by") == "house"  # emptied before 0.14 (no "done" then)
        task = m.get("machine") or m.get("topic") == "waste"
        if m.get("kind") == "house" and m.get("take") and not m.get("done") and not old_done and task and now - m["t"] < 2 * 86400 \
                and now < m.get("until", float("inf")):
            state = w["taken"].format(name=m["taken"]["name"]) if m.get("taken") else w["waiting"]
            out.append({"key": f"m:{m.get('machine') or m['id']}", "icon": "", "text": f"{m.get('title') or ''} · {state}", "msg": m["id"]})
    for who, t0 in list(chat.onway.items()):
        if now - t0 > ONWAY_S:
            continue
        m = next((x for x in reversed(chat.msgs[-300:]) if x["from"] == who and x["t"] >= t0 - 5), None)
        eta = (m or {}).get("eta")
        text = w["onway"].format(name=chat._name(who)) + (f" · {w['eta'].format(t=eta)}" if eta else "")
        out.append({"key": f"o:{who}", "icon": "🚗", "text": text, "msg": m["id"] if m else None})
    d = chat.dinner or {}
    local = dt_util.now()
    if d.get("date") == local.date().isoformat() and local.hour < DINNER_UNTIL and (m := chat.find(d.get("msg") or "")):
        yes = len(m["poll"][0]["votes"]) if m.get("poll") else 0
        dish = str(d.get("dish") or "").strip()
        parts = [w["dinner"] + (f": {dish}" if dish else "")]
        if yes:
            parts.append(w["eat1"] if yes == 1 else w["eat"].format(n=yes))
        out.append({"key": "dinner", "icon": "🍽️", "text": " · ".join(parts), "msg": m["id"]})
    return out


def cards_for(chat: Any, all_cards: list[dict[str, Any]], user_id: str, admin: bool = False) -> list[dict[str, Any]]:
    if not chat.member(user_id, admin):
        return []
    me = chat.sender_of(user_id)
    return [c for c in all_cards if not c.get("msg") or ((m := chat.find(c["msg"])) and chat.can_see(m, user_id, me))]
