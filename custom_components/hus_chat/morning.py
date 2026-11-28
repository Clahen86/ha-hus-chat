"""Good morning: one message at 7 with the day ahead - found in Home Assistant, nothing to set up.

Each line only when its source is there (none of them needed):
- the weather today (the first weather entity's daily forecast)
- dinner from Madplan (a day sensor dated today) and who cooks
- chores left today per child in Pligt-pilot
- the cheapest three hours for power the rest of the day (a price sensor with a "prices" list, e.g. Strømligning)

Nothing to say: no message. Off by default - switched on under Settings, "Messages from the house".
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

AT_HOUR = 7
CHEAP_HOURS = 3
SKIP_DISHES = {"", "–", "-", "Før planen", "unknown", "unavailable"}

WORDS = {
    "da": {"title": "☀️ Godmorgen", "weather": "{icon} {hi}° / {lo}°", "rain": "regn {mm} mm", "dinner": "🍽️ Aftensmad: {dish}",
           "cook": "{name} laver den", "chores": "🧹 Pligter i dag: {list}", "cheap": "⚡ Billigst strøm kl. {a}–{b}", "night": "🌙 Færdig i nat og venter: {list}",
           "title_p": "☀️ Godmorgen {name}", "bring_pe": "🎒 Husk idrætstøj!", "bring_swim": "🩱 Husk badetøj og håndklæde!",
           "bring_food": "🍳 Madkundskab i dag", "bring_trip": "🚌 Tur i dag – husk madpakke og godt tøj",
           "kid_rain": "🧥 Tag regnjakke – det regner, når du skal {when} 🌧️", "kid_snow": "⛄ Sne i dag – tag varmt tøj og gode sko",
           "kid_frost": "🧤 Frost i morges – hue og vanter", "kid_storm": "💨 Kraftig blæst – pas på på cyklen",
           "big_rain": "Regn kl. {t} – tag jakke.", "big_snow": "Sne i dag – varmt tøj.", "big_frost": "Frost i morges – hue og handsker.",
           "big_storm": "Kraftig blæst i dag.", "go": "af sted", "home": "hjem", "go_home": "af sted og hjem",
           "ad_rain": "🌧️ Regn {a}–{b}", "ad_kids": " · {list} har fri i det", "ad_snow": "❄️ Sne i dag", "ad_frost": "🧊 Frost i morges",
           "ad_storm": "💨 Kraftig blæst", "aula": "📨 Ny besked fra skolen: {subject} ({sender})",
           "cook_start": "🍳 Du laver {meal} – start kl. {start}, så er den klar kl. {ready}", "cook_ready": "🍳 Du laver {meal} – klar kl. {ready}",
           "cook_plain": "🍳 Du laver {meal} i dag", "school": "🎒 Skole {a}–{b}", "free": "🎒 Fri i dag: {list}", "bday": "🎂 I dag: {list}",
           "bday_soon": "🎁 Om en uge: {list}", "cal": "📅 {list}", "holiday": "🎉 {list}", "mine": "🧹 Dine pligter i dag: {n}"},
    "en": {"title": "☀️ Good morning", "weather": "{icon} {hi}° / {lo}°", "rain": "rain {mm} mm", "dinner": "🍽️ Dinner: {dish}",
           "cook": "{name} cooks", "chores": "🧹 Chores today: {list}", "cheap": "⚡ Cheapest power {a}–{b}", "night": "🌙 Done in the night and waiting: {list}",
           "title_p": "☀️ Good morning {name}", "bring_pe": "🎒 Bring your PE kit!", "bring_swim": "🩱 Bring swimwear and a towel!",
           "bring_food": "🍳 Cooking class today", "bring_trip": "🚌 Trip today – bring a packed lunch and good clothes",
           "kid_rain": "🧥 Take a rain jacket – it rains when you {when} 🌧️", "kid_snow": "⛄ Snow today – warm clothes and good shoes",
           "kid_frost": "🧤 Frost this morning – hat and gloves", "kid_storm": "💨 Strong wind – careful on the bike",
           "big_rain": "Rain at {t} – take a jacket.", "big_snow": "Snow today – warm clothes.", "big_frost": "Frost this morning – hat and gloves.",
           "big_storm": "Strong wind today.", "go": "go", "home": "come home", "go_home": "go and come home",
           "ad_rain": "🌧️ Rain {a}–{b}", "ad_kids": " · {list} out of school in it", "ad_snow": "❄️ Snow today", "ad_frost": "🧊 Frost this morning",
           "ad_storm": "💨 Strong wind", "aula": "📨 New message from school: {subject} ({sender})",
           "cook_start": "🍳 You cook {meal} – start at {start} to have it ready at {ready}", "cook_ready": "🍳 You cook {meal} – ready at {ready}",
           "cook_plain": "🍳 You cook {meal} today", "school": "🎒 School {a}–{b}", "free": "🎒 Out of school today: {list}", "bday": "🎂 Today: {list}",
           "bday_soon": "🎁 In a week: {list}", "cal": "📅 {list}", "holiday": "🎉 {list}", "mine": "🧹 Your chores today: {n}"},
}
SKY = {"sunny": "☀️", "clear-night": "🌙", "partlycloudy": "⛅", "cloudy": "☁️", "fog": "🌫️", "rainy": "🌧️", "pouring": "🌧️",
       "snowy": "🌨️", "snowy-rainy": "🌨️", "hail": "🌨️", "lightning": "🌩️", "lightning-rainy": "⛈️", "windy": "💨",
       "windy-variant": "💨", "exceptional": "⚠️"}


def words(hass: HomeAssistant) -> dict[str, str]:
    return WORDS.get((hass.config.language or "en").split("-")[0], WORDS["en"])


async def weather_line(hass: HomeAssistant, w: dict[str, str]) -> str | None:
    states = sorted(hass.states.async_all("weather"), key=lambda s: s.entity_id)
    if not states:
        return None
    try:
        res = await hass.services.async_call("weather", "get_forecasts", {"entity_id": states[0].entity_id, "type": "daily"},
                                             blocking=True, return_response=True)
        day = ((res or {}).get(states[0].entity_id) or {}).get("forecast", [])[0]
        hi, lo = round(float(day["temperature"])), round(float(day.get("templow", day["temperature"])))
    except Exception:  # noqa: BLE001 - no daily forecast: no weather line
        return None
    line = w["weather"].format(icon=SKY.get(str(day.get("condition")), "🌡️"), hi=hi, lo=lo)
    mm = day.get("precipitation")
    if isinstance(mm, (int, float)) and mm >= 0.5:
        line += f", {w['rain'].format(mm=round(mm, 1))}"
    return line


def dinner_line(hass: HomeAssistant, w: dict[str, str], today: str) -> str | None:
    seen: list[str] = []
    for e in er.async_get(hass).entities.values():
        if e.platform != "madplan" or e.domain != "sensor":
            continue
        s = hass.states.get(e.entity_id)
        if not s or s.attributes.get("dato") != today or s.attributes.get("fjernet") or s.state in SKIP_DISHES:
            continue
        dish = s.state + (f" ({w['cook'].format(name=s.attributes['kok_navn'])})" if s.attributes.get("kok_navn") else "")
        if dish not in seen:
            seen.append(dish)
    return w["dinner"].format(dish=" / ".join(seen)) if seen else None


async def chores_line(hass: HomeAssistant, w: dict[str, str]) -> str | None:
    get = getattr(hass.data.get("pligt_pilot"), "today", None)
    if not callable(get):
        return None
    try:
        counts = await get()
    except Exception:  # noqa: BLE001
        return None
    left = [f"{name} {n}" for name, n in (counts or {}).items() if isinstance(n, int) and n > 0]
    return w["chores"].format(list=", ".join(left)) if left else None


def cheap_line(hass: HomeAssistant, w: dict[str, str], now: datetime) -> str | None:
    for s in sorted(hass.states.async_all("sensor"), key=lambda s: s.entity_id):
        prices = s.attributes.get("prices")
        if not isinstance(prices, list) or not prices or not isinstance(prices[0], dict) or "start" not in prices[0]:
            continue
        hours: dict[datetime, list[float]] = {}
        for p in prices:
            try:
                start = p["start"] if isinstance(p["start"], datetime) else dt_util.parse_datetime(str(p["start"]))
                start = dt_util.as_local(start)
                if start.date() == now.date() and start.hour >= now.hour:
                    hours.setdefault(start.replace(minute=0, second=0, microsecond=0), []).append(float(p["price"]))
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        keys = sorted(hours)
        if len(keys) < CHEAP_HOURS:
            continue
        avg = {k: sum(v) / len(v) for k, v in hours.items()}
        runs = [keys[i:i + CHEAP_HOURS] for i in range(len(keys) - CHEAP_HOURS + 1)
                if keys[i + CHEAP_HOURS - 1] - keys[i] == timedelta(hours=CHEAP_HOURS - 1)]
        if not runs:
            continue
        best = min(runs, key=lambda r: sum(avg[k] for k in r))
        return w["cheap"].format(a=f"{best[0].hour:02d}", b=f"{(best[-1].hour + 1) % 24:02d}")
    return None


def night_line(chat: Any, w: dict[str, str]) -> str | None:
    """Machines that finished in the night and still wait - no phone rang for them (watch.py)."""
    if chat is None:
        return None
    since = time.time() - 12 * 3600
    names = [m.get("title") or "" for m in chat.msgs[-200:]
             if m.get("night") and not m.get("done") and not m.get("taken") and m["t"] >= since]
    return w["night"].format(list=", ".join(n for n in names if n)) if names else None


async def build(hass: HomeAssistant, now: datetime | None = None, chat: Any = None) -> tuple[str, str] | None:
    """(title, text), or None when there's nothing to say."""
    now, w = now or dt_util.now(), words(hass)
    lines = [await weather_line(hass, w), dinner_line(hass, w, now.date().isoformat()), await chores_line(hass, w),
             night_line(chat, w), cheap_line(hass, w, now)]
    lines = [x for x in lines if x]
    return (w["title"], "\n".join(lines)) if lines else None


# ---------- one good morning per person (0.15) ----------
def _hm(d: datetime) -> str:
    return f"{d.hour}:{d.minute:02d}"


def _who(summary: str, first: str) -> str:
    """ "Lilly: 🎂 Melina Mosskov P" -> "Melina Mosskov P" (a birthday calendar names the child first)."""
    s = re.sub(rf"^\s*{re.escape(first)}\s*:\s*", "", summary, flags=re.I) if first else summary
    return re.sub(r"^[\s🎂🎁🎉]+", "", s).strip()


async def common_lines(hass: HomeAssistant, now: datetime, chat: Any, cals: list[dict[str, Any]], w: dict[str, str]) -> list[str]:
    """For everyone: the weather, dinner, a holiday today, machines done in the night."""
    from . import calendars

    lines = [await weather_line(hass, w), dinner_line(hass, w, now.date().isoformat())]
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hol = []
    for c in (c for c in cals if c["kind"] == "holiday"):
        hol += [e["summary"] for e in await calendars.events(hass, c["entity_id"], day0, day0 + timedelta(days=1)) if e["all_day"] and e["summary"]]
    lines.append(w["holiday"].format(list=", ".join(dict.fromkeys(hol))) if hol else None)
    lines.append(night_line(chat, w))
    return [x for x in lines if x]


async def own_lines(hass: HomeAssistant, chat: Any, p: dict[str, Any], adult: bool, cals: list[dict[str, Any]],
                    now: datetime, w: dict[str, str], chores: dict[str, int] | None, gifts: list[str] | None = None,
                    ctx: dict[str, Any] | None = None) -> list[str]:
    """Only what is this person's: a child their own school day, birthdays and chores; a grown-up when each child is
    out of school, the family's calendar today, everyone's chores and the cheapest power."""
    from . import calendars

    first = (p.get("name") or "").split(" ")[0]
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    lines: list[str | None] = []
    names = {x["id"]: (x.get("name") or "").split(" ")[0] for x in chat.people()}
    ctx = ctx or {}
    wx = ctx.get("wx") or []
    kid_spans = ctx.get("spans") or {}  # person -> (first lesson, last lesson) today
    same_first = sum(1 for x in chat.people() if (x.get("name") or "").split(" ")[0].lower() == first.lower()) > 1
    if not same_first and (cook := (ctx.get("cook") or {}).get(first.lower())):  # the cook's own line: when to start
        lines.append(w["cook_start"].format(meal=cook["meal"], start=cook["start"], ready=cook["ready"]) if cook.get("start")
                     else w["cook_ready"].format(meal=cook["meal"], ready=cook["ready"]) if cook.get("ready") else w["cook_plain"].format(meal=cook["meal"]))
    if adult:
        out = []
        for c in (c for c in cals if c["kind"] == "school" and c["person"]):
            if span := calendars.day_span(await calendars.events(hass, c["entity_id"], day0, day0 + timedelta(days=1))):
                out.append(f"{names.get(c['person'], '?')} {_hm(span[1])}")
        lines.append(w["free"].format(list=" · ".join(out)) if out else None)
        lines.append(weather_adult(wx, kid_spans, names, w))
        if ctx.get("aula"):
            lines.append(w["aula"].format(subject=ctx["aula"]["subject"], sender=ctx["aula"]["sender"]))
        fam = []
        for c in (c for c in cals if c["kind"] == "family"):
            for e in await calendars.events(hass, c["entity_id"], day0, day0 + timedelta(days=1)):
                if e["summary"]:
                    fam.append(e["summary"] if e["all_day"] else f"{_hm(e['start'])} {e['summary']}")
        lines.append(w["cal"].format(list=", ".join(fam[:4])) if fam else None)
        left = [f"{n} {k}" for n, k in (chores or {}).items() if isinstance(k, int) and k > 0]
        lines.append(w["chores"].format(list=", ".join(left)) if left else None)
        lines.append(cheap_line(hass, w, now))
    else:
        mine_cals = [c for c in cals if c["kind"] == "school" and c["person"] == p["id"]]
        for c in mine_cals:
            evs = await calendars.events(hass, c["entity_id"], day0, day0 + timedelta(days=1))
            if span := calendars.day_span(evs):
                lines.append(w["school"].format(a=_hm(span[0]), b=_hm(span[1])))
            from . import smart

            for what in smart.bring([e["summary"] for e in evs]):  # "Husk idrætstøj" - from the timetable (also a trip day)
                lines.append(w[f"bring_{what}"])
        span = kid_spans.get(p["id"])
        if span:  # the child's own times: going and coming home
            windows = [(span[0] - timedelta(hours=1), span[0], "go"), (span[1], span[1] + timedelta(hours=1), "home")]
            lines += weather_advice(wx, windows, w, "kid")
        elif not mine_cals:  # a bigger child without a timetable here: the usual times
            windows = [(day0 + timedelta(hours=7), day0 + timedelta(hours=9), "go"), (day0 + timedelta(hours=14), day0 + timedelta(hours=17), "home")]
            lines += weather_advice(wx, windows, w, "big")
        mine = next((k for n, k in (chores or {}).items() if n.split(" ")[0].lower() == first.lower()), 0)
        lines.append(w["mine"].format(n=mine) if isinstance(mine, int) and mine > 0 else None)
    today, soon = [], []
    for c in (c for c in cals if c["kind"] == "birthday" and (c["person"] == p["id"] or (adult and not c["person"]))):
        for e in await calendars.events(hass, c["entity_id"], day0, day0 + timedelta(days=8)):
            if not e["summary"]:
                continue
            if e["start"].date() == day0.date():
                today.append(_who(e["summary"], first))
            elif e["start"].date() == (day0 + timedelta(days=7)).date():
                soon.append(_who(e["summary"], first))
    lines.append(w["bday"].format(list=", ".join(today)) if today else None)
    lines.append(w["bday_soon"].format(list=", ".join(soon)) if soon else None)
    if gifts is not None:
        gifts += [n for n in soon if n not in gifts]  # "Køb gave" under the message
    return [x for x in lines if x]


async def for_everyone(hass: HomeAssistant, chat: Any, people: list[dict[str, Any]], now: datetime | None = None) -> list[tuple[dict[str, Any], str, str, list[str]]]:
    """[(person, title, text, gifts)] - one good morning each, only with what is theirs. Nobody with nothing to say."""
    from . import calendars

    now, w = now or dt_util.now(), words(hass)
    cals = calendars.find(hass, chat.people())
    common = await common_lines(hass, now, chat, cals, w)
    get = getattr(hass.data.get("pligt_pilot"), "today", None)
    try:
        chores = await get() if callable(get) else None
    except Exception:  # noqa: BLE001
        chores = None
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    spans = {}
    for c in (c for c in cals if c["kind"] == "school" and c["person"]):
        if span := calendars.day_span(await calendars.events(hass, c["entity_id"], day0, day0 + timedelta(days=1))):
            old = spans.get(c["person"])
            spans[c["person"]] = (min(span[0], old[0]), max(span[1], old[1])) if old else span
    ctx = {"wx": await weather_hours(hass), "spans": spans, "aula": aula_new(hass, chat), "cook": cooks_today(hass, chat, now.date().isoformat())}
    out, told_aula = [], False
    for p in people:
        gifts: list[str] = []
        adult = await chat.is_adult(p)
        lines = common + await own_lines(hass, chat, p, adult, cals, now, w, chores, gifts, ctx)
        if lines:
            told_aula = told_aula or (adult and bool(ctx["aula"]))
            out.append((p, w["title_p"].format(name=(p.get("name") or "").split(" ")[0]).strip(), "\n".join(lines), gifts))
    if told_aula:  # each school message told once (per Aula sensor)
        chat.sent_days["aula_seen"] = {**(chat.sent_days.get("aula_seen") or {}), ctx["aula"]["entity"]: ctx["aula"]["key"]}
    return out


# ---------- the week ahead (Sunday evening) ----------
DAY_SHORT = {"da": ["man", "tir", "ons", "tor", "fre", "lør", "søn"], "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
WEEK_WORDS = {
    "da": {"title": "📅 Ugen der kommer", "food": "🍽️ {list}", "waste": "🗑️ {list}", "free": "🎒 Ingen skole: {list}", "bday": "🎂 {list}"},
    "en": {"title": "📅 The week ahead", "food": "🍽️ {list}", "waste": "🗑️ {list}", "free": "🎒 No school: {list}", "bday": "🎂 {list}"},
}


async def week_for_everyone(hass: HomeAssistant, chat: Any, people: list[dict[str, Any]], now: datetime | None = None) -> list[tuple[dict[str, Any], str, str, list[str]]]:
    """Sunday evening, one each: the week's dinners, the bins, schooldays without school, birthdays - only what is theirs
    (a child their own; the grown-ups every child's). Good morning then only says what is today."""
    from . import calendars

    now = now or dt_util.now()
    lang = (hass.config.language or "en").split("-")[0]
    ww, short = WEEK_WORDS.get(lang, WEEK_WORDS["en"]), DAY_SHORT.get(lang, DAY_SHORT["en"])
    start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)  # Monday
    days = [start + timedelta(days=i) for i in range(7)]
    cals = calendars.find(hass, chat.people())
    names = {x["id"]: (x.get("name") or "").split(" ")[0] for x in chat.people()}
    w = words(hass)
    food = []
    for d in days:
        dish = dinner_line(hass, {**w, "dinner": "{dish}", "cook": "{name}"}, d.date().isoformat())
        if dish:
            plain = re.sub(r"\s*\(.*?\)", "", dish)  # without "(Silas laver den)"
            food.append(f"{short[d.weekday()]} {plain}")
    bins = []
    for c in (c for c in cals if c["kind"] == "waste"):
        for e in await calendars.events(hass, c["entity_id"], start, start + timedelta(days=7)):
            if e["summary"]:
                bins.append(f"{short[e['start'].weekday()]} {e['summary']}")
    busy: dict[str, set] = {}  # person -> days with lessons, from all their timetables
    for c in (c for c in cals if c["kind"] == "school" and c["person"]):
        evs = await calendars.events(hass, c["entity_id"], start, start + timedelta(days=7), strict=True)
        if evs is None:
            busy[c["person"]] = {d.date() for d in days}  # can't be read: no "no school" guessed
            continue
        if evs:
            busy.setdefault(c["person"], set()).update(e["start"].date() for e in evs if not e["all_day"])
    # no timetable this week at all (a holiday week): nothing to say
    free = {k: [short[d.weekday()] for d in days[:5] if d.date() not in v] for k, v in busy.items() if v}
    out = []
    for p in people:
        adult = await chat.is_adult(p)
        first = names.get(p["id"], "")
        lines = [ww["food"].format(list=" · ".join(food)) if food else None]
        if adult:
            lines.append(ww["waste"].format(list=" · ".join(dict.fromkeys(bins))) if bins else None)
            nf = [f"{names.get(k, '?')} {', '.join(v)}" for k, v in free.items() if v]
            lines.append(ww["free"].format(list=" · ".join(nf)) if nf else None)
        elif free.get(p["id"]):
            lines.append(ww["free"].format(list=", ".join(free[p["id"]])))
        bd = []
        for c in (c for c in cals if c["kind"] == "birthday" and (c["person"] == p["id"] or (adult and not c["person"]))):
            for e in await calendars.events(hass, c["entity_id"], start, start + timedelta(days=7)):
                if e["summary"]:
                    bd.append(f"{short[e['start'].weekday()]} {_who(e['summary'], first)}")
        lines.append(ww["bday"].format(list=" · ".join(bd)) if bd else None)
        lines = [x for x in lines if x]
        if lines:
            out.append((p, ww["title"], "\n".join(lines), []))
    return out


# ---------- the weather when it matters (0.16) ----------
RAIN = {"rainy", "pouring", "lightning-rainy", "hail"}
SNOW = {"snowy", "snowy-rainy"}


async def weather_hours(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Today's hourly forecast from the first weather entity: [{t, rain, snow, temp, wind_ms}]."""
    states = sorted(hass.states.async_all("weather"), key=lambda s: s.entity_id)
    if not states:
        return []
    st = states[0]
    unit = str(st.attributes.get("wind_speed_unit") or "km/h").lower()
    to_ms = {"km/h": 1 / 3.6, "kph": 1 / 3.6, "mph": 0.44704, "kn": 0.51444, "ft/s": 0.3048}.get(unit, 1.0)
    fahrenheit = "f" in str(st.attributes.get("temperature_unit") or "°C").lower()
    today = dt_util.now().date()
    try:
        res = await hass.services.async_call("weather", "get_forecasts", {"entity_id": st.entity_id, "type": "hourly"}, blocking=True, return_response=True)
    except Exception:  # noqa: BLE001 - no hourly forecast: no advice
        return []
    out = []
    for f in ((res or {}).get(st.entity_id) or {}).get("forecast", []):
        try:
            t = dt_util.as_local(dt_util.parse_datetime(str(f["datetime"])))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        if t.date() != today:
            continue  # only today
        cond = str(f.get("condition") or "")
        mm = f.get("precipitation") if isinstance(f.get("precipitation"), (int, float)) else 0
        if str(st.attributes.get("precipitation_unit") or "mm").lower() == "in":
            mm *= 25.4
        temp = f.get("temperature")
        if fahrenheit and isinstance(temp, (int, float)):
            temp = (temp - 32) * 5 / 9
        out.append({"t": t, "rain": cond in RAIN or (mm >= 0.3 and cond not in SNOW), "snow": cond in SNOW,
                    "temp": temp, "wind_ms": (f.get("wind_speed") or 0) * to_ms})
    return out


def weather_advice(hours: list[dict[str, Any]], windows: list[tuple[datetime, datetime, str]], w: dict[str, str], who: str) -> list[str]:
    """A child's (who="kid") or bigger child's (who="big") advice for the times they're out: rain, snow, frost, wind."""
    inside = lambda h: [x for x in windows if x[0] <= h["t"] < x[1] or (h["t"] <= x[0] < h["t"] + timedelta(hours=1))]  # noqa: E731
    rain_when = sorted({x[2] for h in hours if h["rain"] for x in inside(h)})
    rain_t = next((h["t"] for h in hours if h["rain"] and inside(h)), None)
    out = []
    if rain_when:
        out.append(w["kid_rain"].format(when=w["go_home"] if len(rain_when) == 2 else w[rain_when[0]]) if who == "kid"
                   else w["big_rain"].format(t=f"{rain_t.hour}")) if rain_t else None
    if any(h["snow"] and inside(h) for h in hours):
        out.append(w[f"{who}_snow"])
    elif any(isinstance(h["temp"], (int, float)) and h["temp"] <= 0 for h in hours if inside(h) and any(x[2] == "go" for x in inside(h))):
        out.append(w[f"{who}_frost"])
    if any(h["wind_ms"] >= 14 for h in hours if inside(h)):
        out.append(w[f"{who}_storm"])
    return [x for x in out if x]


def weather_adult(hours: list[dict[str, Any]], spans: dict[str, tuple[datetime, datetime]], names: dict[str, str], w: dict[str, str]) -> str | None:
    """For the grown-ups, one line: rain from–to and which children are out of school in it; snow, frost, wind."""
    day = [h for h in hours if 6 <= h["t"].hour <= 20]
    runs: list[list[datetime]] = []  # unbroken hours of rain: 8–9 and 17–18 stay two
    for h in day:
        if h["rain"]:
            if runs and h["t"] - runs[-1][1] <= timedelta(hours=1):
                runs[-1][1] = h["t"]
            else:
                runs.append([h["t"], h["t"]])
    bits = []
    if runs:
        line = w["ad_rain"].format(a=f"{runs[0][0].hour}", b=f"{(runs[0][1] + timedelta(hours=1)).hour}") + "".join(
            f", {r[0].hour}–{(r[1] + timedelta(hours=1)).hour}" for r in runs[1:])
        kids = [names.get(k, "?") for k, s in spans.items() if any(r[0] <= s[1] < r[1] + timedelta(hours=1) for r in runs)]
        bits.append(line + (w["ad_kids"].format(list=", ".join(kids)) if kids else ""))
    if any(h["snow"] for h in day):
        bits.append(w["ad_snow"])
    elif any(isinstance(h["temp"], (int, float)) and h["temp"] <= 0 and h["t"].hour <= 9 for h in day):
        bits.append(w["ad_frost"])
    if any(h["wind_ms"] >= 14 for h in day):
        bits.append(w["ad_storm"])
    return " · ".join(bits) if bits else None


def aula_new(hass: HomeAssistant, chat: Any) -> dict[str, str] | None:
    """A new message from school (Aula) since it was last told - sender and subject only."""
    from homeassistant.helpers import entity_registry as er

    reg = er.async_get(hass)
    for st in hass.states.async_all("binary_sensor"):
        ent = reg.async_get(st.entity_id)
        if not ent or ent.platform != "aula" or "subject" not in st.attributes:
            continue
        subject, sender = str(st.attributes.get("subject") or "").strip(), str(st.attributes.get("sender") or "").strip()
        import hashlib

        key = hashlib.sha1(f"{sender}|{subject}|{st.attributes.get('text') or ''}".encode()).hexdigest()[:16]
        seen = chat.sent_days.get("aula_seen") or {}
        if subject and seen.get(st.entity_id) != key:
            return {"subject": subject[:90], "sender": sender[:40], "key": key, "entity": st.entity_id}
    return None


def cooks_today(hass: HomeAssistant, chat: Any, today: str) -> dict[str, dict[str, Any]]:
    """first name (lower) -> {meal, ready, start}: who cooks today (Madplan), when it must be ready and when to start
    (the dish's own cooking time from Madplan's day sensor)."""
    dishes = {}  # dish -> its cooking time (minutes), today
    for e in er.async_get(hass).entities.values():
        if e.platform == "madplan" and e.domain == "sensor" and (s := hass.states.get(e.entity_id)) and s.attributes.get("dato") == today:
            if isinstance(s.attributes.get("tid"), (int, float)):
                dishes[str(s.state).strip().lower()] = int(s.attributes["tid"])
    out = {}
    for c in (chat.cooks or {}).values():
        if c.get("date") != today or not c.get("kid"):
            continue
        meal = str(c.get("meal") or "").strip().lower()
        mins = dishes.get(meal) or (next(iter(dishes.values())) if len(dishes) == 1 else None)
        ready, start = (c.get("time") or "")[:5], None
        if ready and mins:
            try:
                h, m = (int(x) for x in ready.split(":"))
                t = datetime(2000, 1, 1, h, m) - timedelta(minutes=mins)
                start = f"{t.hour}:{t.minute:02d}"
            except ValueError:
                start = None
        out[c["kid"].split(" ")[0].lower()] = {"meal": c.get("meal") or "", "ready": ready or None, "start": start}
    return out
