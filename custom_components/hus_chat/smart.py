"""Small things the chat understands in a message: "buy milk" (the shopping list) and "remind me ..." (a reminder).

Pure functions - no Home Assistant - so they are easy to test. Danish, Norwegian, Swedish and English.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import math
import re

# ---------- the shopping list ----------
SHOP = re.compile(r"^\s*(?:husk(?:\s+at)?\s+)?(?:køb|kjøp|köp|buy|get)\s+(?:lige\s+|også\s+|some\s+)?(.+?)\s*[.!]*$", re.I)
SPLIT = re.compile(r"\s*(?:,|\bog\b|\band\b|\boch\b|\+)\s*", re.I)


def shop_items(text: str) -> list[str]:
    """"køb mælk, brød og æg" -> ["Mælk", "Brød", "Æg"]. Nothing for an ordinary message."""
    m = SHOP.match(text or "")
    if not m or len(m.group(1)) > 120 or "?" in text:
        return []
    out = []
    for x in SPLIT.split(m.group(1)):
        x = x.strip(" .!")
        if x and len(x) <= 60:
            out.append(x[0].upper() + x[1:])
    return out[:10]


# ---------- reminders ----------
REMIND = re.compile(r"^\s*(?:mind|minn|påminn)\s+(mig|meg|os|oss|oss alla|alle)\s+(?:om|på|at|att)\s+(.+)$|^\s*remind\s+(me|us)\s+(?:to|about|of)?\s*(.+)$", re.I)
DAYS = {"mandag": 0, "tirsdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lørdag": 5, "søndag": 6,
        "måndag": 0, "tisdag": 1, "lördag": 5, "söndag": 6, "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6}
CLOCK = r"(?:kl\.?|klokken|klockan|at)?\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?"
PATTERNS = [  # (pattern, kind) - tried in order; the first that fits is the time, the rest is what to remember
    (re.compile(r"\b(?:om|i|in)\s+(\d+|en|et|ett|an|a|one|half(?:\s+an)?|en\s+halv)\s*(min(?:ut(?:ter|e|es|er)?)?|time[rn]?|timme|timmar|hours?|t)\b", re.I), "in"),
    (re.compile(r"\b(i\s+morgen|i\s+morgon|imorgen|tomorrow)(?:\s+(tidlig|tidig|morning|aften|kväll|evening))?(?:\s+" + CLOCK + r")?", re.I), "tomorrow"),
    (re.compile(r"\b(?:på|on|nu\s+på|næste|nästa|next)?\s*(" + "|".join(DAYS) + r")(?:\s+" + CLOCK + r")?", re.I), "day"),
    (re.compile(r"\b(i\s+aften|i\s+kväll|i\s+kveld|tonight|this\s+evening)(?:\s+" + CLOCK + r")?", re.I), "tonight"),
    (re.compile(r"\b(?:i\s+dag\s+)?(?:kl\.?|klokken|klockan|at)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?", re.I), "at"),
]


def _hm(h: str | None, m: str | None, ampm: str | None, default: tuple[int, int]) -> tuple[int, int] | None:
    if h is None:
        return default
    hh, mm = int(h), int(m or 0)
    if ampm and ampm.lower() == "pm" and hh < 12:
        hh += 12
    if ampm and ampm.lower() == "am" and hh == 12:
        hh = 0
    return (hh, mm) if hh < 24 and mm < 60 else None


def _num(word: str) -> float:
    w = word.lower()
    if w.startswith("half") or w == "en halv":
        return 0.5
    return 1 if w in ("en", "et", "ett", "an", "a", "one") else float(w)


def reminder(text: str, now: datetime) -> dict | None:
    """"mind mig om tandlæge i morgen kl. 8" -> {"when": tomorrow 08:00, "what": "tandlæge", "all": False}.
    None when it isn't a reminder, or no time was given (then nothing is guessed)."""
    m = REMIND.match(text or "")
    if not m:
        return None
    who, rest = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    everyone = who.lower() in ("os", "oss", "oss alla", "alle", "us")
    for pat, kind in PATTERNS:
        f = pat.search(rest)
        if not f:
            continue
        g = f.groups()
        if kind == "in":
            n = _num(g[0])
            unit = g[1].lower()
            when = now + (timedelta(minutes=n) if unit.startswith("min") else timedelta(hours=n))
        elif kind == "tomorrow":
            part = (g[1] or "").lower()
            default = (7, 0) if part in ("tidlig", "tidig", "morning") else (19, 0) if part in ("aften", "kväll", "evening") else (8, 0)
            hm = _hm(g[2], g[3], g[4], default)
            if not hm:
                return None
            when = (now + timedelta(days=1)).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        elif kind == "day":
            hm = _hm(g[1], g[2], g[3], (8, 0))
            if not hm:
                return None
            ahead = (DAYS[g[0].lower()] - now.weekday()) % 7 or 7
            when = (now + timedelta(days=ahead)).replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        elif kind == "tonight":
            hm = _hm(g[1], g[2], g[3], (19, 0))
            if not hm:
                return None
            if hm[0] < 12:
                hm = (hm[0] + 12, hm[1])  # "i aften kl 8" is 20:00
            when = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
        else:  # "kl. 17" - today, or tomorrow if it has passed
            hm = _hm(g[0], g[1], g[2], (8, 0))
            if not hm:
                return None
            when = now.replace(hour=hm[0], minute=hm[1], second=0, microsecond=0)
            if when <= now:
                when += timedelta(days=1)
        what = (rest[:f.start()] + " " + rest[f.end():]).strip(" ,.!")
        what = re.sub(r"^(?:at|att|to)\s+", "", what, flags=re.I)
        if not what or when <= now:
            return None
        return {"when": when, "what": what[0].upper() + what[1:], "all": everyone}
    return None


# ---------- on my way home ----------
def eta_minutes(lat: float | None, lon: float | None, home_lat: float, home_lon: float) -> int | None:
    """About how long home by car: the distance as the crow flies, a bit longer on the road, at town and country speed."""
    if lat is None or lon is None:
        return None
    r = 6371.0
    p1, p2 = math.radians(lat), math.radians(home_lat)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(home_lon - lon) / 2) ** 2
    km = 2 * r * math.asin(math.sqrt(a)) * 1.3
    if km < 0.3:
        return 0
    return max(5, int(round((km / (35 if km < 15 else 60) * 60 + 3) / 5) * 5))
